"""Padrinhos, apadrinhamentos e pagamentos.

Um padrinho pertence a uma edicao (cidade + ano) e nao persiste entre anos.
Pode apadrinhar varias criancas, inclusive de outra cidade — e nesse caso o
registro fica visivel pelos dois lados: pela edicao do padrinho e pela da
crianca.
"""

from decimal import Decimal

DOIS_DECIMAIS = Decimal("0.01")
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models import Apadrinhamento, Crianca, Edicao, Padrinho, Pagamento
from app.models.tipos import TipoApadrinhamento
from app.schemas.padrinhos import (
    ApadrinhamentoEditar,
    ApadrinhamentoIn,
    ApadrinhamentoResumo,
    PadrinhoEditar,
    PadrinhoIn,
    PadrinhoOut,
    PaginaPadrinhos,
    PaginaPagamentos,
    PagamentoEditar,
    PagamentoIn,
    PagamentoOut,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos.log import registrar

router = APIRouter(tags=["padrinhos"])

BD = Annotated[Session, Depends(get_db)]
Ver = Annotated[ContextoAcesso, Depends(exige_permissao("ver_padrinhos"))]
Editar = Annotated[ContextoAcesso, Depends(exige_permissao("editar_padrinhos"))]
Pagar = Annotated[ContextoAcesso, Depends(exige_permissao("registrar_pagamentos"))]


# ---------------------------------------------------------------- alcance

def _edicoes(ctx: ContextoAcesso, permissao: str) -> list[int]:
    return ctx.edicoes_com(permissao)


def _filtro_padrinhos(ctx: ContextoAcesso, permissao: str):
    """Padrinhos das edicoes que o usuario alcanca.

    Tambem alcanca o padrinho de outra edicao que apadrinhou uma crianca de uma
    edicao sua — e o caso entre cidades, visivel pelos dois lados.
    """
    if ctx.admin_geral:
        return Padrinho.id.is_not(None)

    edicoes = _edicoes(ctx, permissao)
    if not edicoes:
        return Padrinho.id.is_(None)

    pelo_lado_da_crianca = select(Apadrinhamento.padrinho_id).join(
        Crianca, Crianca.id == Apadrinhamento.crianca_id
    ).where(Crianca.edicao_id.in_(edicoes))

    return or_(
        Padrinho.edicao_id.in_(edicoes),
        Padrinho.id.in_(pelo_lado_da_crianca),
    )


def _saida(padrinho: Padrinho) -> PadrinhoOut:
    resumos = []
    combinado = Decimal("0")
    pago = Decimal("0")

    for a in padrinho.apadrinhamentos:
        quitado = a.pagamento_id is not None
        combinado += a.valor
        if quitado:
            pago += a.valor
        resumos.append(
            ApadrinhamentoResumo(
                id=a.id,
                crianca_id=a.crianca_id,
                crianca_primeiro_nome=a.crianca.primeiro_nome,
                crianca_idade=a.crianca.idade,
                tipo=a.tipo,
                valor=a.valor,
                pago=quitado,
                vai_ao_evento=a.vai_ao_evento,
            )
        )

    return PadrinhoOut(
        id=padrinho.id,
        edicao_id=padrinho.edicao_id,
        edicao=padrinho.edicao.nome,
        cidade=padrinho.edicao.cidade.nome,
        ano=padrinho.edicao.ano,
        nome=padrinho.nome,
        whatsapp=padrinho.whatsapp,
        email=padrinho.email,
        observacoes=padrinho.observacoes,
        criado_em=padrinho.criado_em,
        apadrinhamentos=resumos,
        # Quantizados para o total sair sempre com duas casas: sem isto um
        # padrinho sem pagamento devolvia "0" e outro devolvia "240.00".
        total_combinado=combinado.quantize(DOIS_DECIMAIS),
        total_pago=pago.quantize(DOIS_DECIMAIS),
    )


def _carregar(db: Session, padrinho_id: int, ctx: ContextoAcesso, permissao: str) -> Padrinho:
    padrinho = db.scalar(
        select(Padrinho)
        .where(Padrinho.id == padrinho_id, _filtro_padrinhos(ctx, permissao))
        .options(
            joinedload(Padrinho.edicao).joinedload(Edicao.cidade),
            selectinload(Padrinho.apadrinhamentos).joinedload(Apadrinhamento.crianca),
        )
    )
    if padrinho is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Padrinho nao encontrado.")
    return padrinho


# ---------------------------------------------------------------- padrinhos

@router.get("/padrinhos", response_model=PaginaPadrinhos)
def listar_padrinhos(
    db: BD,
    ctx: Ver,
    edicao_id: int | None = None,
    busca: str | None = None,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
):
    condicao = _filtro_padrinhos(ctx, "ver_padrinhos")

    if edicao_id is not None:
        condicao = condicao & (Padrinho.edicao_id == edicao_id)
    if busca:
        termo = f"%{busca.strip()}%"
        condicao = condicao & or_(
            Padrinho.nome.ilike(termo),
            Padrinho.whatsapp.ilike(termo),
            Padrinho.email.ilike(termo),
        )

    total = db.scalar(select(func.count()).select_from(Padrinho).where(condicao)) or 0

    itens = db.scalars(
        select(Padrinho)
        .where(condicao)
        .options(
            joinedload(Padrinho.edicao).joinedload(Edicao.cidade),
            selectinload(Padrinho.apadrinhamentos).joinedload(Apadrinhamento.crianca),
        )
        .order_by(Padrinho.nome)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).unique().all()

    return PaginaPadrinhos(
        total=total, pagina=pagina, por_pagina=por_pagina,
        itens=[_saida(p) for p in itens],
    )


@router.post("/padrinhos", response_model=PadrinhoOut, status_code=status.HTTP_201_CREATED)
def criar_padrinho(dados: PadrinhoIn, db: BD, ctx: Editar):
    if not ctx.alcanca_edicao(dados.edicao_id, "editar_padrinhos"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Voce nao capta padrinhos nesta edicao.")

    padrinho = Padrinho(
        edicao_id=dados.edicao_id,
        nome=" ".join(dados.nome.split()),
        whatsapp=dados.whatsapp,
        email=dados.email,
        observacoes=dados.observacoes,
        criado_por=ctx.usuario.id,
    )
    db.add(padrinho)
    db.flush()

    registrar(
        db, "padrinho_criado", usuario_id=ctx.usuario.id,
        tabela="padrinhos", registro_id=padrinho.id,
        detalhes={"nome": padrinho.nome, "edicao_id": padrinho.edicao_id},
    )
    db.commit()
    return _saida(_carregar(db, padrinho.id, ctx, "editar_padrinhos"))


@router.get("/padrinhos/{padrinho_id}", response_model=PadrinhoOut)
def detalhe_padrinho(padrinho_id: int, db: BD, ctx: Ver):
    return _saida(_carregar(db, padrinho_id, ctx, "ver_padrinhos"))


@router.patch("/padrinhos/{padrinho_id}", response_model=PadrinhoOut)
def editar_padrinho(padrinho_id: int, dados: PadrinhoEditar, db: BD, ctx: Editar):
    padrinho = _carregar(db, padrinho_id, ctx, "editar_padrinhos")

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        setattr(padrinho, campo, " ".join(valor.split()) if campo == "nome" and valor else valor)

    registrar(
        db, "padrinho_editado", usuario_id=ctx.usuario.id,
        tabela="padrinhos", registro_id=padrinho.id,
        detalhes={"campos": sorted(mudancas)},
    )
    db.commit()
    return _saida(_carregar(db, padrinho_id, ctx, "editar_padrinhos"))


# ---------------------------------------------------------- apadrinhamentos

@router.post("/apadrinhamentos", response_model=PadrinhoOut, status_code=status.HTTP_201_CREATED)
def criar_apadrinhamento(dados: ApadrinhamentoIn, db: BD, ctx: Editar):
    """Liga uma crianca a um padrinho, num dos dois tipos."""
    padrinho = _carregar(db, dados.padrinho_id, ctx, "editar_padrinhos")

    crianca = db.scalar(
        select(Crianca)
        .where(Crianca.id == dados.crianca_id)
        .options(joinedload(Crianca.edicao))
    )
    if crianca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")

    # A crianca precisa estar numa edicao que o usuario alcanca — nao
    # necessariamente a mesma do padrinho, porque entre cidades e permitido.
    if not ctx.alcanca_edicao(crianca.edicao_id, "editar_padrinhos"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Voce nao registra apadrinhamento nesta edicao."
        )

    valor = dados.valor
    if valor is None:
        # Copiado da edicao da CRIANCA: e a edicao que define quanto custa a
        # cesta e a festa daquele evento.
        valor = (
            crianca.edicao.valor_cesta
            if dados.tipo == TipoApadrinhamento.CESTA
            else crianca.edicao.valor_festa
        )

    apadrinhamento = Apadrinhamento(
        crianca_id=crianca.id,
        padrinho_id=padrinho.id,
        tipo=dados.tipo,
        valor=valor,
        comissario_id=ctx.usuario.id,
        vai_ao_evento=dados.vai_ao_evento,
    )
    db.add(apadrinhamento)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Esta crianca ja tem padrinho de {dados.tipo}.",
        )

    registrar(
        db, "apadrinhamento_criado", usuario_id=ctx.usuario.id,
        tabela="apadrinhamentos", registro_id=apadrinhamento.id,
        detalhes={
            "crianca_id": crianca.id, "padrinho_id": padrinho.id,
            "tipo": dados.tipo, "valor": str(valor),
        },
    )
    db.commit()
    return _saida(_carregar(db, padrinho.id, ctx, "editar_padrinhos"))


@router.patch("/apadrinhamentos/{apadrinhamento_id}", response_model=PadrinhoOut)
def editar_apadrinhamento(
    apadrinhamento_id: int, dados: ApadrinhamentoEditar, db: BD, ctx: Editar
):
    apadrinhamento = db.get(Apadrinhamento, apadrinhamento_id)
    if apadrinhamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Apadrinhamento nao encontrado.")

    padrinho = _carregar(db, apadrinhamento.padrinho_id, ctx, "editar_padrinhos")

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        setattr(apadrinhamento, campo, valor)

    registrar(
        db, "apadrinhamento_editado", usuario_id=ctx.usuario.id,
        tabela="apadrinhamentos", registro_id=apadrinhamento.id,
        detalhes={"campos": sorted(mudancas)},
    )
    db.commit()
    return _saida(_carregar(db, padrinho.id, ctx, "editar_padrinhos"))


@router.delete("/apadrinhamentos/{apadrinhamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_apadrinhamento(apadrinhamento_id: int, db: BD, ctx: Editar):
    apadrinhamento = db.get(Apadrinhamento, apadrinhamento_id)
    if apadrinhamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Apadrinhamento nao encontrado.")

    _carregar(db, apadrinhamento.padrinho_id, ctx, "editar_padrinhos")

    if apadrinhamento.pagamento_id is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este apadrinhamento ja esta ligado a um pagamento. "
            "Desfaca o pagamento antes.",
        )

    registrar(
        db, "apadrinhamento_apagado", usuario_id=ctx.usuario.id,
        tabela="apadrinhamentos", registro_id=apadrinhamento.id,
        detalhes={"crianca_id": apadrinhamento.crianca_id, "tipo": apadrinhamento.tipo},
    )
    db.delete(apadrinhamento)
    db.commit()


# ---------------------------------------------------------------- pagamentos

def _saida_pagamento(pagamento: Pagamento) -> PagamentoOut:
    return PagamentoOut(
        id=pagamento.id,
        padrinho_id=pagamento.padrinho_id,
        padrinho=pagamento.padrinho.nome,
        valor=pagamento.valor,
        data=pagamento.data,
        forma=pagamento.forma,
        conferido=pagamento.conferido,
        comprovante_arquivo=pagamento.comprovante_arquivo,
        apadrinhamentos=[a.id for a in pagamento.apadrinhamentos],
    )


def _ligar_apadrinhamentos(
    db: Session, pagamento: Pagamento, ids: list[int], padrinho: Padrinho
) -> None:
    """Deixa o pagamento quitando exatamente os apadrinhamentos pedidos."""
    desejados = set(ids)
    do_padrinho = {a.id for a in padrinho.apadrinhamentos}

    fora = desejados - do_padrinho
    if fora:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Ha apadrinhamentos que nao sao deste padrinho.",
        )

    ja_quitados = db.scalars(
        select(Apadrinhamento).where(
            Apadrinhamento.id.in_(desejados),
            Apadrinhamento.pagamento_id.is_not(None),
            Apadrinhamento.pagamento_id != pagamento.id,
        )
    ).all()
    if ja_quitados:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ha apadrinhamentos ja quitados por outro pagamento.",
        )

    for a in padrinho.apadrinhamentos:
        if a.id in desejados:
            a.pagamento_id = pagamento.id
        elif a.pagamento_id == pagamento.id:
            a.pagamento_id = None


