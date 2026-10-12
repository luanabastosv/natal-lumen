"""A programacao do dia do evento de cada edicao.

So a coordenacao geral do evento e a administracao geral: e ela que monta o
quadro de horarios e o dos rodizios de cada nucleo, todo ano, e o ajusta ate o
dia.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DiaEvento, Edicao, Instituicao, InstituicaoDia, Programacao, Usuario
from app.schemas.programacao import (
    InstituicaoNoNucleo,
    NucleosDoDia,
    ProgramacaoIn,
    ProgramacaoOut,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import contexto_atual
from app.servicos.log import registrar

router = APIRouter(prefix="/programacao", tags=["programacao"])

BD = Annotated[Session, Depends(get_db)]
Logado = Annotated[ContextoAcesso, Depends(contexto_atual)]


def _so_coordenacao(ctx: ContextoAcesso, edicao_id: int) -> None:
    if not ctx.e_coordenacao_geral(edicao_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "A programacao e da coordenacao geral do evento."
        )


def _nucleos(db: Session, edicao_id: int) -> list[NucleosDoDia]:
    dias = db.scalars(
        select(DiaEvento).where(DiaEvento.edicao_id == edicao_id).order_by(DiaEvento.data)
    ).all()
    linhas = db.execute(
        select(InstituicaoDia, Instituicao)
        .join(Instituicao, Instituicao.id == InstituicaoDia.instituicao_id)
        .where(InstituicaoDia.edicao_id == edicao_id)
        .order_by(InstituicaoDia.nucleo, Instituicao.nome)
    ).all()
    return [
        NucleosDoDia(
            dia_evento_id=d.id, data=d.data, descricao=d.descricao,
            instituicoes=[
                InstituicaoNoNucleo(
                    nome=i.nome, sigla=i.sigla, nucleo=idia.nucleo,
                    cor_bata_nome=idia.cor_bata_nome, cor_bata_hex=idia.cor_bata_hex,
                )
                for idia, i in linhas
                if idia.dia_evento_id == d.id
            ],
        )
        for d in dias
    ]


def _saida(db: Session, edicao_id: int, p: Programacao | None) -> ProgramacaoOut:
    nucleos = _nucleos(db, edicao_id)
    if p is None:
        return ProgramacaoOut(existe=False, nucleos=nucleos)
    quem = db.get(Usuario, p.atualizado_por) if p.atualizado_por else None
    return ProgramacaoOut(
        **p.dados, existe=True, atualizado_em=p.atualizado_em,
        atualizado_por=quem.nome if quem else None, nucleos=nucleos,
    )


@router.get("/{edicao_id}", response_model=ProgramacaoOut)
def ver(edicao_id: int, db: BD, ctx: Logado):
    _so_coordenacao(ctx, edicao_id)
    if db.get(Edicao, edicao_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")
    return _saida(db, edicao_id, db.scalar(select(Programacao).where(Programacao.edicao_id == edicao_id)))


@router.put("/{edicao_id}", response_model=ProgramacaoOut)
def salvar(edicao_id: int, dados: ProgramacaoIn, db: BD, ctx: Logado):
    _so_coordenacao(ctx, edicao_id)
    if db.get(Edicao, edicao_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    p = db.scalar(select(Programacao).where(Programacao.edicao_id == edicao_id))
    if p is None:
        p = Programacao(edicao_id=edicao_id, dados={})
        db.add(p)
    p.dados = dados.model_dump()
    p.atualizado_em = datetime.now(UTC)
    p.atualizado_por = ctx.usuario.id
    db.flush()
    registrar(
        db, "programacao_salva", usuario_id=ctx.usuario.id,
        tabela="programacoes", registro_id=p.id,
        detalhes={
            "edicao_id": edicao_id,
            "blocos": len(dados.blocos),
            "horarios": sum(len(b.horarios) for b in dados.blocos),
        },
    )
    db.commit()
    db.refresh(p)
    return _saida(db, edicao_id, p)
