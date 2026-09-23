"""Perfis, para preencher os formularios de vinculo."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Perfil
from app.schemas.cadastros import PerfilOut
from app.seguranca.dependencias import exige_permissao

router = APIRouter(prefix="/perfis", tags=["cadastros"])


@router.get("", response_model=list[PerfilOut])
def listar(
    db: Annotated[Session, Depends(get_db)],
    _ctx=Depends(exige_permissao("gerenciar_usuarios")),
):
    return db.scalars(select(Perfil).order_by(Perfil.nome)).all()
