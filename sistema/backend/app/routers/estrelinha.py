"""Estrelinha: conector MCP para a coordenacao perguntar ao Claude sobre os dados.

Endereco publico: https://acesso.natallumen.com/acesso/api/estrelinha/mcp?key=TOKEN
(o nginx tira o /acesso/api, e a aplicacao atende /estrelinha/mcp).

E um servidor MCP minimo, sem estado e so com respostas JSON (o transporte
"Streamable HTTP" do MCP permite isso): cada POST traz uma mensagem JSON-RPC e
recebe a resposta na hora. Sem sessao, sem SSE e sem dependencia nova.

Seguranca, em camadas, e nenhuma depende do Claude se comportar:
  1. TOKEN: sem ESTRELINHA_TOKEN no .env a rota nem existe (404). Com ele,
     quem nao manda o token certo leva 401.
  2. USUARIA PROPRIA: as consultas usam ESTRELINHA_DATABASE_URL, da usuaria
     `estrelinha` do Postgres, que so tem SELECT nas views do schema
     `estrelinha` (migration a3f9d27c6e18). As views mostram todos os dados do
     evento, menos senha e tokens de acesso.
  3. TRANSACAO SO DE LEITURA, com tempo maximo e limite de linhas.

A lojinha do Shopify entra pela ferramenta `consultar_loja` (app/servicos/
shopify.py), que so aparece com as credenciais SHOPIFY_* no .env. Assim a
coordenacao le as vendas da loja sem precisar de conta no Shopify.

O sorrisometro entra pela ferramenta `gerar_sorrisometro` (app/servicos/
sorrisometro.py): conta os apadrinhamentos de cesta e de festa pela mesma
usuaria so de leitura, desenha a arte de feed e de stories e devolve os links.
Os PNGs saem por GET /estrelinha/sorrisometro/{nome}, sem token: o link vai
para o Instagram. Ver a nota em app/servicos/sorrisometro.py.
"""

import base64
import hmac
import json
from contextvars import ContextVar
from functools import lru_cache
from io import BytesIO
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import create_engine
from starlette.concurrency import run_in_threadpool

from app.config import config
from app.servicos import shopify, sorrisometro

router = APIRouter(prefix="/estrelinha", tags=["estrelinha"], include_in_schema=False)

LIMITE_LINHAS = 500
TEMPO_MAXIMO = "15s"
VERSAO_PADRAO = "2025-06-18"

INSTRUCOES = """\
Voce e a Estrelinha, a assistente de dados do Natal Lumen: um evento anual de Natal
para criancas de comunidades e instituicoes, em que cada crianca ganha um padrinho.
Responda em portugues, de forma calorosa e direta, sempre com o numero primeiro.

Como consultar:
- Use `ver_estrutura` para ver as views e colunas, e `consultar` para rodar SQL
  (PostgreSQL, somente SELECT/WITH) sobre elas. Os dados sao ao vivo.
- Uma EDICAO e uma cidade num ano (tabela edicoes: ano, nome, cidade). Quase toda
  pergunta e sobre uma edicao: filtre por edicao_id. "Este ano" e a edicao do ano
  corrente (ou a com ativa = true); "ano passado" e ano - 1. Se houver mais de uma
  edicao no mesmo ano, pergunte qual ou mostre separado.
- criancas.idade e a idade informada na lista daquela edicao.
- Uma crianca pode ter apadrinhamento de tipo 'cesta' e de tipo 'festa'.
  "Apadrinhada" = tem ao menos um apadrinhamento; diga qual tipo contou.
- Datas e horas estao em UTC. Para "hoje", "ontem" etc., converta:
  (criado_em at time zone 'America/Fortaleza')::date. Hoje e
  (now() at time zone 'America/Fortaleza')::date.
- criancas.desistiu_em preenchido = desistiu; checkin_em = chegou no evento;
  falta_em = faltou.
- Prefira contagens e agrupamentos (count, group by). Mostre no maximo uma
  tabela curta. Se a consulta der erro, leia a mensagem, corrija e tente de novo.
- Voce ve todos os dados do evento, inclusive nomes de criancas, contatos e
  observacoes, porque so a coordenacao usa a Estrelinha. Mesmo assim, mostre
  nomes e contatos so quando a pergunta pedir; para o resto, responda com numeros.
- Senhas e tokens de acesso nao estao nas views, e isso e de proposito.

SORRISOMETRO (arte de progresso para o Instagram):
- Quando pedirem o sorrisometro, use `gerar_sorrisometro`. Ela mesma conta os
  apadrinhamentos de cesta e de festa ao vivo (criancas ativas, sem desistentes)
  sobre um total fixo de 1500, e desenha feed (1080x1350) e stories (1080x1920),
  em fundo azul e amarelo. Sem pedido especifico, gere as quatro.
- A ferramenta devolve cada arte inteira como imagem (1080 px), na ordem da
  lista `artes`. Se voce consegue enviar arquivos para a pessoa, envie as
  imagens como arquivo. Sempre responda tambem com os numeros (cesta e festa) e
  os links dos PNGs, um por linha, dizendo formato e fundo de cada um. Os links
  sao publicos e valem 60 dias.
- So mude o total se a pessoa pedir outro numero.
"""

