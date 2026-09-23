"""Dependencias do FastAPI para autenticacao e autorizacao.

Toda rota que mexe em dados declara a permissao que exige, por exemplo:

    @router.post("/cartoes")
    def subir(ctx: Contexto = Depends(exige_permissao("subir_cartoes"))):
        ...

O frontend apenas esconde menus; quem decide e sempre isto aqui.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import config
from app.database import get_db
from app.models import Usuario
from app.seguranca.contexto import ContextoAcesso, montar_contexto
from app.seguranca.sessao import criar_token, gravar_cookies, ler_token, perto_de_expirar
from app.servicos.sessoes import esta_revogada

METODOS_QUE_ALTERAM = {"POST", "PUT", "PATCH", "DELETE"}

NAO_AUTENTICADO = HTTPException(
    status.HTTP_401_UNAUTHORIZED, "Sessao ausente ou expirada."
)


def usuario_atual(
    request: Request,
    resposta: Response,
    db: Annotated[Session, Depends(get_db)],
) -> Usuario:
    """Le a sessao do cookie httpOnly e devolve o usuario."""
    token = request.cookies.get(config.cookie_nome)
    if not token:
        raise NAO_AUTENTICADO

    sessao = ler_token(token)
    if sessao is None:
        raise NAO_AUTENTICADO

    # Encerrada por um logout, mesmo que o token ainda nao tenha expirado.
    if esta_revogada(db, sessao):
        raise NAO_AUTENTICADO

    usuario = db.get(Usuario, sessao.usuario_id)
    if usuario is None or not usuario.ativo:
        raise NAO_AUTENTICADO

    # Quem esta usando o sistema ganha um token novo antes de o atual expirar.
    # E o que permite a sessao ser curta sem obrigar a entrar de novo no meio
    # do trabalho.
    if perto_de_expirar(sessao):
        novo_token, novo_csrf = criar_token(usuario.id)
        gravar_cookies(resposta, novo_token, novo_csrf)
        # O CSRF muda junto; o cabecalho do pedido ATUAL ainda e o antigo.
        request.state.csrf_da_sessao = sessao.csrf
        return usuario

    # O CSRF do token e comparado com o cabecalho nos metodos que alteram dados.
    request.state.csrf_da_sessao = sessao.csrf
    return usuario


def exige_csrf(request: Request) -> None:
    """Confere o token CSRF nos metodos que alteram dados.

    O cookie da sessao ja usa SameSite=Strict, o que por si so barra o pedido
    vindo de outro site. Isto e a segunda tranca: o frontend copia o cookie
    legivel nl_csrf para o cabecalho X-CSRF-Token, e o valor tem de bater com o
    que esta dentro do JWT — que um site de terceiros nao consegue ler.
    """
    if request.method not in METODOS_QUE_ALTERAM:
        return

    esperado = getattr(request.state, "csrf_da_sessao", None)
    enviado = request.headers.get("X-CSRF-Token")

    if not esperado or not enviado or enviado != esperado:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Token CSRF ausente ou invalido.")


def contexto_atual(
    usuario: Annotated[Usuario, Depends(usuario_atual)],
    db: Annotated[Session, Depends(get_db)],
    _csrf: Annotated[None, Depends(exige_csrf)] = None,
) -> ContextoAcesso:
    """Usuario + vinculos ativos, com CSRF ja conferido."""
    return montar_contexto(db, usuario)


Contexto = Annotated[ContextoAcesso, Depends(contexto_atual)]
BD = Annotated[Session, Depends(get_db)]


def exige_permissao(codigo: str):
    """Dependencia que exige a permissao em pelo menos uma edicao do usuario.

    E o portao de entrada da rota. O recorte fino — QUAIS edicoes e quais
    instituicoes — e feito depois, pelos filtros do contexto.
    """

    def verificar(ctx: Contexto) -> ContextoAcesso:
        if not ctx.pode(codigo):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Voce nao tem a permissao necessaria ({codigo}).",
            )
        return ctx

    return verificar


def exige_admin_geral(ctx: Contexto) -> ContextoAcesso:
    """So o admin_geral cria cidades, edicoes e coordenadores de cidade."""
    if not ctx.admin_geral:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Acao restrita a administracao geral."
        )
    return ctx
