"""Kits, compras e check-in das criancas no dia do evento."""

import io
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Apadrinhamento, Cartao, Compra, Crianca, DiaEvento, Kit, Usuario
from app.models.tipos import StatusKit
from app.schemas.logistica import (
    CheckinIn,
    CheckinOut,
    CompraEditar,
    CompraIn,
    CompraOut,
    KitMudar,
    KitOut,
    PaginaCompras,
    PaginaKits,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos.log import registrar

router = APIRouter(tags=["logistica"])

BD = Annotated[Session, Depends(get_db)]
Kits = Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_kits"))]
Compras = Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_compras"))]
Checkin = Annotated[ContextoAcesso, Depends(exige_permissao("fazer_checkin"))]

DOIS_DECIMAIS = Decimal("0.01")


# ---------------------------------------------------------------- kits

@router.get("/kits", response_model=PaginaKits)
def listar_kits(
    db: BD,
    ctx: Kits,
    edicao_id: int | None = None,
    dia_evento_id: int | None = None,
    situacao: str | None = Query(default=None, pattern="^(pendente|montado|entregue)$"),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=100, ge=1, le=500),
):
    """Lista as criancas com o estado do kit de cada uma.

    Parte das criancas, e nao dos kits: a crianca existe desde a importacao, e o
    kit so ganha registro quando alguem mexe nele. Sem isso a equipe de
    estrutura nao veria quem ainda falta.
    """
    condicao = ctx.filtro_criancas("gerenciar_kits")
    if edicao_id is not None:
        condicao = condicao & (Crianca.edicao_id == edicao_id)
    if dia_evento_id is not None:
        condicao = condicao & (Crianca.dia_evento_id == dia_evento_id)

    consulta = (
        select(Crianca, Kit)
        .outerjoin(Kit, Kit.crianca_id == Crianca.id)
        .where(condicao)
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
    )

    if situacao == StatusKit.PENDENTE.value:
        # Sem registro de kit tambem conta como pendente.
        consulta = consulta.where((Kit.id.is_(None)) | (Kit.status == situacao))
    elif situacao is not None:
        consulta = consulta.where(Kit.status == situacao)

    linhas = db.execute(consulta.order_by(Crianca.nome)).unique().all()

    resumo: dict[str, int] = defaultdict(int)
    for _crianca, kit in linhas:
        resumo[kit.status if kit else StatusKit.PENDENTE.value] += 1

    inicio = (pagina - 1) * por_pagina
    pagina_atual = linhas[inicio : inicio + por_pagina]

    return PaginaKits(
        total=len(linhas),
        pagina=pagina,
        por_pagina=por_pagina,
        resumo=dict(resumo),
        itens=[
            KitOut(
                id=kit.id if kit else None,
                crianca_id=crianca.id,
                crianca_nome=crianca.nome,
                instituicao=crianca.instituicao.nome,
                dia_evento=crianca.dia_evento.data if crianca.dia_evento else None,
                status=kit.status if kit else StatusKit.PENDENTE.value,
                entregue_em=kit.entregue_em if kit else None,
                observacoes=kit.observacoes if kit else None,
            )
            for crianca, kit in pagina_atual
        ],
    )


