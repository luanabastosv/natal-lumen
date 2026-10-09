"""varias edicoes por cidade no mesmo ano

Revision ID: f1b2c3d4e5a6
Revises: e5a9c3f71d82
Create Date: 2026-10-09 22:00:00.000000

Uma cidade pode ter mais de uma edicao no mesmo ano (o Natal e a Pascoa,
por exemplo, ou duas frentes do mesmo evento). O que continua unico e o
NOME da edicao dentro da cidade e do ano: e por ele que as telas as
distinguem.
"""
from alembic import op

revision = "f1b2c3d4e5a6"
down_revision = "e5a9c3f71d82"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_edicoes_cidade_ano", "edicoes", type_="unique")
    op.create_unique_constraint(
        "uq_edicoes_cidade_ano_nome", "edicoes", ["cidade_id", "ano", "nome"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_edicoes_cidade_ano_nome", "edicoes", type_="unique")
    op.create_unique_constraint("uq_edicoes_cidade_ano", "edicoes", ["cidade_id", "ano"])
