"""campanha da festa

Revision ID: a4c8e2f61d37
Revises: e3a9c4f6b812
Create Date: 2026-10-20 10:00:00.000000

O apadrinhamento da festa so comeca quando a coordenacao geral libera, quase
no fim da campanha da cesta. Nulo = ainda nao liberada: so cesta.

A festa tambem tem responsavel proprio (criancas.comissario_festa_id): o
comissario da instituicao responde pela cesta, e a festa fica com a
coordenacao ate ela passar a festa de cada crianca para alguem.
"""
from alembic import op
import sqlalchemy as sa

revision = "a4c8e2f61d37"
down_revision = "e3a9c4f6b812"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("edicoes", sa.Column("festa_liberada_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "edicoes",
        sa.Column("festa_liberada_por", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "criancas",
        sa.Column("comissario_festa_id", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_criancas_comissario_festa_id", "criancas", ["comissario_festa_id"])


def downgrade() -> None:
    op.drop_index("ix_criancas_comissario_festa_id", table_name="criancas")
    op.drop_column("criancas", "comissario_festa_id")
    op.drop_column("edicoes", "festa_liberada_por")
    op.drop_column("edicoes", "festa_liberada_em")