INSTRUCOES_LOJA = """
A LOJINHA (Shopify):
- Os produtos do Natal Lumen tambem sao vendidos numa loja no Shopify, fora do
  banco do sistema. Para vendas, pedidos, produtos e estoque da loja, use
  `consultar_loja` (GraphQL da Admin API do Shopify, so leitura). Nao procure
  esses dados nas views do banco.
- Para totais e rankings (faturamento, unidades por produto, vendas por dia),
  prefira o ShopifyQL, que ja agrega e cobre todo o historico:
    { shopifyqlQuery(query: "FROM sales SHOW net_sales, net_items_sold
      GROUP BY product_title SINCE -30d ORDER BY net_sales DESC") {
      tableData { columns { name dataType } rows } parseErrors } }
  Datas no ShopifyQL: SINCE -7d, SINCE 2026-11-01 UNTIL today, TIMESERIES day.
  Se vier parseErrors, corrija a consulta e tente de novo.
- Para pedidos um a um use `orders(first: 50, query: "created_at:>=2026-11-01")`,
  com `pageInfo` para paginar. A lista de pedidos so alcanca os ultimos 60 dias.
- Valores vem como texto em `amount` + `currencyCode` (BRL). Some e formate
  como R$. Horarios vem em UTC: converta para Fortaleza (UTC-3).
- Se vier ACCESS_DENIED, diga que a loja nao liberou esse dado para a Estrelinha
  e qual campo foi; nao insista com o mesmo campo.
- Dados de clientes (nome, email, endereco) so quando a pergunta pedir.
"""

FERRAMENTAS = [
    {
        "name": "ver_estrutura",
        "description": (
            "Lista as views do Natal Lumen que a Estrelinha pode consultar, com as "
            "colunas e tipos. Use antes de montar uma consulta."
        ),
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "consultar",
        "description": (
            "Executa UMA consulta SELECT (ou WITH) somente leitura, ao vivo, sobre as "
            "views do Natal Lumen. Datas em UTC: para dias locais use "
            "at time zone 'America/Fortaleza'. Retorna no maximo "
            f"{LIMITE_LINHAS} linhas; prefira agregacoes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "Consulta PostgreSQL"}},
            "required": ["sql"],
        },
        "annotations": {"readOnlyHint": True},
    },
]

FERRAMENTA_SORRISOMETRO = {
    "name": "gerar_sorrisometro",
    "description": (
        "Gera a arte do sorrisometro (progresso dos apadrinhamentos de cesta e de "
        "festa) com os numeros ao vivo, em feed e/ou stories e fundo azul e/ou "
        "amarelo. Devolve as contagens, os links publicos dos PNGs e uma previa. "
        "Sem edicao_id, usa a edicao de Fortaleza do ano corrente."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "formato": {"type": "string", "enum": ["feed", "stories", "todos"], "default": "todos"},
            "fundo": {"type": "string", "enum": ["azul", "amarelo", "todos"], "default": "todos"},
            "total": {"type": "integer", "description": "Meta do topo da arte (padrao 1500)", "default": 1500},
            "edicao_id": {"type": "integer", "description": "Edicao a contar (opcional)"},
        },
    },
    "annotations": {"readOnlyHint": True},
}

FERRAMENTA_LOJA = {
    "name": "consultar_loja",
    "description": (
        "Le a lojinha do Natal Lumen no Shopify: vendas, pedidos, produtos e "
        "estoque, ao vivo. Recebe UMA consulta GraphQL da Admin API do Shopify "
        "(somente query; mutation e recusada). Para totais e rankings de vendas, "
        "use shopifyqlQuery. Retorna data e, se houver, errors do Shopify."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "graphql": {"type": "string", "description": "Consulta GraphQL (query)"},
            "variaveis": {"type": "object", "description": "Variaveis da consulta, se usar"},
        },
        "required": ["graphql"],
    },
    "annotations": {"readOnlyHint": True, "openWorldHint": True},
}


def _ferramentas() -> list[dict[str, Any]]:
    return FERRAMENTAS + [FERRAMENTA_SORRISOMETRO] + ([FERRAMENTA_LOJA] if shopify.configurado() else [])


def _instrucoes() -> str:
    return INSTRUCOES + (INSTRUCOES_LOJA if shopify.configurado() else "")


@lru_cache
def _engine():
    return create_engine(config.estrelinha_database_url, pool_pre_ping=True, pool_size=2)


