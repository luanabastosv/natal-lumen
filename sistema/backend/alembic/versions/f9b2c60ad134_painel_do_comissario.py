"""painel do comissario

Revision ID: f9b2c60ad134
Revises: e8c1a4f2b930
Create Date: 2026-09-29 09:40:00.000000

O comissario passa a ver o painel. Nao e o painel da edicao: o relatorio ja
passa pelo mesmo filtro das telas, e o filtro dele e crianca a crianca — entao
a mesma permissao mostra a ele so o que esta na mao dele.

O seed dos perfis nao roda no deploy, e so acrescentaria permissao em base
nova. Quem ja tem base precisa desta migracao.
"""
from alembic import op

revision = "f9b2c60ad134"
down_revision = "e8c1a4f2b930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ON CONFLICT porque a chave e composta e a linha pode ja ter sido criada a
    # mao na base.
    op.execute(
        """
        INSERT INTO perfil_permissoes (perfil_id, permissao_id)
        SELECT pf.id, pm.id
        FROM perfis pf, permissoes pm
        WHERE pf.nome = 'Comissario'
          AND pm.codigo = 'ver_painel'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM perfil_permissoes
        WHERE perfil_id = (SELECT id FROM perfis WHERE nome = 'Comissario')
          AND permissao_id = (SELECT id FROM permissoes WHERE codigo = 'ver_painel')
        """
    )
