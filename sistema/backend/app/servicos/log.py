"""Registro de acoes sensiveis em log_atividades (LGPD)."""

from typing import Any

from sqlalchemy.orm import Session

from app.models import LogAtividade


def registrar(
    db: Session,
    acao: str,
    *,
    usuario_id: int | None = None,
    tabela: str | None = None,
    registro_id: int | None = None,
    detalhes: dict[str, Any] | None = None,
) -> None:
    """Acrescenta uma linha ao log.

    Nao faz commit: entra na mesma transacao da acao que esta sendo registrada,
    para nunca existir log de algo que acabou desfeito (nem o contrario).

    usuario_id e opcional porque tentativas de login com email inexistente
    tambem precisam ser registradas.
    """
    db.add(
        LogAtividade(
            usuario_id=usuario_id,
            acao=acao,
            tabela=tabela,
            registro_id=registro_id,
            detalhes=detalhes,
        )
    )
