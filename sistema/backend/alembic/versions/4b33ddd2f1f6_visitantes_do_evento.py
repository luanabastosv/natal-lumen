"""visitantes do evento

Revision ID: 4b33ddd2f1f6
Revises: a3f5c8e21d47
Create Date: 2026-11-25 00:30:00.000000

As pulseiras do evento ganham um QR Code que leva as fotos. Antes do link,
a pessoa deixa nome e celular: sao os visitantes do evento, que a
coordenacao ve numa planilha.

Um QR Code so por edicao, para os dois dias: a edicao guarda o codigo que
vai no QR ("nl26") e o link da galeria, que pode mudar sem reimprimir
pulseira.
"""
import sqlalchemy as sa
from alembic import op

revision = "4b33ddd2f1f6"
down_revision = "a3f5c8e21d47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("edicoes", sa.Column("codigo_fotos", sa.String(length=20), nullable=True))
    op.add_column("edicoes", sa.Column("link_fotos", sa.String(length=500), nullable=True))
    op.create_unique_constraint("uq_edicoes_codigo_fotos", "edicoes", ["codigo_fotos"])

    op.create_table(
        "visitantes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("edicao_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=160), nullable=False),
        sa.Column("celular", sa.String(length=11), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["edicao_id"], ["edicoes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("edicao_id", "celular", name="uq_visitantes_edicao_celular"),
    )
    op.create_index("ix_visitantes_edicao_id", "visitantes", ["edicao_id"])


def downgrade() -> None:
    op.drop_index("ix_visitantes_edicao_id", table_name="visitantes")
    op.drop_table("visitantes")
    op.drop_constraint("uq_edicoes_codigo_fotos", "edicoes", type_="unique")
    op.drop_column("edicoes", "link_fotos")
    op.drop_column("edicoes", "codigo_fotos")
