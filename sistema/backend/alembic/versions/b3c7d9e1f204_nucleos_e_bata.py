"""nucleos e cor da bata

Revision ID: b3c7d9e1f204
Revises: a8d4e2c61f37
Create Date: 2026-10-11 18:00:00.000000

O dia da instituicao ganha o nucleo de rodizio (A a D) e a cor da bata das
criancas dela. Ver models/operacao.py, InstituicaoDia.
"""
from alembic import op
import sqlalchemy as sa

revision = "b3c7d9e1f204"
down_revision = "a8d4e2c61f37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instituicao_dia", sa.Column("nucleo", sa.String(1), nullable=True))
    op.add_column("instituicao_dia", sa.Column("cor_bata_nome", sa.String(40), nullable=True))
    op.add_column("instituicao_dia", sa.Column("cor_bata_hex", sa.String(7), nullable=True))
    op.create_check_constraint(
        "ck_instituicao_dia_nucleo", "instituicao_dia", "nucleo IN ('A', 'B', 'C', 'D')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_instituicao_dia_nucleo", "instituicao_dia", type_="check")
    op.drop_column("instituicao_dia", "cor_bata_hex")
    op.drop_column("instituicao_dia", "cor_bata_nome")
    op.drop_column("instituicao_dia", "nucleo")
