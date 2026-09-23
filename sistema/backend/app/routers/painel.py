"""Painel e relatorios da edicao.

Todos os numeros passam pelo mesmo filtro das telas: quem so alcanca algumas
instituicoes ve os numeros dessas instituicoes, e nao da edicao inteira.
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Apadrinhamento,
    Cartao,
    Compra,
    Crianca,
    DiaEvento,
    Edicao,
    Instituicao,
    Kit,
    Padrinho,
)
from app.models.tipos import StatusCartao, StatusKit, TipoApadrinhamento
from app.schemas.painel import (
    LinhaDia,
    LinhaInstituicao,
    Relatorio,
    ResumoEdicao,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao

router = APIRouter(prefix="/painel", tags=["painel"])

BD = Annotated[Session, Depends(get_db)]
Painel = Annotated[ContextoAcesso, Depends(exige_permissao("ver_painel"))]

DOIS_DECIMAIS = Decimal("0.01")


def _dinheiro(valor) -> Decimal:
    return (valor or Decimal("0")).quantize(DOIS_DECIMAIS)


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

    # --- apadrinhamento ---
    por_tipo = dict(
        db.execute(
            select(Apadrinhamento.tipo, func.count())
            .where(Apadrinhamento.crianca_id.in_(criancas_visiveis))
            .group_by(Apadrinhamento.tipo)
        ).all()
    )
    cesta = por_tipo.get(TipoApadrinhamento.CESTA.value, 0)
    festa = por_tipo.get(TipoApadrinhamento.FESTA.value, 0)

    # Quantos tipos cada crianca ja tem: 0, 1 ou 2.
    tipos_por_crianca = (
        select(Apadrinhamento.crianca_id, func.count().label("quantos"))
        .where(Apadrinhamento.crianca_id.in_(criancas_visiveis))
        .group_by(Apadrinhamento.crianca_id)
        .subquery()
    )
    com_algum = db.scalar(select(func.count()).select_from(tipos_por_crianca)) or 0
    completas = db.scalar(
        select(func.count()).select_from(tipos_por_crianca).where(tipos_por_crianca.c.quantos >= 2)
    ) or 0

    valores = db.execute(
        select(
            func.coalesce(func.sum(Apadrinhamento.valor), 0),
            func.coalesce(
                func.sum(
                    case((Apadrinhamento.pagamento_id.is_not(None), Apadrinhamento.valor), else_=0)
                ),
                0,
            ),
        ).where(Apadrinhamento.crianca_id.in_(criancas_visiveis))
    ).one()

    padrinhos = db.scalar(
        select(func.count(func.distinct(Apadrinhamento.padrinho_id))).where(
            Apadrinhamento.crianca_id.in_(criancas_visiveis)
        )
    ) or 0
    # Padrinhos captados nesta edicao que ainda nao apadrinharam ninguem contam
    # tambem: sao trabalho ja feito pelo comissario.
    captados = db.scalar(
        select(func.count()).select_from(Padrinho).where(Padrinho.edicao_id == edicao_id)
    ) or 0

    # --- cartoes ---
    por_status = dict(
        db.execute(
            select(Cartao.status, func.count())
            .where(Cartao.crianca_id.in_(criancas_visiveis))
            .group_by(Cartao.status)
        ).all()
    )
    digitalizados = sum(por_status.values())
    enviados = por_status.get(StatusCartao.ENVIADO.value, 0)

    # --- kits ---
    kits = dict(
        db.execute(
            select(Kit.status, func.count())
            .where(Kit.crianca_id.in_(criancas_visiveis))
            .group_by(Kit.status)
        ).all()
    )
    montados = kits.get(StatusKit.MONTADO.value, 0)
    entregues = kits.get(StatusKit.ENTREGUE.value, 0)
    # Quem nao tem registro de kit tambem esta pendente.
    pendentes = criancas - montados - entregues

    compras = db.scalar(
        select(func.coalesce(func.sum(Compra.valor_total), 0)).where(Compra.edicao_id == edicao_id)
    )

    checkins = db.scalar(
        select(func.count()).select_from(Crianca).where(alcance, Crianca.checkin_em.is_not(None))
    ) or 0

    resumo = ResumoEdicao(
        edicao_id=edicao.id, edicao=edicao.nome, cidade=edicao.cidade.nome, ano=edicao.ano,
        criancas=criancas, instituicoes=instituicoes,
        apadrinhamentos_possiveis=criancas * 2,
        apadrinhamentos_feitos=cesta + festa,
        cesta_feitos=cesta, festa_feitos=festa,
        criancas_sem_nenhum_padrinho=criancas - com_algum,
        criancas_completas=completas,
        padrinhos=max(padrinhos, captados),
        valor_combinado=_dinheiro(valores[0]),
        valor_pago=_dinheiro(valores[1]),
        cartoes_possiveis=criancas * 2,
        cartoes_digitalizados=digitalizados,
        cartoes_enviados=enviados,
        kits_pendentes=max(pendentes, 0),
        kits_montados=montados,
        kits_entregues=entregues,
        compras_total=_dinheiro(compras),
        checkin_feitos=checkins,
    )

    # --- por instituicao ---
    linhas_inst = db.execute(
        select(
            Crianca.instituicao_id,
            Instituicao.nome,
            func.count(func.distinct(Crianca.id)),
            func.count(func.distinct(Apadrinhamento.crianca_id)),
            func.count(func.distinct(Cartao.id)),
            func.count(func.distinct(case((Kit.status == StatusKit.ENTREGUE.value, Kit.id)))),
            func.count(func.distinct(case((Crianca.checkin_em.is_not(None), Crianca.id)))),
        )
        .join(Instituicao, Instituicao.id == Crianca.instituicao_id)
        .outerjoin(Apadrinhamento, Apadrinhamento.crianca_id == Crianca.id)
        .outerjoin(Cartao, Cartao.crianca_id == Crianca.id)
        .outerjoin(Kit, Kit.crianca_id == Crianca.id)
        .where(alcance)
        .group_by(Crianca.instituicao_id, Instituicao.nome)
        .order_by(Instituicao.nome)
    ).all()

    # --- por dia ---
    linhas_dia = db.execute(
        select(
            Crianca.dia_evento_id,
            DiaEvento.data,
            DiaEvento.descricao,
            func.count(Crianca.id),
            func.count(case((Crianca.checkin_em.is_not(None), Crianca.id))),
        )
        .outerjoin(DiaEvento, DiaEvento.id == Crianca.dia_evento_id)
        .where(alcance)
        .group_by(Crianca.dia_evento_id, DiaEvento.data, DiaEvento.descricao)
        .order_by(DiaEvento.data.nulls_last())
    ).all()

    return Relatorio(
        resumo=resumo,
        por_instituicao=[
            LinhaInstituicao(
                instituicao_id=i, instituicao=nome, criancas=c,
                apadrinhados=a, cartoes=ca, kits_entregues=k, checkin=ch,
            )
            for i, nome, c, a, ca, k, ch in linhas_inst
        ],
        por_dia=[
            LinhaDia(
                dia_evento_id=i, data=d, descricao=desc, criancas=c, checkin=ch,
            )
            for i, d, desc, c, ch in linhas_dia
        ],
    )
