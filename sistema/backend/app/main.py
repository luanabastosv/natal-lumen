"""API do sistema Natal Lumen.

Publicada em https://DOMINIO/acesso/api — dai o root_path, que faz o FastAPI
montar os links e a documentacao com o prefixo certo atras do servidor web.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.routers import auth, cidades, criancas, edicoes, instituicoes, perfis, usuarios

app = FastAPI(
    title="Sistema Natal Lumen",
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
    cidades.router,
    criancas.router,
    edicoes.router,
    instituicoes.router,
    perfis.router,
    usuarios.router,
):
    app.include_router(router)


@app.get("/saude", tags=["infra"])
def saude():
    """Usada para conferir que a API esta de pe."""
    return {"ok": True, "ambiente": config.ambiente}
