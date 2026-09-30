"""kit: so montado ou nao, sem o estado de entregue

Revision ID: c4d8b30e7a12
Revises: b7e2a91f4c60
Create Date: 2026-09-30 16:05:00.000000

O kit tinha tres estados: pendente, montado e entregue. A coordenacao decidiu
em 30/09/2026 que sao dois — o kit e trabalho da equipe de estrutura na semana
do evento, e o que ela registra e se montou ou nao. A entrega no dia quem
acompanha e o check-in da crianca.

Kit que estava "entregue" vira "montado": para ele ter sido entregue, foi
montado antes. Nenhuma linha se perde.

As duas colunas de entrega sao RENOMEADAS, e nao apagadas: a data em que alguem
mexeu naquele kit continua valendo, agora como a data da montagem. Apagar
custaria o historico para nao ganhar nada.
"""
import sqlalchemy as sa
from alembic import op

revision = "c4d8b30e7a12"
down_revision = "b7e2a91f4c60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Antes da restricao nova, senao ela recusa as linhas que ainda estao
    # "entregue".
    op.execute("UPDATE kits SET status = 'montado' WHERE status = 'entregue'")

    op.alter_column("kits", "entregue_em", new_column_name="montado_em")
    op.alter_column("kits", "entregue_por", new_column_name="montado_por")

    op.drop_constraint("ck_kits_status", "kits", type_="check")
    op.create_check_constraint(
        "ck_kits_status", "kits", sa.text("status IN ('pendente', 'montado')")
    )


def downgrade() -> None:
    op.drop_constraint("ck_kits_status", "kits", type_="check")
    op.create_check_constraint(
        "ck_kits_status", "kits", sa.text("status IN ('pendente', 'montado', 'entregue')")
    )
    op.alter_column("kits", "montado_em", new_column_name="entregue_em")
    op.alter_column("kits", "montado_por", new_column_name="entregue_por")
