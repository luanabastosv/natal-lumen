"""Instituicoes. Pertencem a uma cidade e persistem entre anos."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Cidade, Crianca, DiaEvento, Edicao, Instituicao, InstituicaoDia
from app.schemas.cadastros import InstituicaoEditar, InstituicaoIn, InstituicaoOut
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import Contexto, exige_permissao
from app.servicos import codigos
from app.servicos.log import registrar

router = APIRouter(prefix="/instituicoes", tags=["cadastros"])

BD = Annotated[Session, Depends(get_db)]
Cadastros = Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_cadastros"))]


def _saida(inst: Instituicao, extra: dict | None = None) -> InstituicaoOut:
    extra = extra or {}
    return InstituicaoOut(
        id=inst.id,
        cidade_id=inst.cidade_id,
        cidade=inst.cidade.nome,
        nome=inst.nome,
        sigla=inst.sigla,
        responsavel=inst.responsavel,
        telefone=inst.telefone,
        endereco=inst.endereco,
        ativo=inst.ativo,
        dia_evento_id=extra.get("dia_evento_id"),
        dia_evento=extra.get("dia_evento"),
        criancas=extra.get("criancas", 0),
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
def listar(
    db: BD,
    ctx: Contexto,
    cidade_id: int | None = None,
    edicao_id: int | None = None,
):
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

    if edicao_id is not None:
        # Com uma edicao escolhida, so as instituicoes da cidade dela fazem
        # sentido: as outras nao podem ter dia nesta edicao, e mostra-las so
        # levaria a um erro na cara do usuario.
        edicao = db.get(Edicao, edicao_id)
        if edicao is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")
        consulta = consulta.where(Instituicao.cidade_id == edicao.cidade_id)

    instituicoes = db.scalars(consulta).all()

    # Com uma edicao escolhida, a listagem traz o dia marcado e quantas
    # criancas ha nela — e o que a tela de cadastro precisa mostrar.
    extras: dict[int, dict] = {}
    if edicao_id is not None:
        for inst_id, dia_id, data in db.execute(
            select(InstituicaoDia.instituicao_id, InstituicaoDia.dia_evento_id, DiaEvento.data)
            .join(DiaEvento, DiaEvento.id == InstituicaoDia.dia_evento_id)
            .where(InstituicaoDia.edicao_id == edicao_id)
        ).all():
            extras.setdefault(inst_id, {})["dia_evento_id"] = dia_id
            extras[inst_id]["dia_evento"] = data

        for inst_id, quantas in db.execute(
            select(Crianca.instituicao_id, func.count())
            .where(Crianca.edicao_id == edicao_id)
            .group_by(Crianca.instituicao_id)
        ).all():
            extras.setdefault(inst_id, {})["criancas"] = quantas

    return [_saida(i, extras.get(i.id)) for i in instituicoes]


@router.post("", response_model=InstituicaoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: InstituicaoIn, db: BD, ctx: Cadastros):
    if db.get(Cidade, dados.cidade_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cidade nao encontrada.")

    _conferir_cidade(db, ctx, dados.cidade_id)

    inst = Instituicao(**dados.model_dump())
    inst.nome = inst.nome.strip()

    if inst.sigla:
        inst.sigla = inst.sigla.strip().upper()
    else:
        # Sugerida a partir do nome, evitando as que a cidade ja usa.
        usadas = set(
            db.scalars(
                select(Instituicao.sigla).where(
                    Instituicao.cidade_id == inst.cidade_id,
                    Instituicao.sigla.is_not(None),
                )
            ).all()
        )
        inst.sigla = codigos.sugerir_sigla(inst.nome, usadas)

    db.add(inst)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta cidade ja tem uma instituicao com este nome ou com esta sigla.",
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
        if campo == "nome" and valor:
            valor = valor.strip()
        if campo == "sigla" and valor:
            valor = valor.strip().upper()
        setattr(inst, campo, valor)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta cidade ja tem uma instituicao com este nome ou com esta sigla.",
        )

    registrar(
        db, "instituicao_editada", usuario_id=ctx.usuario.id,
        tabela="instituicoes", registro_id=inst.id,
        detalhes={"campos": sorted(mudancas)},
    )
    db.commit()
    db.refresh(inst)
    return _saida(inst)
