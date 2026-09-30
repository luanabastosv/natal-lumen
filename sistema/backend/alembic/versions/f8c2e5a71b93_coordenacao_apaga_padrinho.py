"""coordenacao pode apagar padrinho e desfazer apadrinhamento pago

Revision ID: f8c2e5a71b93
Revises: e6b4f19d0a37
Create Date: 2026-09-30 21:30:00.000000

Ate aqui nao havia como apagar o cadastro de um padrinho, e desfazer um
apadrinhamento so era possivel enquanto ele nao tivesse pagamento. Engano de
captacao acontece — a pessoa liga a crianca ao padrinho errado, e depois paga.

A permissao e separada de `editar_padrinhos` de proposito. Quem capta corrige o
que acabou de digitar; isto aqui desfaz o que ja virou numero no painel e, no
caso do pagamento, mexe onde ha dinheiro. Fica so com a coordenacao.

O seed dos perfis nao roda no deploy: quem ja tem base precisa desta migracao.
"""
from alembic import op

revision = "f8c2e5a71b93"
down_revision = "e6b4f19d0a37"
branch_labels = None
depends_on = None

CODIGO = "excluir_padrinhos"
DESCRICAO = "Apagar padrinhos e desfazer apadrinhamentos ja pagos"


def upgrade() -> None:
    op.execute(
        f"INSERT INTO permissoes (codigo, descricao) VALUES ('{CODIGO}', '{DESCRICAO}') "
        "ON CONFLICT (codigo) DO NOTHING"
    )
    op.execute(
        f"""
        INSERT INTO perfil_permissoes (perfil_id, permissao_id)
        SELECT pf.id, pm.id FROM perfis pf, permissoes pm
        WHERE pf.nome = 'Coordenacao' AND pm.codigo = '{CODIGO}'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM perfil_permissoes WHERE permissao_id = "
        f"(SELECT id FROM permissoes WHERE codigo = '{CODIGO}')"
    )
    op.execute(f"DELETE FROM permissoes WHERE codigo = '{CODIGO}'")
