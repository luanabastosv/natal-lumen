"""Financeiro da edicao: as saidas e os recebimentos.

Sao duas permissoes, e nao uma, de proposito:

    gerenciar_compras     lanca e ve as SAIDAS. Hoje so a coordenacao tem; a
                          estrutura teve ate 06/10/2026.
    registrar_pagamentos  lanca e ve os RECEBIMENTOS. So a coordenacao tem —
                          e a mesma permissao dos pagamentos dos padrinhos,
                          porque e o mesmo assunto: dinheiro que entrou.

Por isso nao existe uma rota so, de resumo, devolvendo tudo: quem cuida so das
compras ve o que a edicao gastou sem ver o que ela arrecadou. O saldo aparece
na tela de quem alcanca as duas metades, somado la.

`GET /recebimentos` e a lista de TODO o dinheiro que entrou, e junta duas
tabelas:

    pagamentos    o padrinho pagando o que apadrinhou. Nao e copiado para ca:
                  a linha e o proprio pagamento, lido de lado, e a categoria
                  dela e DERIVADA do que ele quita (so cesta, so festa, ou os
                  dois). Assim a categoria nunca pode divergir do que foi pago.
    recebimentos  o que chega solto: doacao ou outros.

As duas somas e as duas contagens que a tela mostra saem de uma passada em
memoria sobre as duas listas inteiras, e nao de um GROUP BY: a categoria do
pagamento depende dos apadrinhamentos dele, que o SQL nao agrupa sozinho. Sao
centenas de linhas por edicao — se um dia virar milhares, o lugar de consertar
e aqui.
"""

