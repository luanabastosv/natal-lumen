"""comissario sem pagamentos nem checkin

Revision ID: b3f5d0a71e29
Revises: a7e2b91c4f08
Create Date: 2026-09-27 10:20:00.000000

O seed dos perfis so acrescenta permissoes: de proposito, para nao desfazer
ajustes feitos na base a mao. Entao tirar as duas do codigo nao basta — quem
ja tem base precisa desta migracao.

Pagamento e conferencia de dinheiro ficam com a coordenacao; o check-in do dia
fica com o monitor e a estrutura.
"""
from alembic import op

revision = "b3f5d0a71e29"
down_revision = "a7e2b91c4f08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM perfil_permissoes
        WHERE perfil_id = (SELECT id FROM perfis WHERE nome = 'Comissario')
          AND permissao_id IN (
              SELECT id FROM permissoes
              WHERE codigo IN ('registrar_pagamentos', 'fazer_checkin')
          )
        """
    )


def downgrade() -> None:
    # Devolve as duas ao perfil. ON CONFLICT porque a chave e composta e a
    # linha pode ter sido recriada a mao na base.
    op.execute(
        """
        INSERT INTO perfil_permissoes (perfil_id, permissao_id)
        SELECT pf.id, pm.id
        FROM perfis pf, permissoes pm
        WHERE pf.nome = 'Comissario'
          AND pm.codigo IN ('registrar_pagamentos', 'fazer_checkin')
        ON CONFLICT DO NOTHING
        """
    )