def _rodar(sql: str) -> list[dict[str, Any]]:
    """Roda a consulta numa transacao so de leitura, com tempo e linhas limitados.

    Usa o cursor do psycopg direto, sem parametros: assim `::date`, `%` e `:`
    dentro do SQL do Claude nao viram marcadores de parametro.
    """
    with _engine().connect() as conexao:
        cursor = conexao.connection.cursor()
        try:
            cursor.execute("set transaction read only")
            cursor.execute(f"set local statement_timeout = '{TEMPO_MAXIMO}'")
            cursor.execute("set local search_path = estrelinha")
            cursor.execute(f"select * from (\n{sql}\n) as consulta limit {LIMITE_LINHAS}")
            colunas = [c.name for c in cursor.description or []]
            return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
        finally:
            cursor.close()
            conexao.rollback()


def _ver_estrutura() -> list[dict[str, Any]]:
    return _rodar(
        "select table_name as view, column_name as coluna, data_type as tipo "
        "from information_schema.columns where table_schema = 'estrelinha' "
        "order by table_name, ordinal_position"
    )


def _consultar(sql: str) -> list[dict[str, Any]]:
    sql = sql.strip().rstrip(";").strip()
    primeira = sql.split(None, 1)[0].lower() if sql else ""
    if primeira not in ("select", "with") or ";" in sql:
        raise ValueError("So e permitida uma unica consulta SELECT ou WITH.")
    return _rodar(sql)


CONTAGEM_SORRISOMETRO = """
with ed as (
  select e.id, e.nome, e.ano from edicoes e
  where {filtro}
  order by (e.nome ilike '%fortaleza%') desc, e.ativa desc, e.id desc
  limit 1
),
c as (
  select c.id,
    exists(select 1 from apadrinhamentos a where a.crianca_id = c.id and a.tipo = 'cesta') as tem_cesta,
    exists(select 1 from apadrinhamentos a where a.crianca_id = c.id and a.tipo = 'festa') as tem_festa
  from criancas c join ed on ed.id = c.edicao_id
  where c.desistiu_em is null
)
select ed.id as edicao_id, ed.nome as edicao,
  (select count(*) from c) as criancas,
  (select count(*) from c where tem_cesta) as cesta,
  (select count(*) from c where tem_festa) as festa
from ed
"""


# Endereco de quem chamou (https://acesso.natallumen.com), para o link sair
# completo mesmo sem URL_PUBLICA no .env. Preenchido em mcp(), a cada pedido.
_endereco: ContextVar[str] = ContextVar("endereco", default="")


def _url_publica(nome: str) -> str:
    caminho = f"{config.root_path}/estrelinha/sorrisometro/{nome}"
    base = config.url_publica.rstrip("/") or _endereco.get()
    return f"{base}{caminho}"


def _gerar_sorrisometro(argumentos: dict[str, Any]) -> dict[str, Any]:
    formato = str(argumentos.get("formato") or "todos")
    fundo = str(argumentos.get("fundo") or "todos")
    total = int(argumentos.get("total") or 1500)
    formatos = sorrisometro.FORMATOS if formato == "todos" else (formato,)
    fundos = sorrisometro.FUNDOS if fundo == "todos" else (fundo,)
    if any(f not in sorrisometro.FORMATOS for f in formatos) or any(b not in sorrisometro.FUNDOS for b in fundos):
        raise ValueError("formato: feed, stories ou todos; fundo: azul, amarelo ou todos.")
    if not 0 < total <= 100000:
        raise ValueError("O total precisa estar entre 1 e 100000.")

    edicao_id = argumentos.get("edicao_id")
    filtro = (
        f"e.id = {int(edicao_id)}" if edicao_id is not None
        else "e.ano = extract(year from now() at time zone 'America/Fortaleza')::int"
    )
    linhas = _rodar(CONTAGEM_SORRISOMETRO.format(filtro=filtro))
    if not linhas:
        raise ValueError("Nao achei a edicao. Passe edicao_id (veja a view edicoes).")
    n = linhas[0]

    sorrisometro.limpar_antigos()
    artes, previas = [], []
    for f in formatos:
        for b in fundos:
            img = sorrisometro.desenhar(int(n["cesta"]), int(n["festa"]), total, f, b)
            nome = sorrisometro.salvar(img, f, b)
            artes.append({"formato": f, "fundo": b, "link": _url_publica(nome)})
            # A arte inteira (1080 px), em JPEG para a resposta nao pesar: o
            # Claude consegue entregar como arquivo, e o PNG fica no link.
            buf = BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=92)
            previas.append({"type": "image", "mimeType": "image/jpeg",
                            "data": base64.b64encode(buf.getvalue()).decode()})
    dados = {
        "edicao": n["edicao"], "edicao_id": n["edicao_id"], "total_da_arte": total,
        "cesta": n["cesta"], "festa": n["festa"], "criancas_ativas": n["criancas"],
        "artes": artes,
    }
    corpo = json.dumps(dados, ensure_ascii=False, default=str)
    return {"content": [{"type": "text", "text": corpo}, *previas], "isError": False}


