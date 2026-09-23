"""Encerramento de sessoes antes de o token expirar.

O JWT se valida sozinho, sem tocar na base — rapido, mas significa que um
logout nao o invalidava. Aqui fica a excecao: a lista dos encerrados.
"""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import SessaoRevogada
from app.seguranca.sessao import Sessao


def revogar(db: Session, sessao: Sessao) -> None:
    """Encerra este token. Guardado so ate a data em que ele expiraria."""
    ja_esta = db.scalar(select(SessaoRevogada).where(SessaoRevogada.jti == sessao.jti))
    if ja_esta:
        return

    db.add(
        SessaoRevogada(
            jti=sessao.jti,
            usuario_id=sessao.usuario_id,
            expira_em=sessao.expira_em,
        )
    )
    _limpar_expiradas(db)


def esta_revogada(db: Session, sessao: Sessao) -> bool:
    return db.scalar(
        select(SessaoRevogada.id).where(SessaoRevogada.jti == sessao.jti)
    ) is not None


def _limpar_expiradas(db: Session) -> None:
    """Tira da lista os tokens que ja expiraram sozinhos.

    Feito no logout, que e raro: a tabela nunca cresce sem limite, e nao e
    preciso agendar tarefa nenhuma.
    """
    db.execute(delete(SessaoRevogada).where(SessaoRevogada.expira_em < datetime.now(UTC)))
