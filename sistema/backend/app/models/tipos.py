"""Tipos e valores fixos compartilhados pelos modelos.

Os conjuntos fechados (tipo de apadrinhamento, status de cartao...) sao gravados
como texto com CHECK, e nao como ENUM nativo do PostgreSQL: acrescentar um valor
novo passa a ser uma migration simples de CHECK, sem ALTER TYPE.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import mapped_column


class TipoApadrinhamento(StrEnum):
    CESTA = "cesta"
    FESTA = "festa"


class StatusCartao(StrEnum):
    DIGITALIZADO = "digitalizado"
    ENVIADO = "enviado"


class StatusKit(StrEnum):
    PENDENTE = "pendente"
    MONTADO = "montado"
    ENTREGUE = "entregue"


class TipoToken(StrEnum):
    PRIMEIRO_ACESSO = "primeiro_acesso"
    REDEFINIR_SENHA = "redefinir_senha"


class Sexo(StrEnum):
    MASCULINO = "M"
    FEMININO = "F"


def valores(enum: type[StrEnum]) -> tuple[str, ...]:
    """Valores do enum, para montar o CHECK da coluna."""
    return tuple(item.value for item in enum)


# Colunas reutilizadas em varios modelos.
# Dinheiro sempre em Numeric — nunca Float, que arredonda centavos.
Dinheiro = Annotated[float, mapped_column(Numeric(10, 2))]

CriadoEm = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False),
]

MomentoOpcional = Annotated[
    datetime | None,
    mapped_column(DateTime(timezone=True), nullable=True),
]

Texto = Annotated[str, mapped_column(String(160))]