def _texto(dados: Any, erro: bool = False) -> dict[str, Any]:
    corpo = json.dumps(dados, ensure_ascii=False, default=str)
    return {"content": [{"type": "text", "text": corpo}], "isError": erro}


def _chamar_ferramenta(nome: str, argumentos: dict[str, Any]) -> dict[str, Any]:
    try:
        if nome == "ver_estrutura":
            return _texto(_ver_estrutura())
        if nome == "consultar":
            return _texto(_consultar(str(argumentos.get("sql", ""))))
        if nome == "gerar_sorrisometro":
            return _gerar_sorrisometro(argumentos)
        if nome == "consultar_loja" and shopify.configurado():
            variaveis = argumentos.get("variaveis")
            return _texto(shopify.consultar(
                str(argumentos.get("graphql", "")),
                variaveis if isinstance(variaveis, dict) else None,
            ))
    except Exception as erro:  # o Claude le o erro e corrige a consulta
        return _texto({"erro": str(erro).strip()}, erro=True)
    return _texto({"erro": f"Ferramenta desconhecida: {nome}"}, erro=True)


def _responder(mensagem: dict[str, Any]) -> dict[str, Any] | None:
    metodo = mensagem.get("method")
    ident = mensagem.get("id")
    params = mensagem.get("params") or {}

    if ident is None:  # notificacao (ex.: notifications/initialized): sem resposta
        return None
    if metodo == "initialize":
        resultado = {
            "protocolVersion": params.get("protocolVersion") or VERSAO_PADRAO,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "estrelinha", "title": "Estrelinha ⭐", "version": "1.0.0"},
            "instructions": _instrucoes(),
        }
    elif metodo == "ping":
        resultado = {}
    elif metodo == "tools/list":
        resultado = {"tools": _ferramentas()}
    elif metodo == "tools/call":
        resultado = _chamar_ferramenta(params.get("name", ""), params.get("arguments") or {})
    else:
        return {
            "jsonrpc": "2.0",
            "id": ident,
            "error": {"code": -32601, "message": f"Metodo nao suportado: {metodo}"},
        }
    return {"jsonrpc": "2.0", "id": ident, "result": resultado}


def _confere_token(request: Request) -> None:
    esperado = config.estrelinha_token
    if not esperado or not config.estrelinha_database_url:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    recebido = request.query_params.get("key", "")
    cabecalho = request.headers.get("authorization", "")
    if cabecalho.lower().startswith("bearer "):
        recebido = cabecalho[7:].strip()
    if not hmac.compare_digest(recebido.encode(), esperado.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido")


@router.post("/mcp")
async def mcp(request: Request):
    _confere_token(request)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    esquema = "http" if host.startswith(("localhost", "127.0.0.1", "testserver")) else "https"
    _endereco.set(f"{esquema}://{host.split(',')[0].strip()}" if host else "")
    try:
        corpo = await request.json()
    except ValueError:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON invalido"}},
            status_code=400,
        )
    # As ferramentas esperam o banco ou o Shopify: fora do loop de eventos,
    # para uma consulta lenta nao segurar o resto da API.
    if isinstance(corpo, list):
        respostas = [
            r for m in corpo if isinstance(m, dict) and (r := await run_in_threadpool(_responder, m))
        ]
        return JSONResponse(respostas) if respostas else Response(status_code=202)
    if not isinstance(corpo, dict):
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Pedido invalido"}},
            status_code=400,
        )
    resposta = await run_in_threadpool(_responder, corpo)
    return JSONResponse(resposta) if resposta else Response(status_code=202)


@router.get("/mcp")
def mcp_sem_stream(request: Request):
    """Sem SSE: o MCP manda responder 405 a quem tenta abrir o stream por GET."""
    _confere_token(request)
    return Response(status_code=405, headers={"Allow": "POST"})


@router.get("/sorrisometro/{nome}")
def sorrisometro_publicado(nome: str):
    """A arte gerada pela Estrelinha, sem token (o link vai para o Instagram).

    Com a Estrelinha desligada, nao existe. So serve nomes no formato do
    sorrisometro, de dentro da pasta dele.
    """
    if not config.estrelinha_token or not config.estrelinha_database_url:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    arquivo = sorrisometro.caminho_publicado(nome)
    if arquivo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return FileResponse(arquivo, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})


@router.delete("/mcp")
def mcp_sem_sessao(request: Request):
    _confere_token(request)
    return Response(status_code=405, headers={"Allow": "POST"})
