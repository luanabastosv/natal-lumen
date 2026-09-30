"""comissario registra o pagamento do padrinho dele

Revision ID: a3f7d21c8e45
Revises: a1c8f4e50b27
Create Date: 2026-09-30 14:20:00.000000

Desde que promessa deixou de contar como apadrinhamento, e o PAGAMENTO que
confirma o trabalho do comissario. Com o registro do dinheiro so na mao da
coordenacao, nada do que ele capta apareceria em numero nenhum ate ela passar
por ali — entao o registro do pagamento do padrinho volta para ele.

Volta SEPARADO, e nao pela permissao antiga: `registrar_pagamentos` e a mesma
chave da aba Recebimentos do financeiro, que mostra todo o dinheiro que entra na
edicao (doacao e patrocinio inclusive) e deixa lancar, remover e conferir. Dar
essa chave a cada comissario abriria o caixa inteiro a quem so precisa registrar
o proprio padrinho. A permissao nova alcanca so os pagamentos dos padrinhos que
ele ja alcanca; conferir e apagar continuam com a coordenacao, porque quem
registra o dinheiro nao deve ser quem audita o registro.

O seed dos perfis nao roda no deploy, e so acrescentaria permissao em base nova.
Quem ja tem base precisa desta migracao.
"""
from alembic import op

revision = "a3f7d21c8e45"
down_revision = "a1c8f4e50b27"
branch_labels = None
depends_on = None

CODIGO = "registrar_pagamentos_padrinho"
DESCRICAO = "Registrar o pagamento dos padrinhos que alcanca"

# A coordenacao tem todas as permissoes por definicao, mas isso e uma linha por
# permissao na base — uma permissao nova nao chega la sozinha.
PERFIS = ("Coordenacao", "Comissario")


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO permissoes (codigo, descricao)
        VALUES ('{CODIGO}', '{DESCRICAO}')
        ON CONFLICT (codigo) DO NOTHING
        """
    )
    # A descricao da antiga mudou junto: ela nao fala mais pelos dois assuntos.
    op.execute(
        """
        UPDATE permissoes
        SET descricao = 'Registrar os recebimentos da edicao e conferir pagamentos'
        WHERE codigo = 'registrar_pagamentos'
        """
    )
    for perfil in PERFIS:
        op.execute(
            f"""
            INSERT INTO perfil_permissoes (perfil_id, permissao_id)
            SELECT pf.id, pm.id
            FROM perfis pf, permissoes pm
            WHERE pf.nome = '{perfil}'
              AND pm.codigo = '{CODIGO}'
            ON CONFLICT DO NOTHING
            """
        )


def downgrade() -> None:
    # Apaga os vinculos antes da permissao: a FK nao deixa a ordem inversa.
    op.execute(
        f"""
        DELETE FROM perfil_permissoes
        WHERE permissao_id = (SELECT id FROM permissoes WHERE codigo = '{CODIGO}')
        """
    )
    op.execute(f"DELETE FROM permissoes WHERE codigo = '{CODIGO}'")
