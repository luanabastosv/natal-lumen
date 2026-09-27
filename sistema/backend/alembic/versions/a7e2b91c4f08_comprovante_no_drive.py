"""comprovante no drive

Revision ID: a7e2b91c4f08
Revises: d1d4cbe74be4
"""

import sqlalchemy as sa
from alembic import op

revision = "a7e2b91c4f08"
down_revision = "d1d4cbe74be4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Copia do comprovante no Drive Compartilhado do evento. Anulaveis: o
    # disco continua sendo o original, e o Drive e opcional.
    op.add_column("pagamentos", sa.Column("comprovante_drive_id", sa.String(120), nullable=True))
    op.add_column("pagamentos", sa.Column("comprovante_drive_link", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("pagamentos", "comprovante_drive_link")
    op.drop_column("pagamentos", "comprovante_drive_id")
