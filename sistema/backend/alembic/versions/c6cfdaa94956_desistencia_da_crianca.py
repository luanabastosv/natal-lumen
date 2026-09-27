"""desistencia da crianca

Revision ID: c6cfdaa94956
Revises: 83ef4dd6503b
Create Date: 2026-09-23 18:56:13.437901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6cfdaa94956'
down_revision: Union[str, Sequence[str], None] = '83ef4dd6503b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('criancas', sa.Column('desistiu_em', sa.DateTime(timezone=True), nullable=True))
    op.add_column('criancas', sa.Column('desistiu_por', sa.Integer(), nullable=True))
    # A constraint vai nomeada: sem nome, o downgrade nao tem o que derrubar.
    op.create_foreign_key(
        'fk_criancas_desistiu_por_usuarios', 'criancas', 'usuarios',
        ['desistiu_por'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_criancas_desistiu_por_usuarios', 'criancas', type_='foreignkey')
    op.drop_column('criancas', 'desistiu_por')
    op.drop_column('criancas', 'desistiu_em')
