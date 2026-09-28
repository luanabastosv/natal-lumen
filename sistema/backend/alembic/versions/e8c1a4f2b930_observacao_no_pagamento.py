"""observacao no pagamento

O que aconteceu naquele dinheiro e nao cabe em valor, data e forma: "pagou 200
e pediu para descontar da festa da irma", "veio junto com a doacao da empresa",
"comprovante ilegivel, confirmado por telefone".

`recebimentos` ja tinha o campo; `pagamentos` nao. Agora as duas origens da
lista do financeiro tem o mesmo espaco para explicar a linha.

Revision ID: e8c1a4f2b930
Revises: c47b3e9a1052
"""

import sqlalchemy as sa
from alembic import op

revision = "e8c1a4f2b930"
down_revision = "c47b3e9a1052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pagamentos", sa.Column("observacoes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("pagamentos", "observacoes")
