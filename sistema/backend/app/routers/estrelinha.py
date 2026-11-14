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
     `estrelinha` (migration e7a4c19b5d20). Ela nao alcanca as tabelas reais,
     entao nao ve contato, senha, comprovante nem nome de crianca.
  3. TRANSACAO SO DE LEITURA, com tempo maximo e limite de linhas.
"""

import hmac
import json
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import create_engine

from app.config import config

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
- Voce nao ve nomes de criancas nem contatos de padrinhos, e isso e de proposito.
  Se pedirem, explique que esses dados ficam so no sistema.
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


def _texto(dados: Any, erro: bool = False) -> dict[str, Any]:
    corpo = json.dumps(dados, ensure_ascii=False, default=str)
    return {"content": [{"type": "text", "text": corpo}], "isError": erro}


def _chamar_ferramenta(nome: str, argumentos: dict[str, Any]) -> dict[str, Any]:
    try:
        if nome == "ver_estrutura":
            return _texto(_ver_estrutura())
        if nome == "consultar":
            return _texto(_consultar(str(argumentos.get("sql", ""))))
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
            "instructions": INSTRUCOES,
        }
    elif metodo == "ping":
        resultado = {}
    elif metodo == "tools/list":
        resultado = {"tools": FERRAMENTAS}
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
    try:
        corpo = await request.json()
    except ValueError:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON invalido"}},
            status_code=400,
        )
    if isinstance(corpo, list):
        respostas = [r for m in corpo if isinstance(m, dict) and (r := _responder(m))]
        return JSONResponse(respostas) if respostas else Response(status_code=202)
    if not isinstance(corpo, dict):
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Pedido invalido"}},
            status_code=400,
        )
    resposta = _responder(corpo)
    return JSONResponse(resposta) if resposta else Response(status_code=202)


@router.get("/mcp")
def mcp_sem_stream(request: Request):
    """Sem SSE: o MCP manda responder 405 a quem tenta abrir o stream por GET."""
    _confere_token(request)
    return Response(status_code=405, headers={"Allow": "POST"})


@router.delete("/mcp")
def mcp_sem_sessao(request: Request):
    _confere_token(request)
    return Response(status_code=405, headers={"Allow": "POST"})
