"""falta no evento

Revision ID: e5a9c3f71d82
Revises: d2f6b8a40c19
Create Date: 2026-10-09 18:00:00.000000

No check-in, alem de "chegou", o monitor marca "faltou": a crianca que nao
foi ao evento. E diferente de desistir (aviso antes) e de ainda nao ter
chegado (sem marcacao).
"""
from alembic import op
import sqlalchemy as sa

revision = "e5a9c3f71d82"
down_revision = "d2f6b8a40c19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("criancas", sa.Column("falta_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("criancas", sa.Column("falta_por", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "criancas_falta_por_fkey", "criancas", "usuarios", ["falta_por"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("criancas_falta_por_fkey", "criancas", type_="foreignkey")
    op.drop_column("criancas", "falta_por")
    op.drop_column("criancas", "falta_em")
