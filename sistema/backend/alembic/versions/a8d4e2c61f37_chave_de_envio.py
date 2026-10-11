"""chave de envio

Revision ID: a8d4e2c61f37
Revises: f1b2c3d4e5a6
Create Date: 2026-10-11 15:00:00.000000

Padrinho e pagamento ganham a chave que a tela gera a cada tentativa de
registrar. Um clique repetido depois de a conexao cair devolve o registro que
ja foi gravado, em vez de criar outro.
"""
from alembic import op
import sqlalchemy as sa

revision = "a8d4e2c61f37"
down_revision = "f1b2c3d4e5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("padrinhos", sa.Column("chave_envio", sa.String(64), nullable=True))
    op.create_unique_constraint("padrinhos_chave_envio_key", "padrinhos", ["chave_envio"])
    op.add_column("pagamentos", sa.Column("chave_envio", sa.String(64), nullable=True))
    op.create_unique_constraint("pagamentos_chave_envio_key", "pagamentos", ["chave_envio"])


def downgrade() -> None:
    op.drop_constraint("pagamentos_chave_envio_key", "pagamentos", type_="unique")
    op.drop_column("pagamentos", "chave_envio")
    op.drop_constraint("padrinhos_chave_envio_key", "padrinhos", type_="unique")
    op.drop_column("padrinhos", "chave_envio")
