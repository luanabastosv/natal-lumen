"""Sessao em JWT, guardada num cookie httpOnly.

O token nunca vai para o localStorage: fica so no cookie, que o JavaScript da
pagina nao consegue ler. O cookie usa path=/acesso e SameSite=Strict, possivel
porque o frontend e a API vivem no mesmo dominio.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Response

from app.config import config


@dataclass(frozen=True)
class Sessao:
    usuario_id: int
    csrf: str
    expira_em: datetime
    # Identificador deste token. E o que permite encerra-lo antes da hora.
    jti: str


def criar_token(usuario_id: int) -> tuple[str, str]:
    """Devolve (token, csrf). O csrf viaja dentro do proprio token."""
    agora = datetime.now(UTC)
    csrf = secrets.token_urlsafe(32)

    payload = {
        "sub": str(usuario_id),
        "csrf": csrf,
        "jti": secrets.token_urlsafe(24),
        "iat": agora,
        "exp": agora + timedelta(hours=config.sessao_horas),
    }
    token = jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algoritmo)
    return token, csrf


def ler_token(token: str) -> Sessao | None:
    """Decodifica e valida o token. None se invalido ou expirado."""
    try:
        payload = jwt.decode(token, config.jwt_secret, algorithms=[config.jwt_algoritmo])
        return Sessao(
            usuario_id=int(payload["sub"]),
            csrf=payload["csrf"],
            expira_em=datetime.fromtimestamp(payload["exp"], UTC),
            jti=payload["jti"],
        )
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None


def perto_de_expirar(sessao: Sessao) -> bool:
    """Se falta pouco para o token expirar, vale renova-lo.

    E o que deixa a sessao ser curta sem incomodar: quem esta usando o sistema
    ganha um token novo sozinho; quem parou, expira.
    """
    falta = sessao.expira_em - datetime.now(UTC)
    return falta < timedelta(minutes=config.renovar_faltando_minutos)


def gravar_cookies(resposta: Response, token: str, csrf: str) -> None:
    """Grava o cookie da sessao (httpOnly) e o do CSRF (legivel pelo frontend)."""
    comum = {
        "path": config.cookie_path,
        "secure": config.cookie_secure,
        "samesite": "strict",
        "max_age": config.sessao_horas * 3600,
    }

    resposta.set_cookie(config.cookie_nome, token, httponly=True, **comum)

    # Este precisa ser legivel: o frontend copia o valor para o cabecalho
    # X-CSRF-Token a cada pedido que altera dados.
    resposta.set_cookie(config.cookie_csrf, csrf, httponly=False, **comum)


def apagar_cookies(resposta: Response) -> None:
    for nome in (config.cookie_nome, config.cookie_csrf):
        resposta.delete_cookie(
            nome,
            path=config.cookie_path,
            secure=config.cookie_secure,
            samesite="strict",
        )
