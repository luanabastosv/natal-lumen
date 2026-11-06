"""A intercessao: a equipe que reza marca nas criancas as vivencias oferecidas
por elas, e o painel soma tudo como a planilha manual somava."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AveMaria, Crianca, Edicao, Intercessao
from app.models.tipos import TipoIntercessao
from app.schemas.intercessao import MarcaIntercessao, PainelIntercessao
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos.intercessao import CRIANCAS_POR_VIVENCIA, marcas

router = APIRouter(prefix="/intercessao", tags=["intercessao"])

BD = Annotated[Session, Depends(get_db)]
Interceder = Annotated[ContextoAcesso, Depends(exige_permissao("interceder"))]
VerPainel = Annotated[ContextoAcesso, Depends(exige_permissao("ver_painel_intercessao"))]


def _crianca(db: Session, ctx: ContextoAcesso, crianca_id: int) -> Crianca:
    """A crianca, se quem pede pode marcar intercessao nela. 404 nos dois
    casos, para nao dizer que a crianca existe a quem nao a alcanca."""
    crianca = db.scalar(
        select(Crianca).where(Crianca.id == crianca_id, ctx.filtro_criancas("interceder"))
    )
    if crianca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")
    return crianca


def _da_crianca(db: Session, crianca_id: int) -> list[MarcaIntercessao]:
    return [MarcaIntercessao(**m) for m in marcas(db, [crianca_id]).get(crianca_id, [])]


@router.post("/{crianca_id}/{tipo}", response_model=list[MarcaIntercessao])
def marcar(crianca_id: int, tipo: TipoIntercessao, db: BD, ctx: Interceder):
    """Marca a vivencia na crianca, em nome de quem esta na sessao.

    Marcar de novo nao duplica: ON CONFLICT, para duas abas abertas (ou um
    duplo clique) nao darem erro. Devolve as marcacoes da crianca ja em dia.
    """
    crianca = _crianca(db, ctx, crianca_id)
    db.execute(
        insert(Intercessao)
        .values(crianca_id=crianca.id, usuario_id=ctx.usuario.id, tipo=tipo.value)
        .on_conflict_do_nothing(constraint="uq_intercessoes_crianca_usuario_tipo")
    )
    db.commit()
    return _da_crianca(db, crianca.id)


@router.delete("/{crianca_id}/{tipo}", response_model=list[MarcaIntercessao])
def desmarcar(crianca_id: int, tipo: TipoIntercessao, db: BD, ctx: Interceder):
    """Tira a marcacao DESTA pessoa. A dos outros nao se mexe daqui: cada um
    responde pelo que rezou."""
    crianca = _crianca(db, ctx, crianca_id)
    db.execute(
        delete(Intercessao).where(
            Intercessao.crianca_id == crianca.id,
            Intercessao.usuario_id == ctx.usuario.id,
            Intercessao.tipo == tipo.value,
        )
    )
    db.commit()
    return _da_crianca(db, crianca.id)


@router.get("/painel/{edicao_id}", response_model=PainelIntercessao)
def painel(edicao_id: int, db: BD, ctx: VerPainel):
    edicao = db.get(Edicao, edicao_id)
    if edicao is None or not ctx.alcanca_edicao(edicao_id, "ver_painel_intercessao"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    da_edicao = select(Crianca.id).where(Crianca.edicao_id == edicao_id)
    # Quem desistiu nao vai ao evento, e sai da conta do que falta — como no
    # convite de oracao. O que ja foi rezado por ela continua contado.
    vem = da_edicao.where(Crianca.desistiu_em.is_(None))

    criancas = db.scalar(select(func.count()).select_from(vem.subquery())) or 0
    receberam = db.scalar(
        select(func.count(func.distinct(Intercessao.crianca_id))).where(
            Intercessao.crianca_id.in_(vem)
        )
    ) or 0
    por_tipo = dict(
        db.execute(
            select(Intercessao.tipo, func.count())
            .where(Intercessao.crianca_id.in_(da_edicao))
            .group_by(Intercessao.tipo)
        ).all()
    )
    ave_marias = db.scalar(
        select(func.count()).select_from(AveMaria).where(AveMaria.crianca_id.in_(da_edicao))
    ) or 0

    def vivencias(tipo: TipoIntercessao) -> float:
        return round(por_tipo.get(tipo.value, 0) / CRIANCAS_POR_VIVENCIA[tipo.value], 1)

    return PainelIntercessao(
        edicao=edicao.nome,
        criancas=criancas,
        receberam=receberam,
        faltam=criancas - receberam,
        marcacoes_missa=por_tipo.get(TipoIntercessao.MISSA.value, 0),
        marcacoes_adoracao=por_tipo.get(TipoIntercessao.ADORACAO.value, 0),
        marcacoes_terco=por_tipo.get(TipoIntercessao.TERCO.value, 0),
        marcacoes_jejum=por_tipo.get(TipoIntercessao.JEJUM.value, 0),
        missas=vivencias(TipoIntercessao.MISSA),
        adoracoes=vivencias(TipoIntercessao.ADORACAO),
        tercos=vivencias(TipoIntercessao.TERCO),
        jejuns=vivencias(TipoIntercessao.JEJUM),
        ave_marias=ave_marias,
    )
