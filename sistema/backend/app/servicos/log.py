"""Registro de acoes sensiveis em log_atividades (LGPD)."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
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


def _para_json(valor: Any) -> Any:
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    return str(valor)


def valores(registro: Any, campos) -> dict[str, Any]:
    """Os valores de `campos` em `registro`, prontos para o JSON do log.

    Chamado duas vezes numa edicao — antes e depois de aplicar a mudanca — para
    o log guardar o "antes" e o "depois". So o nome do campo, que era o que se
    guardava, dizia que alguem mudou a idade; nao dizia de quanto para quanto, e
    desfazer um engano exigia voltar o backup da madrugada inteiro.
    """
    return {campo: _para_json(getattr(registro, campo, None)) for campo in sorted(campos)}
