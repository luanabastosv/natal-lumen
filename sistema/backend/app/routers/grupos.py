"""Grupos da comunidade ja usados na cidade — a lista de sugestoes do formulario.

Nao ha rota de criar: o grupo nasce junto com o vinculo do comissario, em
/usuarios. O que existe aqui e a leitura, para a tela poder sugerir o que ja
foi escrito antes em vez de deixar cada coordenador inventar sua grafia.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Edicao, Grupo
from app.schemas.cadastros import GrupoOut
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao

router = APIRouter(prefix="/grupos", tags=["cadastros"])

BD = Annotated[Session, Depends(get_db)]
Gestor = Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_usuarios"))]


@router.get("", response_model=list[GrupoOut])
def listar(
    db: BD,
    ctx: Gestor,
    cidade_id: int | None = None,
    edicao_id: int | None = None,
):
    """Os grupos das cidades que o gestor alcanca.

    A cidade pode vir pela edicao escolhida na lateral: o grupo e da cidade, e
    e assim que ele atravessa os anos — a edicao de 2027 abre sugerindo os
    grupos que 2026 cadastrou.
    """
    consulta = select(Grupo).order_by(Grupo.nome)

    if not ctx.admin_geral:
        edicoes = ctx.edicoes_com("gerenciar_usuarios")
        if not edicoes:
            return []
        consulta = consulta.where(
            Grupo.cidade_id.in_(select(Edicao.cidade_id).where(Edicao.id.in_(edicoes)))
        )

    if cidade_id is not None:
        consulta = consulta.where(Grupo.cidade_id == cidade_id)

    if edicao_id is not None:
        edicao = db.get(Edicao, edicao_id)
        if edicao is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")
        consulta = consulta.where(Grupo.cidade_id == edicao.cidade_id)

    return db.scalars(consulta).all()
