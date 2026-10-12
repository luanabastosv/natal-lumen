"""programacao do evento

Revision ID: d7f1b3c9e520
Revises: c5e8a1d2b347
Create Date: 2026-10-12 12:00:00.000000

A programacao do dia do evento de cada edicao, num JSON: abertura,
rodizios por nucleo e atividades de todos. Ver models/operacao.py.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d7f1b3c9e520"
down_revision = "c5e8a1d2b347"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "programacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("edicao_id", sa.Integer(), sa.ForeignKey("edicoes.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("dados", postgresql.JSONB(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("atualizado_por", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("programacoes")
