"""Edicoes e os dias de cada uma.

Edicao e criada so pela administracao geral. Os dias sao da coordenacao, que
tem gerenciar_cadastros.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Crianca, DiaEvento, Edicao, Instituicao
from app.schemas.cadastros import (
    DiaDaInstituicaoIn,
    DiaDaInstituicaoOut,
    DiaIn,
    DiaOut,
    EdicaoEditar,
    EdicaoIn,
    EdicaoOut,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import Contexto, exige_admin_geral, exige_permissao
from app.servicos import dias
from app.servicos.log import registrar

router = APIRouter(prefix="/edicoes", tags=["cadastros"])

BD = Annotated[Session, Depends(get_db)]
Admin = Annotated[ContextoAcesso, Depends(exige_admin_geral)]


def _saida(edicao: Edicao) -> EdicaoOut:
    return EdicaoOut(
        id=edicao.id,
        cidade_id=edicao.cidade_id,
        cidade=edicao.cidade.nome,
        uf=edicao.cidade.uf,
        ano=edicao.ano,
        nome=edicao.nome,
        valor_cesta=edicao.valor_cesta,
        valor_festa=edicao.valor_festa,
        ativa=edicao.ativa,
    )


def _buscar_edicao(db: Session, ctx: ContextoAcesso, edicao_id: int) -> Edicao:
    """Busca a edicao conferindo se o usuario a alcanca."""
    edicao = db.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    if not ctx.admin_geral and edicao_id not in ctx.edicoes:
        # Mesma resposta de "nao existe": nao confirmar a existencia de edicoes
        # de outras cidades.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    return edicao


@router.get("", response_model=list[EdicaoOut])
def listar(db: BD, ctx: Contexto):
    consulta = (
        select(Edicao)
        .options(joinedload(Edicao.cidade))
        .order_by(Edicao.ano.desc(), Edicao.nome)
    )

    if not ctx.admin_geral:
        if not ctx.edicoes:
            return []
        consulta = consulta.where(Edicao.id.in_(ctx.edicoes))

    return [_saida(e) for e in db.scalars(consulta).all()]


@router.post("", response_model=EdicaoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: EdicaoIn, db: BD, ctx: Admin):
    edicao = Edicao(**dados.model_dump())
    edicao.nome = edicao.nome.strip()
    db.add(edicao)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Esta cidade ja tem uma edicao neste ano."
        )

    registrar(
        db, "edicao_criada", usuario_id=ctx.usuario.id,
        tabela="edicoes", registro_id=edicao.id,
        detalhes={"nome": edicao.nome, "ano": edicao.ano},
    )
    db.commit()
    db.refresh(edicao)
    return _saida(edicao)


@router.patch("/{edicao_id}", response_model=EdicaoOut)
def editar(edicao_id: int, dados: EdicaoEditar, db: BD, ctx: Admin):
    edicao = db.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        setattr(edicao, campo, valor)

    registrar(
        db, "edicao_editada", usuario_id=ctx.usuario.id,
        tabela="edicoes", registro_id=edicao.id,
        detalhes={"campos": sorted(mudancas)},
    )
    db.commit()
    db.refresh(edicao)
    return _saida(edicao)


# ---------------------------------------------------------------- dias

@router.get("/{edicao_id}/dias", response_model=list[DiaOut])
def listar_dias(edicao_id: int, db: BD, ctx: Contexto):
    _buscar_edicao(db, ctx, edicao_id)

    dias = db.scalars(
        select(DiaEvento)
        .where(DiaEvento.edicao_id == edicao_id)
        .order_by(DiaEvento.data)
    ).all()

    # Quantas criancas ja estao marcadas em cada dia.
    contagem = dict(
        db.execute(
            select(Crianca.dia_evento_id, func.count())
            .where(Crianca.edicao_id == edicao_id)
            .group_by(Crianca.dia_evento_id)
        ).all()
    )

    return [
        DiaOut(
            id=d.id,
            edicao_id=d.edicao_id,
            data=d.data,
            descricao=d.descricao,
            total_criancas=contagem.get(d.id, 0),
        )
        for d in dias
    ]


@router.post("/{edicao_id}/dias", response_model=DiaOut, status_code=status.HTTP_201_CREATED)
def criar_dia(
    edicao_id: int,
    dados: DiaIn,
    db: BD,
    ctx: Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_cadastros"))],
):
    _buscar_edicao(db, ctx, edicao_id)

    if not ctx.alcanca_edicao(edicao_id, "gerenciar_cadastros"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Voce nao gerencia os cadastros desta edicao."
        )

    ja_existe = db.scalar(
        select(DiaEvento).where(
            DiaEvento.edicao_id == edicao_id, DiaEvento.data == dados.data
        )
    )
    if ja_existe:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta edicao ja tem este dia.")

    dia = DiaEvento(edicao_id=edicao_id, **dados.model_dump())
    db.add(dia)
    db.flush()

    registrar(
        db, "dia_criado", usuario_id=ctx.usuario.id,
        tabela="dias_evento", registro_id=dia.id,
        detalhes={"edicao_id": edicao_id, "data": str(dia.data)},
    )
    db.commit()
    db.refresh(dia)
    return DiaOut(
        id=dia.id, edicao_id=dia.edicao_id, data=dia.data,
        descricao=dia.descricao, total_criancas=0,
    )


@router.put("/{edicao_id}/instituicoes/{instituicao_id}/dia", response_model=DiaDaInstituicaoOut)
def definir_dia_da_instituicao(
    edicao_id: int,
    instituicao_id: int,
    dados: DiaDaInstituicaoIn,
    db: BD,
    ctx: Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_cadastros"))],
):
    """Marca em que dia esta instituicao vai, e leva as criancas dela junto.

    O dia e da instituicao: se a Escolinha Sol vai no sabado, todas as criancas
    dela vao no sabado. Nao ha como marcar uma crianca num dia diferente.
    """
    _buscar_edicao(db, ctx, edicao_id)

    if not ctx.alcanca_edicao(edicao_id, "gerenciar_cadastros"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Voce nao gerencia os cadastros desta edicao."
        )

    instituicao = db.get(Instituicao, instituicao_id)
    if instituicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instituicao nao encontrada.")

    edicao = db.get(Edicao, edicao_id)
    if instituicao.cidade_id != edicao.cidade_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Esta instituicao nao e da cidade desta edicao.",
        )

    if dados.dia_evento_id is not None:
        dia = db.get(DiaEvento, dados.dia_evento_id)
        if dia is None or dia.edicao_id != edicao_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Este dia nao e desta edicao."
            )

    quantas = dias.definir(db, edicao_id, instituicao_id, dados.dia_evento_id)

    registrar(
        db, "dia_da_instituicao", usuario_id=ctx.usuario.id,
        tabela="instituicao_dia",
        detalhes={
            "edicao_id": edicao_id,
            "instituicao_id": instituicao_id,
            "dia_evento_id": dados.dia_evento_id,
            "criancas": quantas,
        },
    )
    db.commit()

    return DiaDaInstituicaoOut(
        instituicao_id=instituicao_id,
        instituicao=instituicao.nome,
        dia_evento_id=dados.dia_evento_id,
        criancas_atualizadas=quantas,
    )


@router.delete("/{edicao_id}/dias/{dia_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_dia(
    edicao_id: int,
    dia_id: int,
    db: BD,
    ctx: Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_cadastros"))],
):
    _buscar_edicao(db, ctx, edicao_id)

    if not ctx.alcanca_edicao(edicao_id, "gerenciar_cadastros"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Voce nao gerencia os cadastros desta edicao."
        )

    dia = db.get(DiaEvento, dia_id)
    if dia is None or dia.edicao_id != edicao_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dia nao encontrado.")

    marcadas = db.scalar(
        select(func.count()).select_from(Crianca).where(Crianca.dia_evento_id == dia_id)
    )
    if marcadas:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Este dia tem {marcadas} crianca(s) marcada(s). "
            "Mude as criancas de dia antes de apaga-lo.",
        )

    registrar(
        db, "dia_apagado", usuario_id=ctx.usuario.id,
        tabela="dias_evento", registro_id=dia_id,
        detalhes={"edicao_id": edicao_id, "data": str(dia.data)},
    )
    db.delete(dia)
    db.commit()