from collections import defaultdict
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import false, select, true
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models import Compra, Edicao, Padrinho, Pagamento, Recebimento, Usuario
from app.models.tipos import CategoriaRecebimento, TipoApadrinhamento
from app.schemas.financeiro import (
    CompraEditar,
    CompraIn,
    CompraOut,
    LinhaRecebimento,
    PaginaCompras,
    PaginaRecebimentos,
    RecebimentoEditar,
    RecebimentoIn,
    RecebimentoOut,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos import comprovantes
from app.servicos.log import registrar

router = APIRouter(tags=["financeiro"])

BD = Annotated[Session, Depends(get_db)]
Saidas = Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_compras"))]
Entradas = Annotated[ContextoAcesso, Depends(exige_permissao("registrar_pagamentos"))]

DOIS_DECIMAIS = Decimal("0.01")
SEM_CATEGORIA = "sem categoria"

ZERO = Decimal("0")

# Categorias DERIVADAS, que so existem na saida da lista: elas vem do que o
# pagamento quita, e por isso nao ficam gravadas em lugar nenhum. As gravadas
# sao as de CategoriaRecebimento ('doacao', 'outros').
CAT_CESTA = "apadrinhamento_cesta"
CAT_FESTA = "apadrinhamento_festa"
# Um pagamento que quita cesta E festa juntas, ou que ainda nao quita nada.
CAT_APADRINHAMENTO = "apadrinhamento"

FONTE_PAGAMENTO = "pagamento"
FONTE_RECEBIMENTO = "recebimento"

CESTA = TipoApadrinhamento.CESTA.value
FESTA = TipoApadrinhamento.FESTA.value


def _por_edicao(ctx: ContextoAcesso, coluna, permissao: str, edicao_id: int | None):
    """Condicao que limita as linhas as edicoes que o usuario alcanca."""
    if ctx.admin_geral:
        condicao = true()
    elif edicoes := ctx.edicoes_com(permissao):
        condicao = coluna.in_(edicoes)
    else:
        condicao = false()

    if edicao_id is not None:
        condicao = condicao & (coluna == edicao_id)
    return condicao


def _nomes(db: Session, ids: set[int | None]) -> dict[int, str]:
    reais = {i for i in ids if i}
    if not reais:
        return {}
    return {
        u.id: u.nome
        for u in db.scalars(select(Usuario).where(Usuario.id.in_(reais))).all()
    }


def _agrupar(linhas, valor_de) -> dict[str, Decimal]:
    por_categoria: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for linha in linhas:
        por_categoria[linha.categoria or SEM_CATEGORIA] += valor_de(linha)
    return {
        chave: valor.quantize(DOIS_DECIMAIS)
        for chave, valor in sorted(por_categoria.items())
    }


# ------------------------------------------------------------------- saidas

def _saida_compra(compra: Compra, responsavel: str | None) -> CompraOut:
    return CompraOut(
        id=compra.id, edicao_id=compra.edicao_id, descricao=compra.descricao,
        categoria=compra.categoria, quantidade=compra.quantidade,
        valor_total=compra.valor_total, fornecedor=compra.fornecedor,
        data=compra.data, responsavel=responsavel,
    )


@router.get("/compras", response_model=PaginaCompras)
def listar_compras(db: BD, ctx: Saidas, edicao_id: int | None = None):
    condicao = _por_edicao(ctx, Compra.edicao_id, "gerenciar_compras", edicao_id)

    compras = db.scalars(
        select(Compra).where(condicao).order_by(Compra.data.desc(), Compra.id.desc())
    ).all()

    nomes = _nomes(db, {c.responsavel_id for c in compras})
    total = sum((c.valor_total for c in compras), Decimal("0"))

    return PaginaCompras(
        total=len(compras),
        itens=[_saida_compra(c, nomes.get(c.responsavel_id)) for c in compras],
        total_gasto=total.quantize(DOIS_DECIMAIS),
        por_categoria=_agrupar(compras, lambda c: c.valor_total),
    )


@router.post("/compras", response_model=CompraOut, status_code=status.HTTP_201_CREATED)
def criar_compra(dados: CompraIn, db: BD, ctx: Saidas):
    if not ctx.alcanca_edicao(dados.edicao_id, "gerenciar_compras"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Voce nao registra saidas nesta edicao.")

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
def editar_compra(compra_id: int, dados: CompraEditar, db: BD, ctx: Saidas):
    compra = db.get(Compra, compra_id)
    if compra is None or not ctx.alcanca_edicao(compra.edicao_id, "gerenciar_compras"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saida nao encontrada.")

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
    return _saida_compra(compra, _nomes(db, {compra.responsavel_id}).get(compra.responsavel_id))


@router.delete("/compras/{compra_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_compra(compra_id: int, db: BD, ctx: Saidas):
    compra = db.get(Compra, compra_id)
    if compra is None or not ctx.alcanca_edicao(compra.edicao_id, "gerenciar_compras"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saida nao encontrada.")

    registrar(
        db, "compra_apagada", usuario_id=ctx.usuario.id,
        tabela="compras", registro_id=compra.id,
        detalhes={"descricao": compra.descricao, "valor_total": str(compra.valor_total)},
    )
    db.delete(compra)
    db.commit()


# -------------------------------------------------------------- recebimentos

def _saida_recebimento(r: Recebimento, responsavel: str | None) -> RecebimentoOut:
    return RecebimentoOut(
        id=r.id, edicao_id=r.edicao_id, descricao=r.descricao, categoria=r.categoria,
        valor=r.valor, data=r.data, doador=r.doador, forma=r.forma,
        observacoes=r.observacoes, conferido=r.conferido,
        comprovante_arquivo=r.comprovante_arquivo,
        comprovante_drive_link=r.comprovante_drive_link,
        responsavel=responsavel,
    )


def _categoria_do_pagamento(pagamento: Pagamento) -> str:
    """A categoria sai do que o pagamento quita, e nao de um campo escolhido.

    Um campo escolhido poderia dizer "cesta" num dinheiro que pagou festa; isto
    aqui nao pode. Cesta e festa juntas, ou nada marcado ainda, caem no
    apadrinhamento sem tipo — que e a verdade nos dois casos.
    """
    tipos = {a.tipo for a in pagamento.apadrinhamentos}
    if tipos == {CESTA}:
        return CAT_CESTA
    if tipos == {FESTA}:
        return CAT_FESTA
    return CAT_APADRINHAMENTO


def _resumo_do_pagamento(pagamento: Pagamento) -> str:
    """"2 cestas + 1 festa" — escrito como a coordenacao fala."""
    conta: dict[str, int] = defaultdict(int)
    for a in pagamento.apadrinhamentos:
        conta[a.tipo] += 1

    partes = []
    for tipo, singular, plural in ((CESTA, "cesta", "cestas"), (FESTA, "festa", "festas")):
        if conta[tipo]:
            partes.append(f"{conta[tipo]} {singular if conta[tipo] == 1 else plural}")

    return " + ".join(partes) if partes else "sem apadrinhamento marcado"


def _linha_do_pagamento(pagamento: Pagamento, responsavel: str | None) -> LinhaRecebimento:
    return LinhaRecebimento(
        fonte=FONTE_PAGAMENTO,
        id=pagamento.id,
        categoria=_categoria_do_pagamento(pagamento),
        descricao=_resumo_do_pagamento(pagamento),
        quem=pagamento.padrinho.nome,
        valor=pagamento.valor,
        data=pagamento.data,
        forma=pagamento.forma,
        observacoes=pagamento.observacoes,
        conferido=pagamento.conferido,
        tem_comprovante=bool(pagamento.comprovante_arquivo),
        comprovante_drive_link=pagamento.comprovante_drive_link,
        responsavel=responsavel,
        sem_destino=not pagamento.apadrinhamentos,
    )


def _linha_do_recebimento(r: Recebimento, responsavel: str | None) -> LinhaRecebimento:
    return LinhaRecebimento(
        fonte=FONTE_RECEBIMENTO,
        id=r.id,
        categoria=r.categoria,
        descricao=r.descricao,
        quem=r.doador,
        valor=r.valor,
        data=r.data,
        forma=r.forma,
        observacoes=r.observacoes,
        conferido=r.conferido,
        tem_comprovante=bool(r.comprovante_arquivo),
        comprovante_drive_link=r.comprovante_drive_link,
        responsavel=responsavel,
    )


def _edicao_do_recebimento(db: Session, edicao_id: int) -> Edicao:
    """A edicao com a cidade, que e o que nomeia o arquivo do comprovante."""
    return db.scalar(
        select(Edicao).where(Edicao.id == edicao_id).options(joinedload(Edicao.cidade))
    )


@router.get("/recebimentos", response_model=PaginaRecebimentos)
def listar_recebimentos(
    db: BD,
    ctx: Entradas,
    edicao_id: int | None = None,
    categoria: str | None = None,
    conferido: bool | None = None,
    comprovante: bool | None = None,
    limite: int = Query(default=300, ge=1, le=1000),
):
    """Tudo o que entrou: os pagamentos dos padrinhos e os recebimentos soltos.

    Os filtros cortam a LISTA, nunca os totais — ver PaginaRecebimentos.
    """
    pagamentos = db.scalars(
        select(Pagamento)
        .where(
            Pagamento.padrinho_id.in_(
                select(Padrinho.id).where(
                    _por_edicao(ctx, Padrinho.edicao_id, "registrar_pagamentos", edicao_id)
                )
            )
        )
        .options(joinedload(Pagamento.padrinho), selectinload(Pagamento.apadrinhamentos))
    ).unique().all()

    avulsos = db.scalars(
        select(Recebimento).where(
            _por_edicao(ctx, Recebimento.edicao_id, "registrar_pagamentos", edicao_id)
        )
    ).all()

    nomes = _nomes(
        db,
        {p.registrado_por for p in pagamentos} | {r.registrado_por for r in avulsos},
    )

    linhas = [_linha_do_pagamento(p, nomes.get(p.registrado_por)) for p in pagamentos]
    linhas += [_linha_do_recebimento(r, nomes.get(r.registrado_por)) for r in avulsos]

    # Os totais saem de TODAS as linhas, antes de qualquer filtro.
    total_recebido = sum((l.valor for l in linhas), ZERO)
    por_categoria: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for l in linhas:
        por_categoria[l.categoria] += l.valor

    a_conferir = sum((l.valor for l in linhas if not l.conferido), ZERO)
    sem_comprovante = sum(1 for l in linhas if not l.tem_comprovante)
    do_apadrinhamento = sum((p.valor for p in pagamentos), ZERO)

    if categoria is not None:
        linhas = [l for l in linhas if l.categoria == categoria]
    if conferido is not None:
        linhas = [l for l in linhas if l.conferido is conferido]
    if comprovante is not None:
        linhas = [l for l in linhas if l.tem_comprovante is comprovante]

    # Mais recente primeiro; empate resolvido pelo maior id, para a ordem nao
    # mudar entre dois pedidos iguais.
    linhas.sort(key=lambda l: (l.data, l.id), reverse=True)

    return PaginaRecebimentos(
        total=len(linhas),
        itens=linhas[:limite],
        total_recebido=total_recebido.quantize(DOIS_DECIMAIS),
        por_categoria={
            chave: valor.quantize(DOIS_DECIMAIS)
            for chave, valor in sorted(por_categoria.items())
        },
        apadrinhamento=do_apadrinhamento.quantize(DOIS_DECIMAIS),
        pagamentos=len(pagamentos),
        a_conferir=a_conferir.quantize(DOIS_DECIMAIS),
        sem_comprovante=sem_comprovante,
    )


@router.post(
    "/recebimentos", response_model=RecebimentoOut, status_code=status.HTTP_201_CREATED
)
def criar_recebimento(dados: RecebimentoIn, db: BD, ctx: Entradas):
    if not ctx.alcanca_edicao(dados.edicao_id, "registrar_pagamentos"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Voce nao registra recebimentos nesta edicao."
        )

    recebimento = Recebimento(
        **dados.model_dump(exclude={"categoria"}),
        categoria=dados.categoria.value,
        registrado_por=ctx.usuario.id,
    )
    db.add(recebimento)
    db.flush()

    registrar(
        db, "recebimento_registrado", usuario_id=ctx.usuario.id,
        tabela="recebimentos", registro_id=recebimento.id,
        detalhes={
            "descricao": recebimento.descricao,
            "categoria": recebimento.categoria,
            "valor": str(recebimento.valor),
        },
    )
    db.commit()
    db.refresh(recebimento)
    return _saida_recebimento(recebimento, ctx.usuario.nome)


def _carregar_recebimento(db: Session, recebimento_id: int, ctx: ContextoAcesso) -> Recebimento:
    recebimento = db.get(Recebimento, recebimento_id)
    if recebimento is None or not ctx.alcanca_edicao(
        recebimento.edicao_id, "registrar_pagamentos"
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recebimento nao encontrado.")
    return recebimento


@router.patch("/recebimentos/{recebimento_id}", response_model=RecebimentoOut)
def editar_recebimento(
    recebimento_id: int, dados: RecebimentoEditar, db: BD, ctx: Entradas
):
    recebimento = _carregar_recebimento(db, recebimento_id, ctx)

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        setattr(
            recebimento,
            campo,
            valor.value if isinstance(valor, CategoriaRecebimento) else valor,
        )

    registrar(
        db, "recebimento_editado", usuario_id=ctx.usuario.id,
        tabela="recebimentos", registro_id=recebimento.id,
        detalhes={"campos": sorted(mudancas)},
    )
    db.commit()
    db.refresh(recebimento)
    nomes = _nomes(db, {recebimento.registrado_por})
    return _saida_recebimento(recebimento, nomes.get(recebimento.registrado_por))


@router.delete("/recebimentos/{recebimento_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_recebimento(recebimento_id: int, db: BD, ctx: Entradas):
    recebimento = _carregar_recebimento(db, recebimento_id, ctx)

    registrar(
        db, "recebimento_apagado", usuario_id=ctx.usuario.id,
        tabela="recebimentos", registro_id=recebimento.id,
        detalhes={"descricao": recebimento.descricao, "valor": str(recebimento.valor)},
    )
    # Sem a linha ninguem mais alcanca o arquivo: ele sai do disco junto.
    comprovantes.apagar_arquivo(recebimento)
    db.delete(recebimento)
    db.commit()


# ------------------------------------------- comprovante do recebimento

@router.post("/recebimentos/{recebimento_id}/comprovante", response_model=RecebimentoOut)
async def subir_comprovante_do_recebimento(
    recebimento_id: int,
    db: BD,
    ctx: Entradas,
    arquivo: UploadFile = File(...),
):
    """Guarda o comprovante desta doacao.

    Mesmo servico do comprovante do pagamento, e por isso mesmo caminho no
    disco, mesmo espelho no Drive e mesmo cuidado com o arquivo antigo: o
    recibo de uma doacao prova a mesma coisa que o de um apadrinhamento.

    Separado do POST /recebimentos pelo mesmo motivo de sempre: o lancamento do
    dinheiro nao pode falhar por causa de um arquivo grande demais.
    """
    recebimento = _carregar_recebimento(db, recebimento_id, ctx)
    edicao = _edicao_do_recebimento(db, recebimento.edicao_id)

    await comprovantes.guardar(
        db, recebimento, arquivo,
        cidade=edicao.cidade.nome,
        ano=edicao.ano,
        # Sem doador, o arquivo leva a descricao: um nome de arquivo com o que
        # foi recebido ainda encontra a linha; "COMPROVANTE_2026_11_02" nao.
        titular=recebimento.doador or recebimento.descricao,
        data=recebimento.data,
        tabela="recebimentos",
        usuario_id=ctx.usuario.id,
    )

    db.commit()
    db.refresh(recebimento)
    nomes = _nomes(db, {recebimento.registrado_por})
    return _saida_recebimento(recebimento, nomes.get(recebimento.registrado_por))


@router.get("/recebimentos/{recebimento_id}/comprovante")
def baixar_comprovante_do_recebimento(recebimento_id: int, db: BD, ctx: Entradas):
    """Devolve o arquivo. Unica porta para ele, sempre autenticada."""
    return comprovantes.entregar(_carregar_recebimento(db, recebimento_id, ctx))
