"""autorizacoes

Revision ID: 007c6548e5d8
Revises: 00af52b55848
Create Date: 2026-10-06 23:10:00.000000

A autorizacao assinada pelo responsavel da crianca, uma por crianca. Sobe pela
tela de cartoes, numa aba propria, com o que o monitor marca ao conferir:
necessidade especial, restricao alimentar e observacao, cada uma com o "qual".
"""
from alembic import op
import sqlalchemy as sa

revision = "007c6548e5d8"
down_revision = "00af52b55848"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "autorizacoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("crianca_id", sa.Integer(), nullable=False),
        sa.Column("arquivo", sa.String(length=500), nullable=False),
        sa.Column("necessidade_especial", sa.Boolean(), nullable=True),
        sa.Column("necessidade_especial_qual", sa.Text(), nullable=True),
        sa.Column("restricao_alimentar", sa.Boolean(), nullable=True),
        sa.Column("restricao_alimentar_qual", sa.Text(), nullable=True),
        sa.Column("tem_observacao", sa.Boolean(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("monitor_id", sa.Integer(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["crianca_id"], ["criancas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["monitor_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("crianca_id", name="autorizacoes_crianca_id_key"),
    )


def downgrade() -> None:
    op.drop_table("autorizacoes")
