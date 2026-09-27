"""grupo do comissario

Revision ID: f2a7c31d94b6
Revises: e4c81b6d5a30
Create Date: 2026-09-27 15:20:00.000000

O comissario responde por um grupo da comunidade. O grupo pertence a cidade e
atravessa os anos, como a instituicao; `nome_normalizado` (sem acento, sem
caixa, sem espaco duplo) e o que a base cobra como unico, para "Elyon",
"elyon" e "Élyon" nao virarem tres grupos.
"""
from alembic import op
import sqlalchemy as sa

revision = "f2a7c31d94b6"
down_revision = "e4c81b6d5a30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grupos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cidade_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("nome_normalizado", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(["cidade_id"], ["cidades.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cidade_id", "nome_normalizado", name="uq_grupos_cidade_nome"),
    )
    op.create_index("ix_grupos_cidade_id", "grupos", ["cidade_id"])

    op.add_column("usuario_edicao", sa.Column("grupo_id", sa.Integer(), nullable=True))
    op.create_index("ix_usuario_edicao_grupo_id", "usuario_edicao", ["grupo_id"])
    op.create_foreign_key(
        "fk_usuario_edicao_grupo_id_grupos",
        "usuario_edicao", "grupos",
        ["grupo_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_usuario_edicao_grupo_id_grupos", "usuario_edicao", type_="foreignkey"
    )
    op.drop_index("ix_usuario_edicao_grupo_id", table_name="usuario_edicao")
    op.drop_column("usuario_edicao", "grupo_id")

    op.drop_index("ix_grupos_cidade_id", table_name="grupos")
    op.drop_table("grupos")
