"""Painel da edicao: o apadrinhamento de cesta e de festa, e quem falta.

Todos os numeros passam pelo mesmo filtro das telas: quem so alcanca algumas
instituicoes ve os numeros dessas instituicoes, e nao da edicao inteira.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Apadrinhamento,
    Crianca,
    Edicao,
    Grupo,
    Instituicao,
    Perfil,
    Usuario,
    UsuarioEdicao,
)
from app.models.tipos import TipoApadrinhamento
from app.schemas.painel import (
    LinhaComissario,
    LinhaInstituicao,
    Relatorio,
    ResumoEdicao,
)
from app.seeds.perfis_permissoes import PERFIL_COMISSARIO
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao

router = APIRouter(prefix="/painel", tags=["painel"])

BD = Annotated[Session, Depends(get_db)]
Painel = Annotated[ContextoAcesso, Depends(exige_permissao("ver_painel"))]

CESTA = TipoApadrinhamento.CESTA.value
FESTA = TipoApadrinhamento.FESTA.value

SEM_COMISSARIO = "Sem comissário"


@router.get("/{edicao_id}", response_model=Relatorio)
def relatorio(edicao_id: int, db: BD, ctx: Painel):
    edicao = db.scalar(
        select(Edicao).where(Edicao.id == edicao_id).options(joinedload(Edicao.cidade))
    )
    if edicao is None or not ctx.alcanca_edicao(edicao_id, "ver_painel"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    # Mesmo filtro das telas: quem so alcanca algumas instituicoes ve os
    # numeros dessas instituicoes.
    alcance = ctx.filtro_criancas("ver_painel") & (Crianca.edicao_id == edicao_id)
    criancas_visiveis = select(Crianca.id).where(alcance)

    criancas = db.scalar(select(func.count()).select_from(Crianca).where(alcance)) or 0
    instituicoes = db.scalar(
        select(func.count(func.distinct(Crianca.instituicao_id))).where(alcance)
    ) or 0

    por_tipo = dict(
        db.execute(
            select(Apadrinhamento.tipo, func.count())
            .where(Apadrinhamento.crianca_id.in_(criancas_visiveis))
            .group_by(Apadrinhamento.tipo)
        ).all()
    )

    resumo = ResumoEdicao(
        edicao_id=edicao.id,
        edicao=edicao.nome,
        cidade=edicao.cidade.nome,
        ano=edicao.ano,
        criancas=criancas,
        instituicoes=instituicoes,
        cesta_feitos=por_tipo.get(CESTA, 0),
        festa_feitos=por_tipo.get(FESTA, 0),
    )

    return Relatorio(
        resumo=resumo,
        por_instituicao=_por_instituicao(db, alcance),
        por_comissario=_por_comissario(db, alcance, criancas_visiveis, edicao_id),
    )


def _por_instituicao(db: Session, alcance) -> list[LinhaInstituicao]:
    """Quantas criancas a instituicao tem, e quanto ja esta apadrinhado.

    A unicidade de (crianca, tipo) nos apadrinhamentos e o que deixa contar por
    um LEFT JOIN direto: cada crianca traz no maximo duas linhas, uma de cada
    tipo, entao nao ha o que se multiplicar.
    """
    linhas = db.execute(
        select(
            Crianca.instituicao_id,
            Instituicao.nome,
            func.count(func.distinct(Crianca.id)),
            func.count(func.distinct(case((Apadrinhamento.tipo == CESTA, Crianca.id)))),
            func.count(func.distinct(case((Apadrinhamento.tipo == FESTA, Crianca.id)))),
        )
        .join(Instituicao, Instituicao.id == Crianca.instituicao_id)
        .outerjoin(Apadrinhamento, Apadrinhamento.crianca_id == Crianca.id)
        .where(alcance)
        .group_by(Crianca.instituicao_id, Instituicao.nome)
        .order_by(Instituicao.nome)
    ).all()

    return [
        LinhaInstituicao(
            instituicao_id=i, instituicao=nome, criancas=c, cesta=cesta, festa=festa
        )
        for i, nome, c, cesta, festa in linhas
    ]


def _por_comissario(db: Session, alcance, criancas_visiveis, edicao_id: int):
    """Cada comissario, o grupo dele, e o que falta no time dele.

    A lista comeca pelo time da edicao, e nao pelas criancas ja atribuidas: um
    comissario sem nenhuma crianca na mao e justamente o que a coordenacao
    precisa enxergar, e ele nao apareceria se a contagem mandasse.
    """
    # Cesta e festa por crianca, para saber quais estao completas.
    tipos = (
        select(
            Apadrinhamento.crianca_id.label("crianca_id"),
            func.count(case((Apadrinhamento.tipo == CESTA, 1))).label("cesta"),
            func.count(case((Apadrinhamento.tipo == FESTA, 1))).label("festa"),
        )
        .where(Apadrinhamento.crianca_id.in_(criancas_visiveis))
        .group_by(Apadrinhamento.crianca_id)
        .subquery()
    )

    contagens = {
        responsavel: (total, cesta, festa, completas)
        for responsavel, total, cesta, festa, completas in db.execute(
            select(
                Crianca.comissario_id,
                func.count(Crianca.id),
                func.coalesce(func.sum(tipos.c.cesta), 0),
                func.coalesce(func.sum(tipos.c.festa), 0),
                func.count(
                    case(((tipos.c.cesta > 0) & (tipos.c.festa > 0), Crianca.id))
                ),
            )
            .outerjoin(tipos, tipos.c.crianca_id == Crianca.id)
            .where(alcance)
            .group_by(Crianca.comissario_id)
        ).all()
    }

    # O time da edicao. Coordenacao e administracao geral tambem podem assumir
    # criancas; elas entram na lista se tiverem alguma, mas sem grupo, porque
    # grupo e coisa de comissario.
    time = db.execute(
        select(Usuario.id, Usuario.nome, Grupo.nome, Perfil.nome)
        .join(UsuarioEdicao, UsuarioEdicao.usuario_id == Usuario.id)
        .join(Perfil, Perfil.id == UsuarioEdicao.perfil_id)
        .outerjoin(Grupo, Grupo.id == UsuarioEdicao.grupo_id)
        .where(UsuarioEdicao.edicao_id == edicao_id, UsuarioEdicao.ativo.is_(True))
    ).all()
    membros = {i: (nome, grupo, perfil) for i, nome, grupo, perfil in time}

    responsaveis = {
        i for i, (_, _, perfil) in membros.items() if perfil == PERFIL_COMISSARIO
    }
    responsaveis |= {i for i in contagens if i is not None}

    # Quem assumiu crianca mas nao tem vinculo ativo nesta edicao (saiu do time
    # depois de atribuido) continua aparecendo: as criancas dele existem.
    faltando = [i for i in responsaveis if i not in membros]
    if faltando:
        for i, nome in db.execute(
            select(Usuario.id, Usuario.nome).where(Usuario.id.in_(faltando))
        ).all():
            membros[i] = (nome, None, None)

    linhas = []
    for i in responsaveis:
        nome, grupo, perfil = membros.get(i, (f"Usuário {i}", None, None))
        total, cesta, festa, completas = contagens.get(i, (0, 0, 0, 0))
        # So comissario tem grupo; o resto do time aparece sem.
        linhas.append(
            LinhaComissario(
                comissario_id=i, comissario=nome,
                grupo=grupo if perfil == PERFIL_COMISSARIO else None,
                criancas=total, cesta=cesta, festa=festa,
                completas=completas, faltam=total - completas,
            )
        )

    # Sem grupo vai para o fim de cada bloco, e o nome ordena dentro do grupo.
    linhas.sort(key=lambda l: (l.grupo is None, l.grupo or "", l.comissario))

    if None in contagens:
        total, cesta, festa, completas = contagens[None]
        linhas.append(
            LinhaComissario(
                comissario_id=None, comissario=SEM_COMISSARIO, grupo=None,
                criancas=total, cesta=cesta, festa=festa,
                completas=completas, faltam=total - completas,
            )
        )

    return linhas
