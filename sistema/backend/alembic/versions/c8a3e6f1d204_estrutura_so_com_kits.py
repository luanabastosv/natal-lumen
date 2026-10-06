"""a estrutura fica so com os kits

Revision ID: c8a3e6f1d204
Revises: b1e7a35c92df
Create Date: 2026-10-06 10:00:00.000000

A estrutura passa a entrar so na tela de kits, e ganha um painel proprio.

  1. Saem ver_criancas, gerenciar_compras e fazer_checkin. As saidas do
     financeiro ficam com a coordenacao, e o check-in do dia com a monitoria.
  2. Nasce `ver_painel_logistica`: o painel so com as quebras por dia do
     evento, por idade e por instituicao. A estrutura recebe, e a coordenacao
     da cidade tambem, como recebe toda permissao nova.

O seed so acrescenta permissoes, e nao roda no deploy — entao tudo isto
precisa vir por aqui.
"""
from alembic import op

revision = "c8a3e6f1d204"
down_revision = "b1e7a35c92df"
branch_labels = None
depends_on = None

ESTRUTURA = "Estrutura"
COORDENACAO = "Coordenacao"
DESCRICAO_NOVA = "Monta os kits das criancas"
DESCRICAO_ANTIGA = "Compra e monta os kits e faz a entrega"

PERMISSAO = "ver_painel_logistica"
DESCRICAO_PERMISSAO = "Ver o painel da logistica: por dia, por idade e por instituicao"

SAEM = ("ver_criancas", "gerenciar_compras", "fazer_checkin")


def upgrade() -> None:
    lista = ", ".join(f"'{p}'" for p in SAEM)
    op.execute(
        f"""
        DELETE FROM perfil_permissoes
        WHERE perfil_id = (SELECT id FROM perfis WHERE nome = '{ESTRUTURA}')
          AND permissao_id IN (SELECT id FROM permissoes WHERE codigo IN ({lista}))
        """
    )
    op.execute(
        f"UPDATE perfis SET descricao = '{DESCRICAO_NOVA}' WHERE nome = '{ESTRUTURA}'"
    )
    op.execute(
        f"INSERT INTO permissoes (codigo, descricao) "
        f"VALUES ('{PERMISSAO}', '{DESCRICAO_PERMISSAO}') ON CONFLICT (codigo) DO NOTHING"
    )
    # ON CONFLICT porque a chave e composta e a linha pode ja ter sido criada a
    # mao na base.
    op.execute(
        f"""
        INSERT INTO perfil_permissoes (perfil_id, permissao_id)
        SELECT pf.id, pm.id FROM perfis pf, permissoes pm
        WHERE pf.nome IN ('{ESTRUTURA}', '{COORDENACAO}') AND pm.codigo = '{PERMISSAO}'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM perfil_permissoes
        WHERE permissao_id = (SELECT id FROM permissoes WHERE codigo = '{PERMISSAO}')
        """
    )
    op.execute(f"DELETE FROM permissoes WHERE codigo = '{PERMISSAO}'")
    op.execute(
        f"UPDATE perfis SET descricao = '{DESCRICAO_ANTIGA}' WHERE nome = '{ESTRUTURA}'"
    )
    lista = ", ".join(f"'{p}'" for p in SAEM)
    op.execute(
        f"""
        INSERT INTO perfil_permissoes (perfil_id, permissao_id)
        SELECT pf.id, pm.id FROM perfis pf, permissoes pm
        WHERE pf.nome = '{ESTRUTURA}' AND pm.codigo IN ({lista})
        ON CONFLICT DO NOTHING
        """
    )
