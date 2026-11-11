"""intercessao: uma pessoa por vivencia em cada crianca

Revision ID: b6d3f8a2e914
Revises: 8947c37dd3a1
Create Date: 2026-11-11 09:45:00

Cada vivencia (missa, adoracao, terco, jejum) de uma crianca passa a ter UM
dono: quem marcou primeiro. Os outros veem o checkbox marcado e travado.

  1. Se a mesma vivencia de uma crianca foi marcada por mais de uma pessoa,
     fica so a marcacao mais antiga.
  2. A chave unica deixa de ter o usuario: (crianca, vivencia).
"""
from alembic import op

revision = "b6d3f8a2e914"
down_revision = "8947c37dd3a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM intercessoes i
        USING intercessoes primeira
        WHERE i.crianca_id = primeira.crianca_id
          AND i.tipo = primeira.tipo
          AND (primeira.criado_em, primeira.id) < (i.criado_em, i.id)
        """
    )
    op.drop_constraint("uq_intercessoes_crianca_usuario_tipo", "intercessoes", type_="unique")
    op.create_unique_constraint(
        "uq_intercessoes_crianca_tipo", "intercessoes", ["crianca_id", "tipo"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_intercessoes_crianca_tipo", "intercessoes", type_="unique")
    op.create_unique_constraint(
        "uq_intercessoes_crianca_usuario_tipo", "intercessoes", ["crianca_id", "usuario_id", "tipo"]
    )
