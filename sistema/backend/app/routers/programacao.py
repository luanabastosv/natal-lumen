"""A programacao do dia do evento de cada edicao.

Quem monta e a coordenacao geral do evento (e a administracao geral): o
quadro de horarios e o dos rodizios de cada nucleo, todo ano, ajustado ate o
dia. Quando ela marca a programacao como concluida, a equipe inteira da
edicao passa a ver e imprimir — antes disso, so a coordenacao.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DiaEvento, Edicao, Instituicao, InstituicaoDia, Programacao, Usuario
from app.schemas.programacao import (
    ConclusaoIn,
    InstituicaoNoNucleo,
    NucleosDoDia,
    ProgramacaoIn,
    ProgramacaoOut,
    ProgramacaoSalvar,
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


def _nome(db: Session, usuario_id: int | None) -> str | None:
    u = db.get(Usuario, usuario_id) if usuario_id else None
    return u.nome if u else None


def _saida(db: Session, edicao_id: int, p: Programacao | None, coordena: bool) -> ProgramacaoOut:
    # Para quem nao coordena, a programacao em montagem "nao existe": a tela
    # diz que ainda nao foi liberada, e nada do rascunho sai do servidor.
    if p is None or (not coordena and p.concluida_em is None):
        return ProgramacaoOut(existe=False, pode_editar=coordena)
    return ProgramacaoOut(
        **p.dados, existe=True,
        atualizado_em=p.atualizado_em, atualizado_por=_nome(db, p.atualizado_por),
        concluida_em=p.concluida_em, concluida_por=_nome(db, p.concluida_por),
        pode_editar=coordena, nucleos=_nucleos(db, edicao_id),
    )


def _da_edicao(ctx: ContextoAcesso, edicao_id: int) -> None:
    """Qualquer perfil da edicao ve a programacao (depois de concluida)."""
    if not (ctx.admin_geral or edicao_id in ctx.edicoes):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem acesso a esta edicao.")


def _buscar(db: Session, edicao_id: int) -> Programacao | None:
    return db.scalar(select(Programacao).where(Programacao.edicao_id == edicao_id))


@router.get("/{edicao_id}", response_model=ProgramacaoOut)
def ver(edicao_id: int, db: BD, ctx: Logado):
    _da_edicao(ctx, edicao_id)
    if db.get(Edicao, edicao_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")
    return _saida(db, edicao_id, _buscar(db, edicao_id), ctx.e_coordenacao_geral(edicao_id))


@router.put("/{edicao_id}", response_model=ProgramacaoOut)
def salvar(edicao_id: int, dados: ProgramacaoSalvar, db: BD, ctx: Logado):
    _so_coordenacao(ctx, edicao_id)
    if db.get(Edicao, edicao_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    p = _buscar(db, edicao_id)
    if "versao_lida" in dados.model_fields_set:
        salvo = p.atualizado_em if p is not None else None
        if salvo != dados.versao_lida:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Outra pessoa salvou a programacao enquanto voce editava. Copie o "
                "que mudou, cancele a edicao e abra de novo para ver o que esta salvo.",
            )
    if p is None:
        p = Programacao(edicao_id=edicao_id, dados={})
        db.add(p)
    p.dados = ProgramacaoIn(**dados.model_dump(exclude={"versao_lida"})).model_dump()
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
    return _saida(db, edicao_id, p, True)


@router.put("/{edicao_id}/conclusao", response_model=ProgramacaoOut)
def concluir(edicao_id: int, dados: ConclusaoIn, db: BD, ctx: Logado):
    """Marca a programacao como concluida (liberada para a equipe) ou volta
    atras. Editar depois de concluida continua valendo: a equipe ve o que
    estiver salvo."""
    _so_coordenacao(ctx, edicao_id)
    p = _buscar(db, edicao_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Salve a programacao antes de concluir.")
    if dados.concluida:
        p.concluida_em, p.concluida_por = datetime.now(UTC), ctx.usuario.id
    else:
        p.concluida_em, p.concluida_por = None, None
    registrar(
        db, "programacao_concluida" if dados.concluida else "programacao_reaberta",
        usuario_id=ctx.usuario.id, tabela="programacoes", registro_id=p.id,
        detalhes={"edicao_id": edicao_id},
    )
    db.commit()
    db.refresh(p)
    return _saida(db, edicao_id, p, True)
