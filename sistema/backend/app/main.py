"""API do sistema Natal Lumen.

Publicada em https://DOMINIO/acesso/api — dai o root_path, que faz o FastAPI
montar os links e a documentacao com o prefixo certo atras do servidor web.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import config
from app.database import engine
from app.routers import (
    auth,
    autorizacoes,
    cartoes,
    cidades,
    criancas,
    cuidados,
    edicoes,
    financeiro,
    grupos,
    instituicoes,
    lembretes,
    logistica,
    monitoria,
    oracao,
    padrinhos,
    painel,
    perfis,
    usuarios,
)

@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # Nao ha mais nada pesado para aquecer: o EasyOCR saiu, e o que sobrou do
    # scanner e OpenCV puro, que custa ~1 ms por cartao.
    config.caminho_arquivos.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Sistema Natal Lumen",
    lifespan=ciclo_de_vida,
    root_path=config.root_path,
    docs_url="/docs" if not config.em_producao else None,
    redoc_url=None,
)

# Em producao o frontend e servido do mesmo dominio: nao ha pedido entre origens,
# e origens_permitidas vem vazia. O CORS existe so para o Vite em localhost.
if config.origens_permitidas:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.origens_permitidas,
        allow_credentials=True,  # necessario para o cookie da sessao viajar
        allow_methods=["*"],
        allow_headers=["*"],
    )

for router in (
    auth.router,
    autorizacoes.router,
    cartoes.router,
    cidades.router,
    criancas.router,
    cuidados.router,
    edicoes.router,
    financeiro.router,
    grupos.router,
    instituicoes.router,
    lembretes.router,
    logistica.router,
    monitoria.router,
    oracao.router,
    padrinhos.router,
    painel.router,
    perfis.router,
    usuarios.router,
):
    app.include_router(router)


@app.get("/saude", tags=["infra"])
def saude():
    """Usada para conferir que o sistema esta de pe — a API E o banco.

    E o endereco que o monitor externo (UptimeRobot) visita a cada 5 minutos,
    e que o publicar.sh confere depois de reiniciar. So a API respondendo nao
    basta: com o Postgres parado a API sobe, responde aqui, e toda tela da
    erro. Por isso a consulta ao banco, e o 503 quando ela falha — e o 503 que
    dispara o aviso.
    """
    try:
        with engine.connect() as conexao:
            conexao.execute(text("select 1"))
    except Exception:
        return JSONResponse(
            {"ok": False, "ambiente": config.ambiente, "banco": "sem resposta"},
            status_code=503,
        )
    return {"ok": True, "ambiente": config.ambiente}
