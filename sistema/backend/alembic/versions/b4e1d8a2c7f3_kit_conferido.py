"""kit conferido

Revision ID: b4e1d8a2c7f3
Revises: 007c6548e5d8
Create Date: 2026-10-08 12:00:00.000000

Quem conferiu o kit, e quando: a segunda pessoa que abre a caixa montada e
confere antes de fechar. Quem montou ja existia (kits.montado_por).
"""
from alembic import op
import sqlalchemy as sa

revision = "b4e1d8a2c7f3"
down_revision = "007c6548e5d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kits", sa.Column("conferido_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kits", sa.Column("conferido_por", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "kits_conferido_por_fkey", "kits", "usuarios", ["conferido_por"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("kits_conferido_por_fkey", "kits", type_="foreignkey")
    op.drop_column("kits", "conferido_por")
    op.drop_column("kits", "conferido_em")
