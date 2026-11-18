"""Edicoes e os dias de cada uma.

Edicao e criada so pela administracao geral. Os dias sao da coordenacao, que
tem gerenciar_cadastros.

A edicao nova nao nasce vazia de gente: a coordenacao e da CIDADE, entao quem
coordena a cidade ja entra nela. Sem isso, abrir 2027 deixaria a cidade parada
ate a administracao geral recriar os vinculos um a um.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Crianca,
    DiaEvento,
    Edicao,
    Instituicao,
    Perfil,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.schemas.cadastros import (
    CampanhaFestaIn,
    DependenciasOut,
    DiaDaInstituicaoIn,
    DiaDaInstituicaoOut,
    DiaIn,
    DiaOut,
    EdicaoEditar,
    EdicaoIn,
    EdicaoOut,
    MonitorDaInstituicao,
    MonitorResponsavelIn,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import Contexto, exige_admin_geral, exige_permissao
from app.servicos import coordenacao, dias, exclusao
from app.seguranca.reconfirmar import exigir_senha
from app.servicos.log import registrar

router = APIRouter(prefix="/edicoes", tags=["cadastros"])

BD = Annotated[Session, Depends(get_db)]
Admin = Annotated[ContextoAcesso, Depends(exige_admin_geral)]


def _saida(edicao: Edicao) -> EdicaoOut:
    return EdicaoOut(
        id=edicao.id,
        cidade_id=edicao.cidade_id,
        cidade=edicao.cidade.nome,
        uf=edicao.cidade.uf,
        ano=edicao.ano,
        nome=edicao.nome,
        valor_cesta=edicao.valor_cesta,
        valor_festa=edicao.valor_festa,
        ativa=edicao.ativa,
        festa_liberada=edicao.festa_liberada_em is not None,
    )


def _buscar_edicao(db: Session, ctx: ContextoAcesso, edicao_id: int) -> Edicao:
    """Busca a edicao conferindo se o usuario a alcanca."""
    edicao = db.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    if not ctx.admin_geral and edicao_id not in ctx.edicoes:
        # Mesma resposta de "nao existe": nao confirmar a existencia de edicoes
        # de outras cidades.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    return edicao


@router.get("", response_model=list[EdicaoOut])
def listar(db: BD, ctx: Contexto):
    consulta = (
        select(Edicao)
        .options(joinedload(Edicao.cidade))
        .order_by(Edicao.ano.desc(), Edicao.nome)
    )

    if not ctx.admin_geral:
        if not ctx.edicoes:
            return []
        consulta = consulta.where(Edicao.id.in_(ctx.edicoes))

    return [_saida(e) for e in db.scalars(consulta).all()]


@router.post("", response_model=EdicaoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: EdicaoIn, db: BD, ctx: Admin):
    edicao = Edicao(**dados.model_dump())
    edicao.nome = edicao.nome.strip()
    db.add(edicao)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta cidade ja tem uma edicao com este nome neste ano. De outro nome a nova.",
        )

    herdados = coordenacao.povoar_edicao_nova(db, edicao)

    registrar(
        db, "edicao_criada", usuario_id=ctx.usuario.id,
        tabela="edicoes", registro_id=edicao.id,
        detalhes={
            "nome": edicao.nome,
            "ano": edicao.ano,
            **({"coordenacao_herdada": len(herdados)} if herdados else {}),
        },
    )
    db.commit()
    db.refresh(edicao)
    return _saida(edicao)


@router.patch("/{edicao_id}", response_model=EdicaoOut)
def editar(edicao_id: int, dados: EdicaoEditar, db: BD, ctx: Admin):
    edicao = _buscar_edicao(db, ctx, edicao_id)

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        setattr(edicao, campo, valor)

    # Edicao reaberta volta a ser uma edicao ativa da cidade, e a coordenacao
    # da cidade alcanca as edicoes ativas dela. Sem isto a edicao voltaria sem
    # coordenacao nenhuma.
    herdados = (
        coordenacao.povoar_edicao_nova(db, edicao)
        if mudancas.get("ativa") is True
        else []
    )

    registrar(
        db, "edicao_editada", usuario_id=ctx.usuario.id,
        tabela="edicoes", registro_id=edicao.id,
        detalhes={
            "campos": sorted(mudancas),
            **({"coordenacao_herdada": len(herdados)} if herdados else {}),
        },
    )
    db.commit()
    db.refresh(edicao)
    return _saida(edicao)


@router.put("/{edicao_id}/campanha-festa", response_model=EdicaoOut)
def campanha_da_festa(edicao_id: int, dados: CampanhaFestaIn, db: BD, ctx: Contexto):
    """Liga (ou desliga) o apadrinhamento da festa nesta edicao.

    So a administracao geral: e uma chave da edicao inteira, ligada uma vez,
    quase no fim da campanha da cesta. Desligar nao desfaz os apadrinhamentos
    de festa ja feitos; so impede os novos.
    """
    edicao = _buscar_edicao(db, ctx, edicao_id)
    if not ctx.admin_geral:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Quem liga a campanha da festa e a administracao geral.",
        )
    if dados.liberada and edicao.festa_liberada_em is None:
        edicao.festa_liberada_em, edicao.festa_liberada_por = datetime.now(UTC), ctx.usuario.id
    elif not dados.liberada:
        edicao.festa_liberada_em, edicao.festa_liberada_por = None, None
    registrar(
        db, "campanha_festa_liberada" if dados.liberada else "campanha_festa_suspensa",
        usuario_id=ctx.usuario.id, tabela="edicoes", registro_id=edicao.id,
    )
    db.commit()
    db.refresh(edicao)
    return _saida(edicao)


@router.get("/{edicao_id}/dependencias", response_model=DependenciasOut)
def dependencias(edicao_id: int, db: BD, ctx: Admin):
    """O que seria apagado junto com a edicao. A tela pergunta isto antes."""
    edicao = _buscar_edicao(db, ctx, edicao_id)
    return exclusao.resumir(
        db, edicao.id, edicao.nome, exclusao.alcance_da_edicao(edicao_id)
    )


@router.delete("/{edicao_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(
    edicao_id: int,
    db: BD,
    ctx: Admin,
    confirmar: Annotated[bool, Query()] = False,
    # A senha de quem apaga, de novo: ver seguranca/reconfirmar.py.
    senha: Annotated[str | None, Body(embed=True)] = None,
):
    """Apaga a edicao e o ano inteiro que esta dentro dela.

    As instituicoes da cidade NAO vao junto: o cadastro delas atravessa os
    anos. O que sai e o que era daquele ano — criancas, padrinhos, dias,
    compras e os acessos da equipe aquela edicao.

    `confirmar` existe para a exclusao nunca acontecer por engano fora da tela:
    com dados pendurados, o pedido sem confirmacao volta 409 com a conta de
    quantos sao.
    """
    edicao = _buscar_edicao(db, ctx, edicao_id)
    exigir_senha(db, ctx, senha, "apagar_edicao")

    # Lidos antes do DELETE: depois dele o objeto nao pode mais ser consultado.
    nome, ano, cidade_id = edicao.nome, edicao.ano, edicao.cidade_id

    resumo = exclusao.resumir(db, edicao_id, nome, exclusao.alcance_da_edicao(edicao_id))
    if resumo.total and not confirmar:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{nome} tem {resumo.total} registro(s) ligados a ela. "
            "Confirme a exclusao para apagar tudo junto.",
        )

    orfaos = exclusao.apagar_edicao(db, edicao_id)

    registrar(
        db, "edicao_apagada", usuario_id=ctx.usuario.id,
        tabela="edicoes", registro_id=edicao_id,
        detalhes={
            "nome": nome,
            "ano": ano,
            "cidade_id": cidade_id,
            "levou": {item.chave: item.quantidade for item in resumo.itens},
        },
    )
    db.commit()
    exclusao.remover_arquivos(orfaos)


# ---------------------------------------------------------------- dias

@router.get("/{edicao_id}/dias", response_model=list[DiaOut])
def listar_dias(edicao_id: int, db: BD, ctx: Contexto):
    _buscar_edicao(db, ctx, edicao_id)

    dias = db.scalars(
        select(DiaEvento)
        .where(DiaEvento.edicao_id == edicao_id)
        .order_by(DiaEvento.data)
    ).all()

    # Quantas criancas ja estao marcadas em cada dia.
    contagem = dict(
        db.execute(
            select(Crianca.dia_evento_id, func.count())
            .where(Crianca.edicao_id == edicao_id)
            .group_by(Crianca.dia_evento_id)
        ).all()
    )

    return [
        DiaOut(
            id=d.id,
            edicao_id=d.edicao_id,
            data=d.data,
            descricao=d.descricao,
            total_criancas=contagem.get(d.id, 0),
        )
        for d in dias
    ]


@router.post("/{edicao_id}/dias", response_model=DiaOut, status_code=status.HTTP_201_CREATED)
def criar_dia(
    edicao_id: int,
    dados: DiaIn,
    db: BD,
    ctx: Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_cadastros"))],
):
    _buscar_edicao(db, ctx, edicao_id)

    if not ctx.alcanca_edicao(edicao_id, "gerenciar_cadastros"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Voce nao gerencia os cadastros desta edicao."
        )

    ja_existe = db.scalar(
        select(DiaEvento).where(
            DiaEvento.edicao_id == edicao_id, DiaEvento.data == dados.data
        )
    )
    if ja_existe:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta edicao ja tem este dia.")

    dia = DiaEvento(edicao_id=edicao_id, **dados.model_dump())
    db.add(dia)
    db.flush()

    registrar(
        db, "dia_criado", usuario_id=ctx.usuario.id,
        tabela="dias_evento", registro_id=dia.id,
        detalhes={"edicao_id": edicao_id, "data": str(dia.data)},
    )
    db.commit()
    db.refresh(dia)
    return DiaOut(
        id=dia.id, edicao_id=dia.edicao_id, data=dia.data,
        descricao=dia.descricao, total_criancas=0,
    )


@router.put("/{edicao_id}/instituicoes/{instituicao_id}/dia", response_model=DiaDaInstituicaoOut)
def definir_dia_da_instituicao(
    edicao_id: int,
    instituicao_id: int,
    dados: DiaDaInstituicaoIn,
    db: BD,
    ctx: Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_cadastros"))],
):
    """Marca em que dia esta instituicao vai, e leva as criancas dela junto.

    O dia e da instituicao: se a Escolinha Sol vai no sabado, todas as criancas
    dela vao no sabado. Nao ha como marcar uma crianca num dia diferente.
    """
    _buscar_edicao(db, ctx, edicao_id)

    if not ctx.alcanca_edicao(edicao_id, "gerenciar_cadastros"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Voce nao gerencia os cadastros desta edicao."
        )

    instituicao = db.get(Instituicao, instituicao_id)
    if instituicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instituicao nao encontrada.")

    edicao = db.get(Edicao, edicao_id)
    if instituicao.cidade_id != edicao.cidade_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Esta instituicao nao e da cidade desta edicao.",
        )

    if dados.dia_evento_id is not None:
        dia = db.get(DiaEvento, dados.dia_evento_id)
        if dia is None or dia.edicao_id != edicao_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Este dia nao e desta edicao."
            )

    quantas = dias.definir(
        db, edicao_id, instituicao_id, dados.dia_evento_id, dados.onibus
    )
    # Lido depois de gravar: `definir` pode ter criado a ligacao agora, e
    # quando `onibus` vem omitido o numero certo e o que ja estava la.
    onibus = dias.onibus_da_instituicao(db, edicao_id, instituicao_id)

    registrar(
        db, "dia_da_instituicao", usuario_id=ctx.usuario.id,
        tabela="instituicao_dia",
        detalhes={
            "edicao_id": edicao_id,
            "instituicao_id": instituicao_id,
            "dia_evento_id": dados.dia_evento_id,
            "onibus": onibus,
            "criancas": quantas,
        },
    )
    db.commit()

    return DiaDaInstituicaoOut(
        instituicao_id=instituicao_id,
        instituicao=instituicao.nome,
        dia_evento_id=dados.dia_evento_id,
        onibus=onibus,
        criancas_atualizadas=quantas,
    )


PERFIL_MONITOR = "Monitoria"


def _instituicao_da_edicao(
    db: Session, ctx: ContextoAcesso, edicao_id: int, instituicao_id: int
) -> Instituicao:
    """A instituicao, conferindo que quem pede gerencia a edicao e que ela e da
    cidade da edicao."""
    edicao = _buscar_edicao(db, ctx, edicao_id)
    if not ctx.alcanca_edicao(edicao_id, "gerenciar_cadastros"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Voce nao gerencia os cadastros desta edicao."
        )
    instituicao = db.get(Instituicao, instituicao_id)
    if instituicao is None or instituicao.cidade_id != edicao.cidade_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instituicao nao encontrada.")
    return instituicao


def _atribuicoes_de_monitor(db: Session, edicao_id: int, instituicao_id: int):
    """(atribuicao, usuario) dos monitores ativos atribuidos a instituicao."""
    return db.execute(
        select(UsuarioInstituicao, Usuario)
        .join(UsuarioEdicao, UsuarioEdicao.id == UsuarioInstituicao.usuario_edicao_id)
        .join(Usuario, Usuario.id == UsuarioEdicao.usuario_id)
        .join(Perfil, Perfil.id == UsuarioEdicao.perfil_id)
        .where(
            UsuarioEdicao.edicao_id == edicao_id,
            UsuarioEdicao.ativo.is_(True),
            Usuario.ativo.is_(True),
            UsuarioInstituicao.instituicao_id == instituicao_id,
            Perfil.nome.startswith(PERFIL_MONITOR),
        )
        .order_by(Usuario.nome)
    ).all()


@router.get(
    "/{edicao_id}/instituicoes/{instituicao_id}/monitores",
    response_model=list[MonitorDaInstituicao],
)
def monitores_da_instituicao(
    edicao_id: int,
    instituicao_id: int,
    db: BD,
    ctx: Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_cadastros"))],
):
    """Os monitores atribuidos a instituicao nesta edicao: as opcoes do monitor
    responsavel. Vazia enquanto ninguem da monitoria foi atribuido a ela."""
    _instituicao_da_edicao(db, ctx, edicao_id, instituicao_id)
    return [
        MonitorDaInstituicao(
            usuario_id=u.id, nome=u.nome, whatsapp=u.whatsapp, responsavel=a.responsavel
        )
        for a, u in _atribuicoes_de_monitor(db, edicao_id, instituicao_id)
    ]


@router.put(
    "/{edicao_id}/instituicoes/{instituicao_id}/monitor-responsavel",
    response_model=list[MonitorDaInstituicao],
)
def definir_monitor_responsavel(
    edicao_id: int,
    instituicao_id: int,
    dados: MonitorResponsavelIn,
    db: BD,
    ctx: Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_cadastros"))],
):
    """Escolhe, entre os monitores atribuidos, o responsavel pela instituicao.

    So um por instituicao: marcar um desmarca os outros. Quem nao esta
    atribuido a ela nao pode ser escolhido — a responsabilidade e de quem ja
    responde pela instituicao na monitoria.
    """
    _instituicao_da_edicao(db, ctx, edicao_id, instituicao_id)
    atribuicoes = _atribuicoes_de_monitor(db, edicao_id, instituicao_id)

    if dados.usuario_id is not None and not any(
        u.id == dados.usuario_id for _, u in atribuicoes
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Esta pessoa nao e monitora desta instituicao nesta edicao.",
        )

    antes = next((u.id for a, u in atribuicoes if a.responsavel), None)
    for a, u in atribuicoes:
        a.responsavel = u.id == dados.usuario_id

    registrar(
        db, "monitor_responsavel", usuario_id=ctx.usuario.id,
        tabela="usuario_instituicao",
        detalhes={
            "edicao_id": edicao_id,
            "instituicao_id": instituicao_id,
            "antes": antes,
            "depois": dados.usuario_id,
        },
    )
    db.commit()
    return [
        MonitorDaInstituicao(
            usuario_id=u.id, nome=u.nome, whatsapp=u.whatsapp, responsavel=a.responsavel
        )
        for a, u in atribuicoes
    ]


@router.delete("/{edicao_id}/dias/{dia_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_dia(
    edicao_id: int,
    dia_id: int,
    db: BD,
    ctx: Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_cadastros"))],
):
    _buscar_edicao(db, ctx, edicao_id)

    if not ctx.alcanca_edicao(edicao_id, "gerenciar_cadastros"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Voce nao gerencia os cadastros desta edicao."
        )

    dia = db.get(DiaEvento, dia_id)
    if dia is None or dia.edicao_id != edicao_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dia nao encontrado.")

    marcadas = db.scalar(
        select(func.count()).select_from(Crianca).where(Crianca.dia_evento_id == dia_id)
    )
    if marcadas:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Este dia tem {marcadas} crianca(s) marcada(s). "
            "Mude as criancas de dia antes de apaga-lo.",
        )

    registrar(
        db, "dia_apagado", usuario_id=ctx.usuario.id,
        tabela="dias_evento", registro_id=dia_id,
        detalhes={"edicao_id": edicao_id, "data": str(dia.data)},
    )
    db.delete(dia)
    db.commit()
