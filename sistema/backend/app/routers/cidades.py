"""Cidades. So a administracao geral cria e edita."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cidade, Edicao
from app.schemas.cadastros import CidadeIn, CidadeOut
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import Contexto, exige_admin_geral
from app.servicos.log import registrar

router = APIRouter(prefix="/cidades", tags=["cadastros"])

BD = Annotated[Session, Depends(get_db)]
Admin = Annotated[ContextoAcesso, Depends(exige_admin_geral)]


@router.get("", response_model=list[CidadeOut])
def listar(db: BD, ctx: Contexto):
    """Admin ve todas; os demais, so as cidades das edicoes que alcancam."""
    consulta = select(Cidade).order_by(Cidade.nome)

    if not ctx.admin_geral:
        if not ctx.edicoes:
            return []
        consulta = consulta.where(
            Cidade.id.in_(select(Edicao.cidade_id).where(Edicao.id.in_(ctx.edicoes)))
        )

    return db.scalars(consulta).all()


@router.post("", response_model=CidadeOut, status_code=status.HTTP_201_CREATED)
def criar(dados: CidadeIn, db: BD, ctx: Admin):
    cidade = Cidade(nome=dados.nome.strip(), uf=dados.uf.upper(), ativo=dados.ativo)
    db.add(cidade)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ja existe uma cidade com este nome nesta UF."
        )

    registrar(
        db, "cidade_criada", usuario_id=ctx.usuario.id,
        tabela="cidades", registro_id=cidade.id,
        detalhes={"nome": cidade.nome, "uf": cidade.uf},
    )
    db.commit()
    db.refresh(cidade)
    return cidade


@router.patch("/{cidade_id}", response_model=CidadeOut)
def editar(cidade_id: int, dados: CidadeIn, db: BD, ctx: Admin):
    cidade = db.get(Cidade, cidade_id)
    if cidade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cidade nao encontrada.")

    cidade.nome = dados.nome.strip()
    cidade.uf = dados.uf.upper()
    cidade.ativo = dados.ativo

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ja existe uma cidade com este nome nesta UF."
        )

    registrar(
        db, "cidade_editada", usuario_id=ctx.usuario.id,
        tabela="cidades", registro_id=cidade.id,
    )
    db.commit()
    db.refresh(cidade)
    return cidade
