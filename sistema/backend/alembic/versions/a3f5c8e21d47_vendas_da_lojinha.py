"""vendas da lojinha no financeiro

Revision ID: a3f5c8e21d47
Revises: d2b6e8f14a73
Create Date: 2026-11-23 23:30:00.000000

A venda paga da lojinha no Shopify entra em `recebimentos` com a categoria
'lojinha', copiada do pedido (servicos/lojinha.py). Duas colunas novas, vazias
em todo recebimento que ja existe: o id do pedido, unico, para o mesmo pedido
nunca entrar duas vezes, e o numero que a loja mostra (#1549).
"""
import sqlalchemy as sa
from alembic import op

revision = "a3f5c8e21d47"
down_revision = "d2b6e8f14a73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recebimentos", sa.Column("shopify_pedido_id", sa.String(60), nullable=True))
    op.add_column("recebimentos", sa.Column("shopify_pedido_numero", sa.String(30), nullable=True))
    op.create_unique_constraint(
        "uq_recebimentos_shopify_pedido_id", "recebimentos", ["shopify_pedido_id"]
    )
    op.drop_constraint("ck_recebimentos_categoria", "recebimentos", type_="check")
    op.create_check_constraint(
        "ck_recebimentos_categoria", "recebimentos",
        "categoria IN ('doacao', 'outros', 'lojinha')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM recebimentos WHERE categoria = 'lojinha'")
    op.drop_constraint("ck_recebimentos_categoria", "recebimentos", type_="check")
    op.create_check_constraint(
        "ck_recebimentos_categoria", "recebimentos", "categoria IN ('doacao', 'outros')"
    )
    op.drop_constraint("uq_recebimentos_shopify_pedido_id", "recebimentos", type_="unique")
    op.drop_column("recebimentos", "shopify_pedido_numero")
    op.drop_column("recebimentos", "shopify_pedido_id")
