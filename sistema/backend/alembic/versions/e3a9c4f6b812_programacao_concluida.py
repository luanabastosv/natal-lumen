"""programacao concluida

Revision ID: e3a9c4f6b812
Revises: d7f1b3c9e520
Create Date: 2026-10-12 16:00:00.000000

A programacao so aparece para a equipe inteira depois que a coordenacao
geral a marca como concluida. Nulo = ainda em montagem, so a coordenacao ve.
"""
from alembic import op
import sqlalchemy as sa

revision = "e3a9c4f6b812"
down_revision = "d7f1b3c9e520"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("programacoes", sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "programacoes",
        sa.Column("concluida_por", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("programacoes", "concluida_por")
    op.drop_column("programacoes", "concluida_em")
