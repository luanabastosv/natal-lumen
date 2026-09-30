"""padrinho: e membro do Ser Feliz? tem interesse em contribuir mensalmente?

Revision ID: b7e2a91f4c60
Revises: a3f7d21c8e45
Create Date: 2026-09-30 15:10:00.000000

Duas perguntas que a captacao ja fazia na conversa e anotava fora do sistema.

Aceitam NULO, e sem default: nulo aqui nao e "nao", e "ninguem perguntou". Os
padrinhos cadastrados antes destes campos nunca ouviram a pergunta, e um
`server_default=false` os marcaria como "nao e membro" e "nao quer contribuir"
— duas afirmacoes que ninguem apurou. E justamente a lista dos que faltam
perguntar que a captacao precisa reaproveitar no ano seguinte.
"""
import sqlalchemy as sa
from alembic import op

revision = "b7e2a91f4c60"
down_revision = "a3f7d21c8e45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("padrinhos", sa.Column("membro_ser_feliz", sa.Boolean(), nullable=True))
    op.add_column("padrinhos", sa.Column("interesse_mensal", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("padrinhos", "interesse_mensal")
    op.drop_column("padrinhos", "membro_ser_feliz")