@router.post("/kits", response_model=list[KitOut])
def mudar_kits(dados: KitMudar, db: BD, ctx: Kits):
    """Muda o estado do kit de varias criancas de uma vez.

    A equipe monta os kits em lote, entao mudar um a um seria lento demais.
    """
    criancas = db.scalars(
        select(Crianca)
        .where(Crianca.id.in_(dados.criancas), ctx.filtro_criancas("gerenciar_kits"))
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
    ).all()

    if len(criancas) != len(set(dados.criancas)):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Ha criancas que voce nao alcanca ou que nao existem."
        )

    agora = datetime.now(UTC)
    saida = []

    for crianca in criancas:
        kit = db.scalar(select(Kit).where(Kit.crianca_id == crianca.id))
        if kit is None:
            kit = Kit(crianca_id=crianca.id)
            db.add(kit)

        kit.status = dados.status
        if dados.observacoes is not None:
            kit.observacoes = dados.observacoes

        if dados.status == StatusKit.ENTREGUE.value:
            kit.entregue_em = agora
            kit.entregue_por = ctx.usuario.id
        else:
            # Voltar atras limpa a entrega, senao ficaria data de entrega num
            # kit que voltou para montagem.
            kit.entregue_em = None
            kit.entregue_por = None

        db.flush()
        saida.append(
            KitOut(
                id=kit.id, crianca_id=crianca.id, crianca_nome=crianca.nome,
                instituicao=crianca.instituicao.nome,
                dia_evento=crianca.dia_evento.data if crianca.dia_evento else None,
                status=kit.status, entregue_em=kit.entregue_em, observacoes=kit.observacoes,
            )
        )

    registrar(
        db, "kits_atualizados", usuario_id=ctx.usuario.id,
        tabela="kits",
        detalhes={"status": dados.status, "criancas": [c.id for c in criancas]},
    )
    db.commit()
    return saida


# ---------------------------------------------------------------- compras

def _saida_compra(compra: Compra, responsavel: str | None) -> CompraOut:
    return CompraOut(
        id=compra.id, edicao_id=compra.edicao_id, descricao=compra.descricao,
        categoria=compra.categoria, quantidade=compra.quantidade,
        valor_total=compra.valor_total, fornecedor=compra.fornecedor,
        data=compra.data, responsavel=responsavel,
    )


@router.get("/compras", response_model=PaginaCompras)
def listar_compras(db: BD, ctx: Compras, edicao_id: int | None = None):
    edicoes = ctx.edicoes_com("gerenciar_compras")

    if ctx.admin_geral:
        condicao = Compra.id.is_not(None)
    elif edicoes:
        condicao = Compra.edicao_id.in_(edicoes)
    else:
        condicao = Compra.id.is_(None)

    if edicao_id is not None:
        condicao = condicao & (Compra.edicao_id == edicao_id)

    compras = db.scalars(
        select(Compra).where(condicao).order_by(Compra.data.desc(), Compra.id.desc())
    ).all()

    nomes = {
        u.id: u.nome
        for u in db.scalars(
            select(Usuario).where(Usuario.id.in_({c.responsavel_id for c in compras if c.responsavel_id}))
        ).all()
    }

    total = sum((c.valor_total for c in compras), Decimal("0"))
    por_categoria: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for c in compras:
        por_categoria[c.categoria or "sem categoria"] += c.valor_total

    return PaginaCompras(
        total=len(compras),
        itens=[_saida_compra(c, nomes.get(c.responsavel_id)) for c in compras],
        total_gasto=total.quantize(DOIS_DECIMAIS),
        por_categoria={k: v.quantize(DOIS_DECIMAIS) for k, v in sorted(por_categoria.items())},
    )


