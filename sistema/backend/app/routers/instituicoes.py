"""Instituicoes. Pertencem a uma cidade e persistem entre anos."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Cidade, Edicao, Instituicao
from app.schemas.cadastros import InstituicaoEditar, InstituicaoIn, InstituicaoOut
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import Contexto, exige_permissao
from app.servicos.log import registrar

router = APIRouter(prefix="/instituicoes", tags=["cadastros"])

BD = Annotated[Session, Depends(get_db)]
Cadastros = Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_cadastros"))]


def _saida(inst: Instituicao) -> InstituicaoOut:
    return InstituicaoOut(
        id=inst.id,
        cidade_id=inst.cidade_id,
        cidade=inst.cidade.nome,
        nome=inst.nome,
        responsavel=inst.responsavel,
        telefone=inst.telefone,
        endereco=inst.endereco,
        ativo=inst.ativo,
    )


def _cidades_do_usuario(db: Session, ctx: ContextoAcesso) -> list[int]:
    """Cidades das edicoes que o usuario alcanca."""
    if not ctx.edicoes:
        return []
    return list(
        db.scalars(select(Edicao.cidade_id).where(Edicao.id.in_(ctx.edicoes))).all()
    )


def _conferir_cidade(db: Session, ctx: ContextoAcesso, cidade_id: int) -> None:
    if ctx.admin_geral:
        return
    if cidade_id not in _cidades_do_usuario(db, ctx):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Esta instituicao nao e de uma cidade sua."
        )


@router.get("", response_model=list[InstituicaoOut])
def listar(db: BD, ctx: Contexto, cidade_id: int | None = None):
    """Lista as instituicoes das cidades que o usuario alcanca.

    Nao filtra pelas instituicoes atribuidas em usuario_instituicao: o nome da
    instituicao nao e dado sensivel, e comissarios precisam ver a lista para
    entender de onde vem cada crianca. O filtro fino vale para as criancas.
    """
    consulta = (
        select(Instituicao)
        .options(joinedload(Instituicao.cidade))
        .order_by(Instituicao.nome)
    )

    if not ctx.admin_geral:
        cidades = _cidades_do_usuario(db, ctx)
        if not cidades:
            return []
        consulta = consulta.where(Instituicao.cidade_id.in_(cidades))

    if cidade_id is not None:
        consulta = consulta.where(Instituicao.cidade_id == cidade_id)

    return [_saida(i) for i in db.scalars(consulta).all()]


@router.post("", response_model=InstituicaoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: InstituicaoIn, db: BD, ctx: Cadastros):
    if db.get(Cidade, dados.cidade_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cidade nao encontrada.")

    _conferir_cidade(db, ctx, dados.cidade_id)

    inst = Instituicao(**dados.model_dump())
    inst.nome = inst.nome.strip()
    db.add(inst)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta cidade ja tem uma instituicao com este nome.",
        )

    registrar(
        db, "instituicao_criada", usuario_id=ctx.usuario.id,
        tabela="instituicoes", registro_id=inst.id,
        detalhes={"nome": inst.nome, "cidade_id": inst.cidade_id},
    )
    db.commit()
    db.refresh(inst)
    return _saida(inst)


@router.patch("/{instituicao_id}", response_model=InstituicaoOut)
def editar(instituicao_id: int, dados: InstituicaoEditar, db: BD, ctx: Cadastros):
    inst = db.get(Instituicao, instituicao_id)
    if inst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instituicao nao encontrada.")

    _conferir_cidade(db, ctx, inst.cidade_id)

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        setattr(inst, campo, valor.strip() if campo == "nome" and valor else valor)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta cidade ja tem uma instituicao com este nome.",
        )

    registrar(
        db, "instituicao_editada", usuario_id=ctx.usuario.id,
        tabela="instituicoes", registro_id=inst.id,
        detalhes={"campos": sorted(mudancas)},
    )
    db.commit()
    db.refresh(inst)
    return _saida(inst)
