"""Estrelinha + lojinha no Shopify: le a loja, renova o token e nunca altera nada.

Nao fala com o Shopify de verdade nem precisa do banco: as chamadas HTTP
sao trocadas por um Shopify de mentira, que anota o que recebeu.

Rodar com:  python -m tests.test_estrelinha_loja
"""

import json
import os

# A aplicacao exige estas duas para importar; o teste nao usa o banco.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x:x@localhost:1/x")
os.environ.setdefault("JWT_SECRET", "teste")

from fastapi.testclient import TestClient  # noqa: E402

from app.config import config  # noqa: E402
from app.main import app  # noqa: E402
from app.servicos import shopify  # noqa: E402

URL = "/estrelinha/mcp"
TOKEN_MCP = "token-da-estrelinha-de-teste"

ok = 0
falhas: list[str] = []


def confere(d: str, c: bool, extra: str = "") -> None:
    global ok
    if c:
        ok += 1
        print(f"  ok     {d}")
    else:
        falhas.append(d)
        print(f"  FALHOU {d} {extra}")


class Resposta:
    def __init__(self, status: int, corpo: dict | str):
        self.status_code = status
        self._corpo = corpo
        self.text = corpo if isinstance(corpo, str) else json.dumps(corpo)

    def json(self):
        return self._corpo if isinstance(self._corpo, dict) else json.loads(self._corpo)


class ShopifyDeMentira:
    """Faz o papel de httpx.post dentro de app.servicos.shopify."""

    def __init__(self):
        self.pedidos_de_token: list[dict] = []
        self.consultas: list[dict] = []
        self.recusar_token_vez = 0  # >0: a n-esima consulta leva 401
        self.erro_token = ""
        self.resposta_graphql: dict = {"data": {"shop": {"name": "Lojinha Natal Lumen"}}}

    def post(self, url, data=None, json=None, headers=None, timeout=None):  # noqa: A002
        if url.endswith("/admin/oauth/access_token"):
            self.pedidos_de_token.append({"url": url, **(data or {})})
            if self.erro_token:
                return Resposta(400, self.erro_token)
            n = len(self.pedidos_de_token)
            return Resposta(200, {"access_token": f"shpat_{n}", "scope": "read_orders",
                                  "expires_in": 86399})
        self.consultas.append({"url": url, "corpo": json, "token": (headers or {}).get(
            "X-Shopify-Access-Token")})
        if self.recusar_token_vez and len(self.consultas) == self.recusar_token_vez:
            return Resposta(401, {"errors": "[API] Invalid API key or access token"})
        return Resposta(200, self.resposta_graphql)


def rpc(cliente, metodo, params=None):
    corpo = {"jsonrpc": "2.0", "id": 1, "method": metodo, "params": params or {}}
    return cliente.post(f"{URL}?key={TOKEN_MCP}", json=corpo).json()["result"]


def loja(cliente, graphql, variaveis=None):
    argumentos = {"graphql": graphql}
    if variaveis is not None:
        argumentos["variaveis"] = variaveis
    r = rpc(cliente, "tools/call", {"name": "consultar_loja", "arguments": argumentos})
    return r["isError"], json.loads(r["content"][0]["text"])


def ligar_loja(ligada: bool) -> None:
    config.shopify_loja = "natal-lumen.myshopify.com" if ligada else ""
    config.shopify_client_id = "id-do-app" if ligada else ""
    config.shopify_client_secret = "segredo-do-app" if ligada else ""
    shopify.esquecer_token()


