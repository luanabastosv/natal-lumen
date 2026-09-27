"""comissario responsavel pela crianca

Revision ID: e4c81b6d5a30
Revises: b3f5d0a71e29
Create Date: 2026-09-27 11:05:00.000000

A instituicao e atendida por um TIME de comissarios. Este campo nao muda o
alcance de ninguem — diz apenas quem responde por cada crianca.
"""
from alembic import op
import sqlalchemy as sa

revision = "e4c81b6d5a30"
down_revision = "b3f5d0a71e29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("criancas", sa.Column("comissario_id", sa.Integer(), nullable=True))
    op.create_index("ix_criancas_comissario_id", "criancas", ["comissario_id"])
    op.create_foreign_key(
        "fk_criancas_comissario_id_usuarios",
        "criancas", "usuarios",
        ["comissario_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_criancas_comissario_id_usuarios", "criancas", type_="foreignkey")
    op.drop_index("ix_criancas_comissario_id", table_name="criancas")
    op.drop_column("criancas", "comissario_id")
