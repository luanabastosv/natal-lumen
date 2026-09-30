"""tokens de acesso: o prazo passa a ter fuso

Revision ID: e6b4f19d0a37
Revises: d5a1c73f2e88
Create Date: 2026-09-30 20:05:00.000000

`tokens_acesso.expira_em` era a unica data do sistema sem fuso. Um datetime com
fuso gravado nessa coluna vira a hora LOCAL do servidor, e e relido como se
fosse UTC — entao o prazo anda pelo tamanho do fuso.

Num servidor em UTC, que e o caso de teste e de producao hoje, os dois valores
coincidem e nada quebra. Num servidor no fuso de Sao Paulo, um link de
redefinicao de 2 horas nasce 1 hora no passado, e o de primeiro acesso perde 3
das 72 horas. O defeito estava latente, esperando alguem acertar o relogio do
servidor para o horario de Brasilia.

A conversao le os valores existentes como UTC, que e o que eles de fato sao nos
servidores atuais.
"""
import sqlalchemy as sa
from alembic import op

revision = "e6b4f19d0a37"
down_revision = "d5a1c73f2e88"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tokens_acesso "
        "ALTER COLUMN expira_em TYPE timestamptz USING expira_em AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tokens_acesso "
        "ALTER COLUMN expira_em TYPE timestamp USING expira_em AT TIME ZONE 'UTC'"
    )
