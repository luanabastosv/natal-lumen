"""contribuicao mensal com tres respostas

Revision ID: c5e8a1d2b347
Revises: b3c7d9e1f204
Create Date: 2026-10-12 10:00:00.000000

"Tem interesse em contribuir mensalmente?" ganha uma terceira resposta: ja
contribuo. A coluna deixa de ser booleana; o que havia vira texto sem perder
nada (true -> sim, false -> nao, nulo continua nulo).
"""
from alembic import op
import sqlalchemy as sa

revision = "c5e8a1d2b347"
down_revision = "b3c7d9e1f204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "padrinhos", "interesse_mensal",
        type_=sa.String(12),
        postgresql_using="CASE WHEN interesse_mensal THEN 'sim' "
                         "WHEN NOT interesse_mensal THEN 'nao' END",
    )
    op.create_check_constraint(
        "ck_padrinhos_interesse_mensal", "padrinhos",
        "interesse_mensal IN ('sim', 'nao', 'ja_contribui')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_padrinhos_interesse_mensal", "padrinhos", type_="check")
    # Quem ja contribui volta como "sim": e o mais perto que o booleano chega.
    op.alter_column(
        "padrinhos", "interesse_mensal",
        type_=sa.Boolean(),
        postgresql_using="CASE WHEN interesse_mensal = 'nao' THEN false "
                         "WHEN interesse_mensal IS NULL THEN NULL ELSE true END",
    )
