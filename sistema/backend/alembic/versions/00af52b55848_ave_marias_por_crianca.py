"""ave-marias por crianca

Revision ID: 00af52b55848
Revises: c8a3e6f1d204
Create Date: 2026-10-06 22:37:28.517942

Cada convite de oracao que aparece vira uma linha aqui, e a ficha da crianca
mostra quantas ave-marias ja foram rezadas por ela.
"""
from alembic import op
import sqlalchemy as sa

revision = "00af52b55848"
down_revision = "c8a3e6f1d204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ave_marias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("crianca_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["crianca_id"], ["criancas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "crianca_id", "usuario_id", "dia", name="uq_ave_marias_crianca_usuario_dia"
        ),
    )
    op.create_index("ix_ave_marias_crianca_id", "ave_marias", ["crianca_id"])


def downgrade() -> None:
    op.drop_index("ix_ave_marias_crianca_id", table_name="ave_marias")
    op.drop_table("ave_marias")
