"""observacao do comissario

Revision ID: c7a3e9d15b20
Revises: b4e1d8a2c7f3
Create Date: 2026-10-08 23:00:00.000000

O recado do comissario sobre a crianca, separado da observacao que chega da
lista da instituicao.
"""
from alembic import op
import sqlalchemy as sa

revision = "c7a3e9d15b20"
down_revision = "b4e1d8a2c7f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("criancas", sa.Column("observacao_comissario", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("criancas", "observacao_comissario")
