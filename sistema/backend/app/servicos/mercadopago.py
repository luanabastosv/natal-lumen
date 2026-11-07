"""Conversa com a API do Mercado Pago (Checkout Pro).

Tres chamadas:

  POST /checkout/preferences          cria o link de pagamento (a "preferencia")
  GET  /v1/payments/{id}              le um pagamento, quando chega o aviso
  GET  /v1/payments/search            procura os pagamentos de um link, para
                                      conferir sem depender do aviso

E uma conferencia local: a assinatura do aviso (webhook).

O que vai para o Mercado Pago e o minimo: o valor, uma descricao sem nome de
crianca ("Natal Lumen: 2 cestas + 1 festa"), e o nome e o email do padrinho
para o formulario ja vir preenchido. Nome de crianca nao sai do sistema.
"""

import hashlib
import hmac
from datetime import datetime
from decimal import Decimal

import httpx2 as httpx

from app.config import config

API = "https://api.mercadopago.com"


class ErroMercadoPago(Exception):
    """Falha com mensagem ja em portugues, para subir ate a tela."""

    def __init__(self, mensagem: str, *, detalhe: str = ""):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhe = detalhe


def configurado() -> bool:
    return config.mercadopago_ligado


def _cabecalhos(chave_idempotencia: str | None = None) -> dict[str, str]:
    cabecalhos = {"Authorization": f"Bearer {config.mercadopago_access_token.strip()}"}
    if chave_idempotencia:
        # Se a conexao cai e a chamada repete, o Mercado Pago devolve o mesmo
        # link em vez de criar outro.
        cabecalhos["X-Idempotency-Key"] = chave_idempotencia
    return cabecalhos


def _pedir(metodo: str, caminho: str, **kwargs) -> dict:
    if not configurado():
        raise ErroMercadoPago(
            "O Mercado Pago nao esta ligado neste sistema. Falta o "
            "MERCADOPAGO_ACCESS_TOKEN no .env (ver docs/MERCADO_PAGO.md)."
        )
    try:
        resposta = httpx.request(
            metodo, f"{API}{caminho}", timeout=config.mercadopago_timeout_s, **kwargs
        )
    except httpx.HTTPError as e:
        raise ErroMercadoPago(
            "Nao foi possivel falar com o Mercado Pago agora. Tente de novo em "
            "instantes.",
            detalhe=str(e),
        ) from e

    if resposta.status_code in (401, 403):
        raise ErroMercadoPago(
            "O Mercado Pago recusou a credencial do sistema. Confira o "
            "MERCADOPAGO_ACCESS_TOKEN.",
            detalhe=resposta.text[:500],
        )
    if resposta.status_code >= 400:
        try:
            corpo = resposta.json()
        except ValueError:
            corpo = {}
        motivo = corpo.get("message") or corpo.get("error") or f"erro {resposta.status_code}"
        raise ErroMercadoPago(
            f"O Mercado Pago recusou o pedido: {motivo}.", detalhe=resposta.text[:500]
        )
    return resposta.json()


def _data_mp(momento: datetime) -> str:
    """O formato que o Mercado Pago aceita: 2026-11-09T12:00:00.000-03:00."""
    return momento.isoformat(timespec="milliseconds")


def criar_preferencia(
    *,
    referencia: str,
    titulo: str,
    valor: Decimal,
    expira_em: datetime,
    agora: datetime,
    padrinho_nome: str,
    padrinho_email: str | None,
    url_aviso: str | None,
) -> dict:
    """Cria o link. Devolve {"id", "link"}."""
    corpo: dict = {
        "items": [
            {
                "id": referencia[:20],
                "title": titulo,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(valor),
            }
        ],
        "external_reference": referencia,
        "expires": True,
        "expiration_date_from": _data_mp(agora),
        "expiration_date_to": _data_mp(expira_em),
        # O que aparece na fatura do cartao do padrinho.
        "statement_descriptor": "NATAL LUMEN",
        # So cartao (decisao de 07/11/2026). O Pix o padrinho ja faz direto,
        # com comprovante; boleto e loterica demoram dias e caberiam depois do
        # prazo do link. "Dinheiro em conta" (saldo do Mercado Pago) o Mercado
        # Pago nao deixa excluir.
        "payment_methods": {
            "excluded_payment_types": [
                {"id": "ticket"},
                {"id": "atm"},
                {"id": "bank_transfer"},
            ],
        },
        "payer": {"name": padrinho_nome},
    }
    if config.mercadopago_parcelas_max > 0:
        corpo["payment_methods"]["installments"] = config.mercadopago_parcelas_max
    if padrinho_email:
        corpo["payer"]["email"] = padrinho_email
    if url_aviso:
        corpo["notification_url"] = url_aviso

    resposta = _pedir(
        "POST", "/checkout/preferences", json=corpo, headers=_cabecalhos(referencia)
    )
    link = resposta.get("init_point")
    if not resposta.get("id") or not link:
        raise ErroMercadoPago("O Mercado Pago nao devolveu o link.", detalhe=str(resposta)[:500])
    return {"id": resposta["id"], "link": link}


def encerrar_preferencia(preferencia_id: str, agora: datetime) -> None:
    """Faz o link parar de aceitar pagamento (ao cancelar). Melhor esforco."""
    try:
        _pedir(
            "PUT",
            f"/checkout/preferences/{preferencia_id}",
            json={"expires": True, "expiration_date_to": _data_mp(agora)},
            headers=_cabecalhos(),
        )
    except ErroMercadoPago:
        pass


def buscar_pagamento(pagamento_id: str) -> dict:
    return _pedir("GET", f"/v1/payments/{pagamento_id}", headers=_cabecalhos())


def pagamentos_da_referencia(referencia: str) -> list[dict]:
    resposta = _pedir(
        "GET",
        "/v1/payments/search",
        params={
            "external_reference": referencia,
            "sort": "date_created",
            "criteria": "desc",
        },
        headers=_cabecalhos(),
    )
    return resposta.get("results") or []


def assinatura_valida(
    assinatura: str | None, pedido_id: str | None, dado_id: str | None
) -> bool:
    """Confere o cabecalho x-signature do aviso.

    O Mercado Pago assina "id:{data.id};request-id:{x-request-id};ts:{ts};" com
    HMAC-SHA256 e a assinatura secreta do painel. Sem segredo configurado,
    passa: o aviso so dispara uma consulta a API, e e a resposta da API que
    vale, nunca o corpo do aviso.
    """
    segredo = config.mercadopago_segredo_webhook.strip()
    if not segredo:
        return True
    if not assinatura:
        return False

    partes = {}
    for pedaco in assinatura.split(","):
        chave, _, valor = pedaco.strip().partition("=")
        partes[chave] = valor
    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1:
        return False

    modelo = ""
    if dado_id:
        modelo += f"id:{dado_id.lower() if dado_id.isalnum() else dado_id};"
    if pedido_id:
        modelo += f"request-id:{pedido_id};"
    modelo += f"ts:{ts};"
    esperado = hmac.new(segredo.encode(), modelo.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)
