"""Link de pagamento do Mercado Pago, para o padrinho pagar no cartao.

O comissario escolhe as criancas como no apadrinhar, mas em vez de registrar
um pagamento que ja aconteceu, gera um link e manda ao padrinho. As criancas
ficam reservadas enquanto o link vale; quando o Mercado Pago aprova, o
pagamento entra sozinho e as criancas passam a contar como apadrinhadas. O
ciclo inteiro esta em servicos/cobrancas.py.
"""

import secrets
from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import config
from app.database import get_db
from app.models import Apadrinhamento, CobrancaCartao, Pagamento
from app.models.tipos import TipoApadrinhamento
from app.routers.padrinhos import (
    _carregar,
    _crianca_para_apadrinhar,
    _ja_enviado,
    _saida,
    saida_cobranca,
)
from app.schemas.padrinhos import (
    AgradecimentoPendente,
    AvisoDeLinkPago,
    LinkDePagamentoIn,
    MeusLinks,
    PadrinhoOut,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos import cobrancas, mercadopago
from app.servicos.log import registrar

router = APIRouter(tags=["mercado pago"])

BD = Annotated[Session, Depends(get_db)]
Editar = Annotated[ContextoAcesso, Depends(exige_permissao("editar_padrinhos"))]


def _erro_mp(e: mercadopago.ErroMercadoPago) -> HTTPException:
    return HTTPException(status.HTTP_502_BAD_GATEWAY, e.mensagem)


def _resumo(pares: list[tuple[str, str]]) -> str:
    """'Natal Lumen: 2 cestas + 1 festa'. Sem nome de crianca: vai para fora."""
    conta = {t: sum(1 for _, tipo in pares if tipo == t) for t in ("cesta", "festa")}
    partes = []
    for tipo, plural in (("cesta", "cestas"), ("festa", "festas")):
        if conta[tipo]:
            partes.append(f"{conta[tipo]} {tipo if conta[tipo] == 1 else plural}")
    return "Natal Lumen: " + " + ".join(partes)


def _url_aviso() -> str | None:
    if not config.url_publica:
        return None
    return f"{config.url_publica.rstrip('/')}{config.root_path}/mercadopago/notificacoes"


def _resposta(db: Session, ctx: ContextoAcesso, cobranca_id: int) -> PadrinhoOut:
    db.expire_all()
    cobranca = db.get(CobrancaCartao, cobranca_id)
    saida = _saida(_carregar(db, cobranca.padrinho_id, ctx, "editar_padrinhos"))
    saida.ultimo_link = saida_cobranca(cobranca)
    return saida


def _cobranca_minha(db: Session, ctx: ContextoAcesso, cobranca_id: int) -> CobrancaCartao:
    cobranca = db.get(CobrancaCartao, cobranca_id)
    if cobranca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link de pagamento nao encontrado.")
    padrinho = _carregar(db, cobranca.padrinho_id, ctx, "editar_padrinhos")
    if ctx.so_proprias_criancas(padrinho.edicao_id) and cobranca.criado_por != ctx.usuario.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Este link foi gerado por outra pessoa do time. So ela, ou a "
            "coordenacao, mexe nele.",
        )
    return cobranca


@router.get("/mercadopago/situacao")
def situacao(ctx: Editar):
    """Se a tela deve oferecer o link do cartao, e por quanto tempo ele vale."""
    return {"ligado": mercadopago.configurado(), "minutos": config.mercadopago_link_minutos}


