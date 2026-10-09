"""nomes da montagem e da conferencia

Revision ID: d2f6b8a40c19
Revises: c7a3e9d15b20
Create Date: 2026-10-09 12:00:00.000000

Quem monta e confere os kits e voluntario do dia, sem conta no sistema: a
"Montagem + Conferencia" da instituicao grava os nomes como texto.
"""
from alembic import op
import sqlalchemy as sa

revision = "d2f6b8a40c19"
down_revision = "c7a3e9d15b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kits", sa.Column("montado_por_nome", sa.String(length=120), nullable=True))
    op.add_column("kits", sa.Column("conferido_por_nome", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("kits", "conferido_por_nome")
    op.drop_column("kits", "montado_por_nome")
