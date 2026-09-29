"""onibus da instituicao no dia

Revision ID: c05f8e21a7d3
Revises: f9b2c60ad134
Create Date: 2026-09-29 14:10:00.000000

Quantos onibus buscam cada instituicao no dia dela. Era a coluna "# ONIBUS" da
planilha, e e o unico numero da logistica do dia que o sistema ainda nao sabia
calcular sozinho — os outros (quantas criancas, quantas sem padrinho) ja saem
das proprias tabelas.

Fica em `instituicao_dia`, e nao no cadastro da instituicao, porque e numero de
UM ano: a escola que precisou de dois onibus em 2026 pode precisar de um em
2027. Nasce zero em todo mundo — nenhum transporte fechado ainda.
"""
import sqlalchemy as sa
from alembic import op

revision = "c05f8e21a7d3"
down_revision = "f9b2c60ad134"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instituicao_dia",
        sa.Column("onibus", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_instituicao_dia_onibus", "instituicao_dia", "onibus >= 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_instituicao_dia_onibus", "instituicao_dia", type_="check")
    op.drop_column("instituicao_dia", "onibus")