def main() -> None:
    config.estrelinha_token = TOKEN_MCP
    config.estrelinha_database_url = config.estrelinha_database_url or "postgresql+psycopg://x"
    falso = ShopifyDeMentira()
    post_original = shopify.httpx.post
    shopify.httpx.post = falso.post
    cliente = TestClient(app)
    try:
        print("Sem credenciais da loja")
        ligar_loja(False)
        nomes = [t["name"] for t in rpc(cliente, "tools/list")["tools"]]
        confere("consultar_loja nao aparece", "consultar_loja" not in nomes, str(nomes))
        ini = rpc(cliente, "initialize", {"protocolVersion": "2025-06-18"})
        confere("instrucoes nao falam da loja", "LOJINHA" not in ini["instructions"])
        r = rpc(cliente, "tools/call", {"name": "consultar_loja", "arguments": {"graphql": "{shop{name}}"}})
        confere("chamar mesmo assim da erro", r["isError"])
        confere("e nada saiu para o Shopify", not falso.consultas and not falso.pedidos_de_token)

        print("Com credenciais da loja")
        ligar_loja(True)
        nomes = [t["name"] for t in rpc(cliente, "tools/list")["tools"]]
        confere("tools/list tem as quatro ferramentas",
                nomes == ["ver_estrutura", "consultar", "gerar_sorrisometro", "consultar_loja"], str(nomes))
        ini = rpc(cliente, "initialize", {"protocolVersion": "2025-06-18"})
        confere("instrucoes ensinam o ShopifyQL",
                "LOJINHA" in ini["instructions"] and "shopifyqlQuery" in ini["instructions"])

        erro, dados = loja(cliente, "{ shop { name } }")
        confere("le a loja", not erro and dados == falso.resposta_graphql, str(dados))
        token = falso.pedidos_de_token[0]
        confere("pede o token por client_credentials, na loja certa",
                token["grant_type"] == "client_credentials" and token["client_id"] == "id-do-app"
                and token["client_secret"] == "segredo-do-app"
                and token["url"] == "https://natal-lumen.myshopify.com/admin/oauth/access_token")
        consulta = falso.consultas[0]
        confere("consulta vai para a Admin API na versao do .env",
                consulta["url"] == f"https://natal-lumen.myshopify.com/admin/api/"
                                   f"{config.shopify_versao_api}/graphql.json")
        confere("manda o token no cabecalho, nunca o segredo",
                consulta["token"] == "shpat_1" and "segredo" not in json.dumps(consulta["corpo"]))

        erro, _ = loja(cliente, "query($n: Int!) { orders(first: $n) { nodes { name } } }", {"n": 5})
        confere("variaveis chegam ao Shopify",
                not erro and falso.consultas[-1]["corpo"]["variables"] == {"n": 5})
        confere("reaproveita o token (um pedido so)", len(falso.pedidos_de_token) == 1)

        falso.recusar_token_vez = len(falso.consultas) + 1
        erro, _ = loja(cliente, "{ shop { name } }")
        confere("token recusado: renova e tenta de novo",
                not erro and len(falso.pedidos_de_token) == 2
                and falso.consultas[-1]["token"] == "shpat_2")
        falso.recusar_token_vez = 0

        print("Consultas que tem de passar")
        for d, g in [
            ("ShopifyQL", '{ shopifyqlQuery(query: "FROM sales SHOW net_sales GROUP BY '
                          'product_title SINCE -30d") { tableData { rows } parseErrors } }'),
            ("query com nome", "query Vendas { orders(first: 5) { nodes { name } } }"),
            ("palavra mutation dentro de um texto",
             '{ orders(first: 5, query: "tag:mutation") { nodes { name } } }'),
            ("variavel chamada $mutation", "query($mutation: String) { shop { name } }"),
            ("fragmento", "query { shop { ...F } } fragment F on Shop { name }"),
        ]:
            erro, dados = loja(cliente, g)
            confere(f"passa: {d}", not erro, str(dados))

        print("Ataques")
        antes = len(falso.consultas)
        for d, g in [
            ("mutation", 'mutation { productDelete(input: {id: "gid://shopify/Product/1"}) '
                         "{ deletedProductId } }"),
            ("mutation com nome", "mutation Apagar { orderCancel(orderId: \"x\") { job { id } } }"),
            ("mutation em maiusculas", "MUTATION { a }"),
            ("mutation depois de um comentario", "# so uma consulta\nmutation { a }"),
            ("mutation escondida depois de uma query", "query A { shop { name } } mutation B { a }"),
            ("mutation depois de um texto com chaves", 'query A { x(q: "}") } mutation B { a }'),
            ("subscription", "subscription { a }"),
            ("texto sem consulta", "me diga as vendas"),
        ]:
            erro, _ = loja(cliente, g)
            confere(f"barrado: {d}", erro)
        confere("nenhum ataque chegou ao Shopify", len(falso.consultas) == antes)

        print("Erros com explicacao")
        falso.resposta_graphql = {"data": {"orders": {"nodes": [{"note": "x" * 70_000}]}}}
        erro, dados = loja(cliente, "{ orders(first: 250) { nodes { note } } }")
        confere("resposta enorme vira pedido de resumo", erro and "grande demais" in dados["erro"])
        falso.resposta_graphql = {"errors": [{"message": "Access denied for orders field.",
                                              "extensions": {"code": "ACCESS_DENIED"}}]}
        erro, dados = loja(cliente, "{ orders(first: 5) { nodes { name } } }")
        confere("ACCESS_DENIED do Shopify chega ao Claude",
                "ACCESS_DENIED" in json.dumps(dados), str(dados))
        shopify.esquecer_token()
        falso.erro_token = '{"error":"shop_not_permitted"}'
        erro, dados = loja(cliente, "{ shop { name } }")
        confere("shop_not_permitted explicado em portugues",
                erro and "mesma organizacao" in dados["erro"], str(dados))
    finally:
        shopify.httpx.post = post_original
        ligar_loja(False)

    print(f"\n{ok} verificacoes ok, {len(falhas)} falha(s)")
    if falhas:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
