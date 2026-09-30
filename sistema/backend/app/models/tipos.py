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
    """Dois estados, e nao tres.

    Havia um "entregue", marcado no dia do evento. Saiu em 30/09/2026 por
    decisao da coordenacao: o kit e trabalho da equipe de estrutura na semana
    anterior, e o que ela precisa registrar e se montou ou nao. A entrega no dia
    quem acompanha e o check-in da crianca.
    """

    PENDENTE = "pendente"
    MONTADO = "montado"


class CategoriaRecebimento(StrEnum):
    """Categorias GRAVADAS em recebimentos — as duas que alguem escolhe.

    As de apadrinhamento nao estao aqui de proposito: elas nao sao escolhidas,
    sao DERIVADAS do que o pagamento quita (so cesta, so festa, ou os dois).
    Guardar a categoria de um pagamento ao lado dos apadrinhamentos que ele
    quita abriria a porta para as duas divergirem — uma linha dizendo "cesta"
    num dinheiro que pagou festa. Os rotulos das derivadas vivem no router do
    financeiro, que e quem as calcula.
    """

    DOACAO = "doacao"
    OUTROS = "outros"


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

# Instante obrigatorio, COM fuso. Existe para nenhum instante do sistema ficar
# sem ele: um `datetime` sem fuso vai para o banco como a hora LOCAL do
# servidor, e volta como se fosse UTC. Num servidor em UTC isso passa
# despercebido; num servidor no fuso de Sao Paulo, um prazo de duas horas nasce
# uma hora no passado.
Momento = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), nullable=False),
]

Texto = Annotated[str, mapped_column(String(160))]
