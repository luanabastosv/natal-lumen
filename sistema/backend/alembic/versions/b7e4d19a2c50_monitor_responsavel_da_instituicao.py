"""monitor responsavel da instituicao

Revision ID: b7e4d19a2c50
Revises: a3f9d27c6e18
Create Date: 2026-11-18 16:30:00.000000

Entre os monitores atribuidos a uma instituicao numa edicao, um e o
responsavel por ela. A marca fica na propria atribuicao (usuario_instituicao):
so pode ser responsavel quem esta atribuido, e tirar a instituicao do monitor
tira a responsabilidade junto. Nasce falsa em todo mundo — ninguem escolhido.
"""
import sqlalchemy as sa
from alembic import op

revision = "b7e4d19a2c50"
down_revision = "a3f9d27c6e18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuario_instituicao",
        sa.Column("responsavel", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("usuario_instituicao", "responsavel")
