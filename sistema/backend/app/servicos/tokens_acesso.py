"""Tokens de uso unico para primeiro acesso e redefinicao de senha.

O valor em claro so existe no link entregue ao voluntario; na base fica apenas
o hash. Se a base vazar, os links nao sao reconstituiveis.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import config
from app.models import TokenAcesso, Usuario
from app.models.tipos import TipoToken


def _hash(token: str) -> str:
    """SHA-256 basta: o token ja e aleatorio e de vida curta.

    (Argon2 existe para proteger senhas escolhidas por pessoas, que sao
    adivinhaveis; um token de 32 bytes aleatorios nao e.)
    """
    return hashlib.sha256(token.encode()).hexdigest()


def gerar(
    db: Session,
    usuario: Usuario,
    tipo: TipoToken = TipoToken.PRIMEIRO_ACESSO,
    *,
    horas: int | None = None,
) -> str:
    """Cria o token e devolve o valor em claro (unica vez que ele existe).

    Invalida os tokens anteriores do mesmo tipo: pedir um link novo derruba o
    antigo.
    """
    pendentes = db.scalars(
        select(TokenAcesso).where(
            TokenAcesso.usuario_id == usuario.id,
            TokenAcesso.tipo == tipo.value,
            TokenAcesso.usado_em.is_(None),
        )
    ).all()
    agora = datetime.now(UTC)
    for antigo in pendentes:
        antigo.usado_em = agora

    token = secrets.token_urlsafe(32)
    validade = horas if horas is not None else config.token_primeiro_acesso_horas

    db.add(
        TokenAcesso(
            usuario_id=usuario.id,
            token_hash=_hash(token),
            tipo=tipo.value,
            expira_em=agora + timedelta(hours=validade),
        )
    )
    return token


def validar(db: Session, token: str) -> TokenAcesso | None:
    """Devolve o token se existir, nao tiver sido usado e nao estiver expirado."""
    registro = db.scalar(
        select(TokenAcesso).where(TokenAcesso.token_hash == _hash(token))
    )
    if registro is None or registro.usado_em is not None:
        return None

    expira_em = registro.expira_em
    if expira_em.tzinfo is None:
        expira_em = expira_em.replace(tzinfo=UTC)

    if expira_em < datetime.now(UTC):
        return None

    return registro


def consumir(registro: TokenAcesso) -> None:
    """Marca como usado. De uso unico: nao serve uma segunda vez."""
    registro.usado_em = datetime.now(UTC)
