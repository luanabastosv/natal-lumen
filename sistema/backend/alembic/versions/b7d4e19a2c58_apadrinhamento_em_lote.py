"""apadrinhamento em lote

Revision ID: b7d4e19a2c58
Revises: 4b33ddd2f1f6
Create Date: 2026-11-27 10:00:00.000000

Um grupo junta o dinheiro, faz uma transferencia so, e cada pessoa do grupo
vira um padrinho com a sua crianca. O lote liga os pagamentos dessa planilha,
para o ZIP de agradecimentos do grupo poder ser baixado de novo.
"""
import sqlalchemy as sa
from alembic import op

revision = "b7d4e19a2c58"
down_revision = "4b33ddd2f1f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lotes_apadrinhamento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("edicao_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=160), nullable=False),
        sa.Column("criado_por", sa.Integer(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("chave_envio", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["edicao_id"], ["edicoes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["criado_por"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chave_envio"),
    )
    op.create_index(
        "ix_lotes_apadrinhamento_edicao_id", "lotes_apadrinhamento", ["edicao_id"]
    )
    op.add_column("pagamentos", sa.Column("lote_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_pagamentos_lote_id", "pagamentos", "lotes_apadrinhamento",
        ["lote_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_pagamentos_lote_id", "pagamentos", ["lote_id"])


def downgrade() -> None:
    op.drop_index("ix_pagamentos_lote_id", table_name="pagamentos")
    op.drop_constraint("fk_pagamentos_lote_id", "pagamentos", type_="foreignkey")
    op.drop_column("pagamentos", "lote_id")
    op.drop_index("ix_lotes_apadrinhamento_edicao_id", table_name="lotes_apadrinhamento")
    op.drop_table("lotes_apadrinhamento")
