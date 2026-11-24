"""troca da crianca desistente

Revision ID: d2b6e8f14a73
Revises: b7e4d19a2c50
Create Date: 2026-11-24 00:30:00.000000

Quando uma crianca apadrinhada desiste, a coordenacao passa o apadrinhamento
para outra crianca, com o mesmo pagamento. O apadrinhamento guarda de qual
crianca veio, quando foi a troca e quando o padrinho foi avisado. As tres
colunas nascem vazias: nenhuma troca feita ainda.
"""
import sqlalchemy as sa
from alembic import op

revision = "d2b6e8f14a73"
down_revision = "b7e4d19a2c50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("apadrinhamentos", sa.Column("trocado_de_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_apadrinhamentos_trocado_de_id_criancas",
        "apadrinhamentos", "criancas", ["trocado_de_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column("apadrinhamentos", sa.Column("trocado_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "apadrinhamentos", sa.Column("troca_avisada_em", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("apadrinhamentos", "troca_avisada_em")
    op.drop_column("apadrinhamentos", "trocado_em")
    op.drop_constraint("fk_apadrinhamentos_trocado_de_id_criancas", "apadrinhamentos", type_="foreignkey")
    op.drop_column("apadrinhamentos", "trocado_de_id")
