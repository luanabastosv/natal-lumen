"""Painel da coordenacao da monitoria, e a divisao de cada dia em nucleos.

A monitoria responde pelo PAPEL e pelo DIA: os cartoes que as criancas
escrevem, as autorizacoes, quem tem cuidado especial, e como as instituicoes de
cada dia se dividem nos nucleos de rodizio (A a D), cada uma com a cor de bata
dela.

O painel inteiro e da coordenacao da monitoria, da coordenacao geral e da
administracao geral. O monitor de base ve o MESMO painel recortado nas
instituicoes dele: as criancas, os cartoes e autorizacoes que faltam, e quem
precisa de cuidado especial. Os nucleos continuam so da coordenacao.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Autorizacao, Cartao, Crianca, DiaEvento, Edicao, Instituicao, InstituicaoDia
from app.schemas.monitoria import (
    CuidadoCrianca,
    DiaMonitoria,
    InstituicaoMonitoria,
    NucleosIn,
    PainelMonitoria,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import contexto_atual
from app.servicos.log import registrar

router = APIRouter(prefix="/monitoria", tags=["monitoria"])

BD = Annotated[Session, Depends(get_db)]
# contexto_atual ja confere o CSRF nos metodos que alteram dados.
Logado = Annotated[ContextoAcesso, Depends(contexto_atual)]

PERFIL_COORDENACAO_MONITORIA = "Monitoria - coordenacao"
PERFIL_MONITOR = "Monitoria - monitores"


def _so_coordenacao_da_monitoria(ctx: ContextoAcesso, edicao_id: int) -> None:
    if ctx.e_coordenacao_geral(edicao_id):
        return
    if any(
        v.edicao_id == edicao_id and v.perfil == PERFIL_COORDENACAO_MONITORIA
        for v in ctx.vinculos
    ):
        return
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "Este painel e da coordenacao da monitoria.",
    )


def _alcance_do_painel(ctx: ContextoAcesso, edicao_id: int) -> frozenset[int] | None:
    """None = a edicao inteira (quem coordena). Um conjunto = as instituicoes
    do monitor — vazio, se a coordenacao ainda nao deu nenhuma a ele."""
    try:
        _so_coordenacao_da_monitoria(ctx, edicao_id)
        return None
    except HTTPException:
        pass
    for v in ctx.vinculos:
        if v.edicao_id == edicao_id and v.perfil == PERFIL_MONITOR:
            return v.instituicoes
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Este painel e da monitoria.")


@router.get("/{edicao_id}/painel", response_model=PainelMonitoria)
def painel(edicao_id: int, db: BD, ctx: Logado):
    alcance = _alcance_do_painel(ctx, edicao_id)
    edicao = db.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    vai = (Crianca.edicao_id == edicao_id) & Crianca.desistiu_em.is_(None)
    if alcance is not None:
        vai = vai & Crianca.instituicao_id.in_(alcance)

    # Uma linha por instituicao: criancas que vao, cartoes de cada tipo e
    # autorizacoes. Subconsultas por crianca, e nao joins, para um cartao a
    # mais nao multiplicar a contagem de criancas.
    cesta = (
        select(func.count()).where(Cartao.crianca_id == Crianca.id, Cartao.tipo == "cesta")
        .correlate(Crianca).scalar_subquery()
    )
    festa = (
        select(func.count()).where(Cartao.crianca_id == Crianca.id, Cartao.tipo == "festa")
        .correlate(Crianca).scalar_subquery()
    )
    autorizada = (
        select(func.count()).where(Autorizacao.crianca_id == Crianca.id)
        .correlate(Crianca).scalar_subquery()
    )
    contas = {
        l.instituicao_id: l
        for l in db.execute(
            select(
                Crianca.instituicao_id,
                func.count().label("criancas"),
                func.sum(cesta).label("cesta"),
                func.sum(festa).label("festa"),
                func.sum(autorizada).label("autorizacoes"),
            )
            .where(vai)
            .group_by(Crianca.instituicao_id)
        ).all()
    }

    # Cuidados: as criancas que vao e cuja autorizacao marcou alguma coisa.
    cuidados: dict[int, list[CuidadoCrianca]] = {}
    for c, a in db.execute(
        select(Crianca, Autorizacao)
        .join(Autorizacao, Autorizacao.crianca_id == Crianca.id)
        .where(
            vai,
            Autorizacao.necessidade_especial.is_(True) | Autorizacao.restricao_alimentar.is_(True),
        )
        .order_by(Crianca.codigo)
    ).all():
        cuidados.setdefault(c.instituicao_id, []).append(
            CuidadoCrianca(
                crianca_id=c.id,
                codigo=c.codigo,
                nome=c.nome,
                necessidade_especial=a.necessidade_especial_qual if a.necessidade_especial else None,
                restricao_alimentar=a.restricao_alimentar_qual if a.restricao_alimentar else None,
            )
        )

    instituicoes = db.scalars(
        select(Instituicao).where(Instituicao.id.in_(contas.keys())).order_by(Instituicao.nome)
    ).all() if contas else []
    dias_das = {
        d.instituicao_id: d
        for d in db.scalars(
            select(InstituicaoDia).where(InstituicaoDia.edicao_id == edicao_id)
        ).all()
    }
    dias = {d.id: d for d in db.scalars(select(DiaEvento).where(DiaEvento.edicao_id == edicao_id)).all()}

    linhas = []
    for inst in instituicoes:
        c = contas[inst.id]
        idia = dias_das.get(inst.id)
        dia = dias.get(idia.dia_evento_id) if idia else None
        linhas.append(
            InstituicaoMonitoria(
                instituicao_id=inst.id,
                instituicao=inst.nome,
                sigla=inst.sigla,
                dia_evento_id=dia.id if dia else None,
                dia_data=dia.data if dia else None,
                dia_descricao=dia.descricao if dia else None,
                nucleo=idia.nucleo if idia else None,
                cor_bata_nome=idia.cor_bata_nome if idia else None,
                cor_bata_hex=idia.cor_bata_hex if idia else None,
                criancas=c.criancas,
                cartoes_cesta=int(c.cesta or 0),
                cartoes_festa=int(c.festa or 0),
                autorizacoes=int(c.autorizacoes or 0),
                cuidados=cuidados.get(inst.id, []),
            )
        )

    por_dia: dict[int | None, DiaMonitoria] = {}
    for l in linhas:
        d = por_dia.setdefault(
            l.dia_evento_id,
            DiaMonitoria(
                dia_evento_id=l.dia_evento_id, data=l.dia_data, descricao=l.dia_descricao,
                instituicoes=0, criancas=0, necessidade_especial=0, restricao_alimentar=0,
            ),
        )
        d.instituicoes += 1
        d.criancas += l.criancas
        d.necessidade_especial += sum(1 for x in l.cuidados if x.necessidade_especial)
        d.restricao_alimentar += sum(1 for x in l.cuidados if x.restricao_alimentar)

    return PainelMonitoria(
        edicao=edicao.nome,
        criancas=sum(l.criancas for l in linhas),
        cartoes_cesta=sum(l.cartoes_cesta for l in linhas),
        cartoes_festa=sum(l.cartoes_festa for l in linhas),
        autorizacoes=sum(l.autorizacoes for l in linhas),
        necessidade_especial=sum(d.necessidade_especial for d in por_dia.values()),
        restricao_alimentar=sum(d.restricao_alimentar for d in por_dia.values()),
        # Os dias em ordem de data; "sem dia" por ultimo.
        por_dia=sorted(por_dia.values(), key=lambda d: (d.data is None, d.data or 0)),
        por_instituicao=linhas,
    )


@router.put("/{edicao_id}/nucleos", response_model=PainelMonitoria)
def salvar_nucleos(edicao_id: int, dados: NucleosIn, db: BD, ctx: Logado):
    """Grava o nucleo e a cor da bata de cada instituicao, de uma vez.

    So instituicoes que ja tem dia nesta edicao: o nucleo e uma divisao DO
    DIA, e sem dia nao ha em que nucleo cair.
    """
    _so_coordenacao_da_monitoria(ctx, edicao_id)

    registros = {
        d.instituicao_id: d
        for d in db.scalars(
            select(InstituicaoDia).where(
                InstituicaoDia.edicao_id == edicao_id,
                InstituicaoDia.instituicao_id.in_([i.instituicao_id for i in dados.instituicoes]),
            )
        ).all()
    }
    sem_dia = [i.instituicao_id for i in dados.instituicoes if i.instituicao_id not in registros]
    if sem_dia:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ha instituicoes sem dia do evento nesta edicao. Defina o dia delas antes.",
        )

    def normal(nucleo, nome, hexa):
        return (nucleo or None, (nome or "").strip() or None, hexa.lower() if hexa else None)

    # Alguem salvou estas instituicoes enquanto esta janela estava aberta:
    # recusa tudo, antes de gravar, e diz quais.
    mexidas = []
    for i in dados.instituicoes:
        if i.antes is None:
            continue
        r = registros[i.instituicao_id]
        if normal(i.antes.nucleo, i.antes.cor_bata_nome, i.antes.cor_bata_hex) != normal(
            r.nucleo, r.cor_bata_nome, r.cor_bata_hex
        ):
            mexidas.append(i.instituicao_id)
    if mexidas:
        nomes = db.scalars(
            select(Instituicao.nome).where(Instituicao.id.in_(mexidas)).order_by(Instituicao.nome)
        ).all()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Outra pessoa mudou os nucleos enquanto voce editava ("
            + ", ".join(nomes[:5]) + (" e outras" if len(nomes) > 5 else "")
            + "). Feche a janela e abra de novo para ver o que esta salvo.",
        )

    mudancas = []
    for i in dados.instituicoes:
        r = registros[i.instituicao_id]
        cor_hex = i.cor_bata_hex.lower() if i.cor_bata_hex else None
        cor_nome = (i.cor_bata_nome or "").strip() or None
        if (r.nucleo, r.cor_bata_nome, r.cor_bata_hex) != (i.nucleo, cor_nome, cor_hex):
            mudancas.append({
                "instituicao_id": i.instituicao_id,
                "antes": [r.nucleo, r.cor_bata_nome],
                "depois": [i.nucleo, cor_nome],
            })
        r.nucleo, r.cor_bata_nome, r.cor_bata_hex = i.nucleo, cor_nome, cor_hex

    if mudancas:
        registrar(
            db, "nucleos_organizados", usuario_id=ctx.usuario.id,
            tabela="instituicao_dia", detalhes={"edicao_id": edicao_id, "mudancas": mudancas},
        )
    db.commit()
    return painel(edicao_id, db, ctx)