@router.post(
    "/padrinhos/{padrinho_id}/link-de-pagamento",
    response_model=PadrinhoOut,
    status_code=status.HTTP_201_CREATED,
)
def gerar_link(padrinho_id: int, dados: LinkDePagamentoIn, db: BD, ctx: Editar):
    """Reserva as criancas e gera o link do Mercado Pago para o padrinho pagar.

    Tudo ou nada, como no apadrinhar: se uma crianca nao puder, ou o Mercado
    Pago nao gerar o link, nada fica gravado.
    """
    if not mercadopago.configurado():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "O link de pagamento ainda nao esta ligado neste sistema.",
        )
    cobrancas.expirar_vencidas(db)

    padrinho = _carregar(db, padrinho_id, ctx, "editar_padrinhos")
    if not ctx.alcanca_edicao(padrinho.edicao_id, "registrar_pagamentos_padrinho"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Gerar o link registra o pagamento quando ele cair, e voce nao "
            "registra pagamentos.",
        )

    ja = _ja_enviado(db, CobrancaCartao, dados.chave_envio)
    if ja is not None:
        if ja.padrinho_id != padrinho.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Este envio ja foi usado para outro padrinho.")
        return _resposta(db, ctx, ja.id)

    pares = [(c.crianca_id, c.tipo) for c in dados.criancas]
    if len(set(pares)) != len(pares):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "A mesma crianca e tipo vieram duas vezes."
        )
    criancas = {cid: _crianca_para_apadrinhar(db, ctx, cid, tipo) for cid, tipo in pares}

    agora = cobrancas.agora()
    cobranca = CobrancaCartao(
        padrinho_id=padrinho.id,
        valor=Decimal("0"),
        status="aguardando",
        referencia=f"nl-{secrets.token_urlsafe(18)}",
        expira_em=agora + timedelta(minutes=config.mercadopago_link_minutos),
        chave_envio=dados.chave_envio,
        criado_por=ctx.usuario.id,
    )
    db.add(cobranca)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        ja = _ja_enviado(db, CobrancaCartao, dados.chave_envio)
        if ja is None:
            raise
        return _resposta(db, ctx, ja.id)

    total = Decimal("0")
    tipos = []
    for crianca_id, tipo in pares:
        crianca = criancas[crianca_id]
        valor = (
            crianca.edicao.valor_cesta
            if tipo == TipoApadrinhamento.CESTA
            else crianca.edicao.valor_festa
        )
        total += Decimal(str(valor))
        db.add(
            Apadrinhamento(
                crianca_id=crianca.id,
                padrinho_id=padrinho.id,
                tipo=tipo,
                valor=valor,
                comissario_id=ctx.usuario.id,
                cobranca_id=cobranca.id,
            )
        )
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{crianca.codigo} ja tem padrinho de {tipo}. Nada foi gravado.",
            )
        tipos.append((crianca.codigo, tipo))
    cobranca.valor = total

    try:
        preferencia = mercadopago.criar_preferencia(
            referencia=cobranca.referencia,
            titulo=_resumo(tipos),
            valor=total,
            expira_em=cobranca.expira_em,
            agora=agora,
            padrinho_nome=padrinho.nome,
            padrinho_email=padrinho.email,
            url_aviso=_url_aviso(),
        )
    except mercadopago.ErroMercadoPago as e:
        db.rollback()
        raise _erro_mp(e) from e

    cobranca.preferencia_id = preferencia["id"]
    cobranca.link = preferencia["link"]
    registrar(
        db, "link_de_pagamento_gerado", usuario_id=ctx.usuario.id,
        tabela="cobrancas_cartao", registro_id=cobranca.id,
        detalhes={
            "padrinho_id": padrinho.id, "valor": str(total),
            "criancas": [{"crianca_id": c, "tipo": t} for c, t in pares],
            "expira_em": cobranca.expira_em.isoformat(),
        },
    )
    db.commit()
    return _resposta(db, ctx, cobranca.id)


@router.get("/cobrancas/minhas", response_model=MeusLinks)
def meus_links(db: BD, ctx: Editar):
    """O que a tela pergunta de tempos em tempos, onde quer que a pessoa esteja.

    Devolve os links pagos que ela gerou e ainda nao viu, para o aviso de
    "pagamento aprovado, mande o agradecimento". Antes, confere no Mercado Pago
    os links dela que ainda esperam: no seu computador o aviso do Mercado Pago
    nao chega, e na producao isto cobre um aviso perdido.
    """
    cobrancas.expirar_vencidas(db)
    abertos = db.scalars(
        select(CobrancaCartao.id).where(
            CobrancaCartao.criado_por == ctx.usuario.id,
            CobrancaCartao.status == "aguardando",
        )
    ).all()
    if mercadopago.configurado():
        for cobranca_id in abertos:
            try:
                cobrancas.conferir(db, cobranca_id)
            except mercadopago.ErroMercadoPago:
                break

    pagos = db.scalars(
        select(CobrancaCartao)
        .where(
            CobrancaCartao.criado_por == ctx.usuario.id,
            CobrancaCartao.status.in_(("pago", "pago_apos_vencer")),
            CobrancaCartao.avisado_em.is_(None),
        )
        .options(
            joinedload(CobrancaCartao.padrinho),
            joinedload(CobrancaCartao.pagamento)
            .selectinload(Pagamento.apadrinhamentos)
            .joinedload(Apadrinhamento.crianca),
        )
        .order_by(CobrancaCartao.encerrada_em)
    ).unique().all()

    ainda = db.scalar(
        select(func.count()).select_from(CobrancaCartao).where(
            CobrancaCartao.criado_por == ctx.usuario.id,
            CobrancaCartao.status == "aguardando",
        )
    )
    return MeusLinks(
        abertos=ainda or 0,
        pagos=[
            AvisoDeLinkPago(
                cobranca_id=c.id,
                status=c.status,
                valor=c.pagamento.valor if c.pagamento else c.valor,
                padrinho_id=c.padrinho_id,
                padrinho_nome=c.padrinho.nome,
                padrinho_whatsapp=c.padrinho.whatsapp,
                apadrinhamentos=[
                    AgradecimentoPendente(
                        id=a.id,
                        crianca_id=a.crianca_id,
                        crianca_primeiro_nome=a.crianca.primeiro_nome,
                    )
                    for a in (c.pagamento.apadrinhamentos if c.pagamento else [])
                ],
            )
            for c in pagos
        ],
    )


