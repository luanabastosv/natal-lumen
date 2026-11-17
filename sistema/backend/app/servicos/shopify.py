"""Leitura da lojinha do Natal Lumen no Shopify, para a Estrelinha.

Duas chamadas:

  POST /admin/oauth/access_token          troca id + segredo do app por um
                                          token que vale ~24 h (client
                                          credentials grant, o jeito do
                                          Shopify desde 2026 para app da
                                          propria loja)
  POST /admin/api/{versao}/graphql.json   roda a consulta GraphQL do Claude

So leitura, em duas camadas que nao dependem do Claude:
  1. O app no Shopify so recebe escopos de leitura (read_orders,
     read_products, read_reports). Uma mutation, se passasse, levaria
     ACCESS_DENIED do proprio Shopify.
  2. `so_leitura` recusa antes de sair daqui qualquer documento com
     mutation ou subscription.

A coordenacao nao precisa de conta no Shopify: as credenciais ficam so no
.env do servidor, e quem usa a Estrelinha ve as respostas, nunca o token.
"""

import json
import threading
import time
from typing import Any

import httpx2 as httpx

from app.config import config

# Resposta maior que isso nao ajuda o Claude a responder e enche a conversa.
MAX_CARACTERES = 60_000

_trava = threading.Lock()
_token: dict[str, Any] = {"valor": "", "vence_em": 0.0}


class ErroShopify(Exception):
    """Falha com mensagem em portugues, que o Claude le e repassa."""


def configurado() -> bool:
    return config.shopify_ligado


def _loja() -> str:
    loja = config.shopify_loja.strip().lower()
    loja = loja.removeprefix("https://").removeprefix("http://").split("/")[0]
    return loja.removesuffix(".myshopify.com")


def _base() -> str:
    return f"https://{_loja()}.myshopify.com"


# --- Token -----------------------------------------------------------------


def _pedir_token() -> tuple[str, float]:
    try:
        resposta = httpx.post(
            f"{_base()}/admin/oauth/access_token",
            data={
                "grant_type": "client_credentials",
                "client_id": config.shopify_client_id.strip(),
                "client_secret": config.shopify_client_secret.strip(),
            },
            timeout=config.shopify_timeout_s,
        )
    except httpx.HTTPError as erro:
        raise ErroShopify(f"Nao consegui falar com o Shopify agora: {erro}") from erro

    if resposta.status_code >= 400:
        texto = resposta.text[:300]
        if "shop_not_permitted" in texto:
            raise ErroShopify(
                "O Shopify recusou o app (shop_not_permitted): o app e a loja nao "
                "estao na mesma organizacao do Dev Dashboard."
            )
        raise ErroShopify(
            f"O Shopify recusou as credenciais do app (HTTP {resposta.status_code}). "
            f"Confira SHOPIFY_LOJA, SHOPIFY_CLIENT_ID e SHOPIFY_CLIENT_SECRET. {texto}"
        )
    corpo = resposta.json()
    validade = float(corpo.get("expires_in") or 86399)
    return corpo["access_token"], time.monotonic() + validade


def _token_valido(renovar: bool = False) -> str:
    with _trava:
        # Renova com folga de 2 minutos, em vez de pedir um token por chamada.
        if renovar or not _token["valor"] or time.monotonic() > _token["vence_em"] - 120:
            _token["valor"], _token["vence_em"] = _pedir_token()
        return _token["valor"]


def esquecer_token() -> None:
    with _trava:
        _token["valor"], _token["vence_em"] = "", 0.0


# --- Guarda de leitura -------------------------------------------------------


def _palavras_de_fora(documento: str) -> list[str]:
    """Palavras fora de qualquer { }, sem comentarios, textos e $variaveis.

    Sao elas que dizem o tipo da operacao (query, mutation, subscription,
    fragment). Um campo chamado "mutation" dentro da selecao nao conta.
    """
    palavras: list[str] = []
    profundidade = 0
    i, n = 0, len(documento)
    while i < n:
        c = documento[i]
        if c == "#":
            while i < n and documento[i] not in "\r\n":
                i += 1
        elif documento.startswith('"""', i):
            fim = documento.find('"""', i + 3)
            i = n if fim < 0 else fim + 3
            continue
        elif c == '"':
            i += 1
            while i < n and documento[i] != '"':
                i += 2 if documento[i] == "\\" else 1
        elif c == "{":
            profundidade += 1
        elif c == "}":
            profundidade -= 1
        elif c.isalpha() or c == "_":
            inicio = i
            while i < n and (documento[i].isalnum() or documento[i] == "_"):
                i += 1
            if profundidade == 0 and (inicio == 0 or documento[inicio - 1] != "$"):
                palavras.append(documento[inicio:i].lower())
            continue
        i += 1
    return palavras


def so_leitura(documento: str) -> None:
    if "{" not in documento:
        raise ValueError("Mande uma consulta GraphQL, como: { shop { name } }")
    proibidas = {"mutation", "subscription"} & set(_palavras_de_fora(documento))
    if proibidas:
        raise ValueError(
            "A Estrelinha so le a loja: mutation e subscription nao sao permitidas."
        )


# --- Consulta ----------------------------------------------------------------


def _postar(documento: str, variaveis: dict[str, Any] | None, token: str) -> httpx.Response:
    try:
        return httpx.post(
            f"{_base()}/admin/api/{config.shopify_versao_api.strip()}/graphql.json",
            json={"query": documento, "variables": variaveis or {}},
            headers={"X-Shopify-Access-Token": token},
            timeout=config.shopify_timeout_s,
        )
    except httpx.HTTPError as erro:
        raise ErroShopify(f"Nao consegui falar com o Shopify agora: {erro}") from erro


def consultar(documento: str, variaveis: dict[str, Any] | None = None) -> dict[str, Any]:
    """Roda uma consulta GraphQL so de leitura na Admin API da loja.

    Devolve `data` e, se houver, `errors` do Shopify: o Claude le o erro
    (campo errado, ACCESS_DENIED, parseErrors do ShopifyQL) e corrige.
    """
    if not configurado():
        raise ErroShopify(
            "A loja do Shopify nao esta ligada na Estrelinha. Faltam SHOPIFY_LOJA, "
            "SHOPIFY_CLIENT_ID e SHOPIFY_CLIENT_SECRET no .env (docs/ESTRELINHA.md)."
        )
    documento = (documento or "").strip()
    so_leitura(documento)

    resposta = _postar(documento, variaveis, _token_valido())
    if resposta.status_code == 401:  # token revogado ou vencido antes da hora
        resposta = _postar(documento, variaveis, _token_valido(renovar=True))
    if resposta.status_code == 429:
        raise ErroShopify("O Shopify pediu para esperar (limite de chamadas). Tente de novo.")
    if resposta.status_code >= 400:
        raise ErroShopify(f"O Shopify respondeu HTTP {resposta.status_code}: {resposta.text[:500]}")

    corpo = resposta.json()
    resultado = {k: corpo[k] for k in ("data", "errors") if corpo.get(k) is not None}
    if len(json.dumps(resultado, ensure_ascii=False, default=str)) > MAX_CARACTERES:
        raise ErroShopify(
            "A resposta veio grande demais. Peca menos campos, use first: menor "
            "ou um resumo pelo shopifyqlQuery."
        )
    return resultado
