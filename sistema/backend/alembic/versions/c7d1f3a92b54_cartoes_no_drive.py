"""cartoes e autorizacoes no drive

Revision ID: c7d1f3a92b54
Revises: a4c8e2f61d37
Create Date: 2026-10-27 10:00:00.000000

Cada cartao e cada autorizacao ganha uma copia no Drive Compartilhado, em
pastas por instituicao. O id da copia fica gravado: nulo quer dizer que ainda
nao foi, e a copia da noite manda o que ficou para tras.
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d1f3a92b54"
down_revision = "a4c8e2f61d37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cartoes", sa.Column("drive_id", sa.String(100), nullable=True))
    op.add_column("autorizacoes", sa.Column("drive_id", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("autorizacoes", "drive_id")
    op.drop_column("cartoes", "drive_id")
