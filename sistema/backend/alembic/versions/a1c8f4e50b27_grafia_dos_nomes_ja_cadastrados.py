"""grafia dos nomes ja cadastrados

Revision ID: a1c8f4e50b27
Revises: c05f8e21a7d3
Create Date: 2026-09-29 16:20:00.000000

A partir de agora a grafia do nome se decide na entrada (servicos/nomes.py),
mas quem ja esta na base entrou antes disso: as listas trazem turmas inteiras
em CAIXA ALTA, e na tela elas aparecem gritando ao lado das digitadas na mao.

Aqui a mesma regra passa uma vez por criancas, padrinhos e usuarios. Quem ja
estava certo nao muda — a regra e idempotente, e rodar de novo nao faz nada.

A volta nao existe: a grafia original nao fica guardada em lugar nenhum, e e
justamente ela que se quis perder.
"""
import sqlalchemy as sa
from alembic import op

from app.servicos.nomes import nome_proprio

revision = "a1c8f4e50b27"
down_revision = "c05f8e21a7d3"
branch_labels = None
depends_on = None

TABELAS = ("criancas", "padrinhos", "usuarios")


def upgrade() -> None:
    conexao = op.get_bind()

    for tabela in TABELAS:
        alvo = sa.table(tabela, sa.column("id", sa.Integer), sa.column("nome", sa.String))

        # Em lote, e nao linha a linha: sao milhares de criancas por edicao, e
        # cada UPDATE solto seria uma ida ao banco.
        mudancas = [
            {"alvo_id": id_, "alvo_nome": arrumado}
            for id_, nome in conexao.execute(sa.select(alvo.c.id, alvo.c.nome))
            if (arrumado := nome_proprio(nome)) != nome
        ]
        if not mudancas:
            continue

        conexao.execute(
            alvo.update()
            .where(alvo.c.id == sa.bindparam("alvo_id"))
            .values(nome=sa.bindparam("alvo_nome")),
            mudancas,
        )
        print(f"  {tabela}: {len(mudancas)} nome(s) regravado(s)")


def downgrade() -> None:
    """Sem volta: a grafia anterior nao foi guardada."""