@router.post("/cobrancas/{cobranca_id}/avisado", status_code=status.HTTP_204_NO_CONTENT)
def marcar_avisado(cobranca_id: int, db: BD, ctx: Editar):
    """A pessoa viu o aviso de link pago: ele nao aparece mais."""
    cobranca = db.get(CobrancaCartao, cobranca_id)
    if cobranca is None or cobranca.criado_por != ctx.usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link de pagamento nao encontrado.")
    if cobranca.avisado_em is None:
        cobranca.avisado_em = cobrancas.agora()
        db.commit()


@router.post("/cobrancas/{cobranca_id}/conferir", response_model=PadrinhoOut)
def conferir_link(cobranca_id: int, db: BD, ctx: Editar):
    """Pergunta ao Mercado Pago se o padrinho ja pagou. E o caminho do seu
    computador, onde o aviso do Mercado Pago nao chega, e o socorro de quando
    o aviso se perde."""
    cobranca = _cobranca_minha(db, ctx, cobranca_id)
    try:
        cobrancas.conferir(db, cobranca.id)
    except mercadopago.ErroMercadoPago as e:
        raise _erro_mp(e) from e
    return _resposta(db, ctx, cobranca_id)


@router.post("/cobrancas/{cobranca_id}/cancelar", response_model=PadrinhoOut)
def cancelar_link(cobranca_id: int, db: BD, ctx: Editar):
    """Desiste do link: as criancas voltam a ficar livres.

    Pergunta antes ao Mercado Pago: se o padrinho ja pagou, nao cancela, e o
    pagamento entra.
    """
    cobranca = _cobranca_minha(db, ctx, cobranca_id)
    if cobranca.status != "aguardando":
        raise HTTPException(status.HTTP_409_CONFLICT, "Este link ja foi encerrado.")
    try:
        cobranca = cobrancas.conferir(db, cobranca.id)
    except mercadopago.ErroMercadoPago as e:
        raise _erro_mp(e) from e
    if cobranca.status == "pago":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "O padrinho ja pagou este link: o pagamento acabou de entrar, e as "
            "criancas estao apadrinhadas.",
        )
    if cobranca.status_mercadopago in cobrancas.EM_ANDAMENTO:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ha um pagamento deste link em analise no Mercado Pago. Espere a "
            "resposta antes de cancelar.",
        )

    cobranca = cobrancas._travar(db, cobranca_id)
    if cobranca.status == "aguardando":
        if cobranca.preferencia_id:
            mercadopago.encerrar_preferencia(cobranca.preferencia_id, cobrancas.agora())
        cobrancas.liberar(db, cobranca, "cancelado", ctx.usuario.id)
    db.commit()
    return _resposta(db, ctx, cobranca_id)


@router.post("/mercadopago/notificacoes")
def aviso_do_mercadopago(
    request: Request, db: BD, corpo: Annotated[dict | None, Body()] = None
):
    """O aviso (webhook) que o Mercado Pago manda quando um pagamento muda.

    Sem login: quem chama e o Mercado Pago. Por isso o corpo nao vale nada
    sozinho: dele so se tira o numero do pagamento, e o pagamento e lido na
    API com o nosso token. Um aviso falso, no maximo, faz o sistema perguntar
    ao Mercado Pago por um pagamento que nao e nosso.

    Responde 200 a tudo que nao for erro nosso: o Mercado Pago repete o aviso
    enquanto nao recebe 200, e um aviso da lojinha (mesma conta) nao e erro.
    """
    params = request.query_params
    corpo = corpo or {}

    tipo = corpo.get("type") or params.get("type") or params.get("topic")
    dado_id = (
        (corpo.get("data") or {}).get("id")
        or params.get("data.id")
        or (params.get("id") if params.get("topic") == "payment" else None)
    )
    if tipo != "payment" or not dado_id:
        return {"ok": True, "ignorado": True}

    if not mercadopago.assinatura_valida(
        request.headers.get("x-signature"),
        request.headers.get("x-request-id"),
        params.get("data.id") or str(dado_id),
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Assinatura invalida.")

    if not mercadopago.configurado():
        return {"ok": True, "ignorado": True}
    try:
        cobrancas.receber_aviso(db, str(dado_id))
    except mercadopago.ErroMercadoPago as e:
        # 5xx: o Mercado Pago tenta de novo mais tarde.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, e.mensagem) from e
    return {"ok": True}