@router.get("/pagamentos", response_model=PaginaPagamentos)
def listar_pagamentos(
    db: BD,
    ctx: Pagar,
    padrinho_id: int | None = None,
    conferido: bool | None = None,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
):
    condicao = Pagamento.padrinho_id.in_(
        select(Padrinho.id).where(_filtro_padrinhos(ctx, "registrar_pagamentos"))
    )
    if padrinho_id is not None:
        condicao = condicao & (Pagamento.padrinho_id == padrinho_id)
    if conferido is not None:
        condicao = condicao & (Pagamento.conferido.is_(conferido))

    total = db.scalar(select(func.count()).select_from(Pagamento).where(condicao)) or 0

    itens = db.scalars(
        select(Pagamento)
        .where(condicao)
        .options(joinedload(Pagamento.padrinho), selectinload(Pagamento.apadrinhamentos))
        .order_by(Pagamento.data.desc(), Pagamento.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).unique().all()

    return PaginaPagamentos(
        total=total, pagina=pagina, por_pagina=por_pagina,
        itens=[_saida_pagamento(p) for p in itens],
    )


@router.post("/pagamentos", response_model=PagamentoOut, status_code=status.HTTP_201_CREATED)
def criar_pagamento(dados: PagamentoIn, db: BD, ctx: Pagar):
    padrinho = _carregar(db, dados.padrinho_id, ctx, "registrar_pagamentos")

    pagamento = Pagamento(
        padrinho_id=padrinho.id,
        valor=dados.valor,
        data=dados.data,
        forma=dados.forma,
        registrado_por=ctx.usuario.id,
    )
    db.add(pagamento)
    db.flush()

    _ligar_apadrinhamentos(db, pagamento, dados.apadrinhamentos, padrinho)

    registrar(
        db, "pagamento_registrado", usuario_id=ctx.usuario.id,
        tabela="pagamentos", registro_id=pagamento.id,
        detalhes={
            "padrinho_id": padrinho.id, "valor": str(dados.valor),
            "apadrinhamentos": dados.apadrinhamentos,
        },
    )
    db.commit()
    db.refresh(pagamento)
    return _saida_pagamento(pagamento)


@router.patch("/pagamentos/{pagamento_id}", response_model=PagamentoOut)
def editar_pagamento(pagamento_id: int, dados: PagamentoEditar, db: BD, ctx: Pagar):
    pagamento = db.get(Pagamento, pagamento_id)
    if pagamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pagamento nao encontrado.")

    padrinho = _carregar(db, pagamento.padrinho_id, ctx, "registrar_pagamentos")

    mudancas = dados.model_dump(exclude_unset=True)
    apadrinhamentos = mudancas.pop("apadrinhamentos", None)

    for campo, valor in mudancas.items():
        setattr(pagamento, campo, valor)

    if apadrinhamentos is not None:
        _ligar_apadrinhamentos(db, pagamento, apadrinhamentos, padrinho)

    registrar(
        db, "pagamento_editado", usuario_id=ctx.usuario.id,
        tabela="pagamentos", registro_id=pagamento.id,
        detalhes={"campos": sorted(dados.model_dump(exclude_unset=True))},
    )
    db.commit()
    db.refresh(pagamento)
    return _saida_pagamento(pagamento)


@router.delete("/pagamentos/{pagamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_pagamento(pagamento_id: int, db: BD, ctx: Pagar):
    pagamento = db.get(Pagamento, pagamento_id)
    if pagamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pagamento nao encontrado.")

    _carregar(db, pagamento.padrinho_id, ctx, "registrar_pagamentos")

    # Solta os apadrinhamentos que ele quitava, senao ficariam apontando para
    # um pagamento que nao existe mais.
    for a in pagamento.apadrinhamentos:
        a.pagamento_id = None

    registrar(
        db, "pagamento_apagado", usuario_id=ctx.usuario.id,
        tabela="pagamentos", registro_id=pagamento.id,
        detalhes={"valor": str(pagamento.valor)},
    )
    db.delete(pagamento)
    db.commit()
