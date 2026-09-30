"""usuario: quando pediu senha nova

Revision ID: d5a1c73f2e88
Revises: c4d8b30e7a12
Create Date: 2026-09-30 19:40:00.000000

O sistema nao envia email. A tela de "esqueci minha senha" gerava um link que
nao chegava a lugar nenhum, e respondia "enviamos um link" — uma promessa que
nao se cumpria. Quem esquecia a senha ficava esperando.

O pedido passa a ficar marcado no usuario, e a lista de usuarios mostra quem
esta esperando. A coordenacao ve e gera o link, que e o caminho que ja existia e
ninguem sabia que era o caminho.
"""
import sqlalchemy as sa
from alembic import op

revision = "d5a1c73f2e88"
down_revision = "c4d8b30e7a12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuarios", sa.Column("pediu_senha_em", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("usuarios", "pediu_senha_em")