@router.post("/compras", response_model=CompraOut, status_code=status.HTTP_201_CREATED)
def criar_compra(dados: CompraIn, db: BD, ctx: Compras):
    if not ctx.alcanca_edicao(dados.edicao_id, "gerenciar_compras"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Voce nao registra compras nesta edicao.")

    compra = Compra(**dados.model_dump(), responsavel_id=ctx.usuario.id)
    db.add(compra)
    db.flush()

    registrar(
        db, "compra_registrada", usuario_id=ctx.usuario.id,
        tabela="compras", registro_id=compra.id,
        detalhes={"descricao": compra.descricao, "valor_total": str(compra.valor_total)},
    )
    db.commit()
    db.refresh(compra)
    return _saida_compra(compra, ctx.usuario.nome)


@router.patch("/compras/{compra_id}", response_model=CompraOut)
def editar_compra(compra_id: int, dados: CompraEditar, db: BD, ctx: Compras):
    compra = db.get(Compra, compra_id)
    if compra is None or not ctx.alcanca_edicao(compra.edicao_id, "gerenciar_compras"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compra nao encontrada.")

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        setattr(compra, campo, valor)

    registrar(
        db, "compra_editada", usuario_id=ctx.usuario.id,
        tabela="compras", registro_id=compra.id,
        detalhes={"campos": sorted(mudancas)},
    )
    db.commit()
    db.refresh(compra)
    return _saida_compra(compra, None)


@router.delete("/compras/{compra_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_compra(compra_id: int, db: BD, ctx: Compras):
    compra = db.get(Compra, compra_id)
    if compra is None or not ctx.alcanca_edicao(compra.edicao_id, "gerenciar_compras"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compra nao encontrada.")

    registrar(
        db, "compra_apagada", usuario_id=ctx.usuario.id,
        tabela="compras", registro_id=compra.id,
        detalhes={"descricao": compra.descricao, "valor_total": str(compra.valor_total)},
    )
    db.delete(compra)
    db.commit()


# ---------------------------------------------------------------- check-in

@router.post("/checkin", response_model=CheckinOut)
def fazer_checkin(dados: CheckinIn, db: BD, ctx: Checkin):
    """Registra a chegada da crianca no dia do evento.

    Nao recusa nada: quem esta na porta precisa deixar a crianca entrar. O que
    estiver estranho — dia errado, sem padrinho, kit nao montado — volta como
    aviso na tela.
    """
    crianca = db.scalar(
        select(Crianca)
        .where(
            func.lower(Crianca.codigo) == dados.codigo.strip().lower(),
            Crianca.edicao_id == dados.edicao_id,
            ctx.filtro_criancas("fazer_checkin"),
        )
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
    )
    if crianca is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Nenhuma crianca com este codigo entre as que voce alcanca.",
        )

    avisos: list[str] = []
    ja_tinha = crianca.checkin_em is not None

    if ja_tinha:
        avisos.append("Esta crianca ja tinha feito check-in.")

    if crianca.dia_evento and crianca.dia_evento.data != date.today():
        avisos.append(
            f"O dia dela e {crianca.dia_evento.data.strftime('%d/%m/%Y')}, nao hoje."
        )
    elif crianca.dia_evento is None:
        avisos.append("Esta crianca nao esta marcada em nenhum dia.")

    kit = db.scalar(select(Kit).where(Kit.crianca_id == crianca.id))
    kit_status = kit.status if kit else StatusKit.PENDENTE.value
    if kit_status == StatusKit.PENDENTE.value:
        avisos.append("O kit dela ainda nao esta montado.")

    padrinhos = db.scalar(
        select(func.count()).select_from(Apadrinhamento).where(Apadrinhamento.crianca_id == crianca.id)
    )
    if not padrinhos:
        avisos.append("Esta crianca nao tem padrinho.")

    cartoes = db.scalar(
        select(func.count()).select_from(Cartao).where(Cartao.crianca_id == crianca.id)
    )
    if cartoes < 2:
        avisos.append(f"Tem {cartoes} de 2 cartoes digitalizados.")

    if not ja_tinha:
        crianca.checkin_em = datetime.now(UTC)
        crianca.checkin_por = ctx.usuario.id

    registrar(
        db, "checkin", usuario_id=ctx.usuario.id,
        tabela="criancas", registro_id=crianca.id,
        detalhes={"codigo": crianca.codigo, "repetido": ja_tinha},
    )
    db.commit()

    return CheckinOut(
        crianca_id=crianca.id,
        nome=crianca.nome,
        idade=crianca.idade,
        instituicao=crianca.instituicao.nome,
        dia_evento=crianca.dia_evento.data if crianca.dia_evento else None,
        ja_tinha_checkin=ja_tinha,
        checkin_em=crianca.checkin_em,
        kit_status=kit_status,
        avisos=avisos,
    )


@router.get("/checkin/qrcode/{crianca_id}")
def qrcode_da_crianca(crianca_id: int, db: BD, ctx: Checkin):
    """QR com o codigo da crianca, para colar no cracha e ler na porta."""
    crianca = db.scalar(
        select(Crianca).where(Crianca.id == crianca_id, ctx.filtro_criancas("fazer_checkin"))
    )
    if crianca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")

    imagem = qrcode.make(f"{crianca.edicao_id}:{crianca.codigo}")
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="image/png")
