"""o comissariado se parte em dois perfis

Revision ID: b1e7a35c92df
Revises: a9d4f602c1be
Create Date: 2026-10-01 14:10:00.000000

Mesma historia da monitoria, do outro lado da campanha. "Comissario" era um
perfil so, preso as instituicoes atribuidas E a lista nominal de criancas de
cada um. Quem coordena a captacao precisa da edicao inteira e precisa
redistribuir essa lista entre o time, e nada disso existia.

Tres mudancas:

  1. "Comissario" passa a se chamar "Comissarios - comissario". Quem ja esta
     nele continua exatamente como estava: o vinculo aponta para o perfil por
     id, e o id nao muda. So o nome na tela.
  2. Nasce a permissao `atribuir_comissario` — mudar SO quem responde pela
     crianca, sem o poder de criar, renomear ou apagar crianca que vem com
     `editar_criancas`.
  3. Nasce "Comissarios - coordenacao", com as permissoes do comissario mais
     essa, e sem o filtro por instituicao e por crianca. O filtro nao esta na
     base: sao as listas em app/seeds/perfis_permissoes.py, e la o nome novo
     nao entra.

A coordenacao da cidade recebe `atribuir_comissario` junto, como recebe toda
permissao nova — ela faz tudo o que qualquer equipe faz.

O seed nao roda no deploy, entao tudo isto precisa vir por aqui.
"""
from alembic import op

revision = "b1e7a35c92df"
down_revision = "a9d4f602c1be"
branch_labels = None
depends_on = None

ANTIGO = "Comissario"
COMISSARIO = "Comissarios - comissario"
COORDENACAO_CAPTACAO = "Comissarios - coordenacao"

DESCRICAO_COMISSARIO = "Capta padrinhos das criancas atribuidas a ele e envia os cartoes"
DESCRICAO_COORDENACAO = (
    "Coordena a captacao: todas as instituicoes, e distribui a lista do time"
)

PERMISSAO = "atribuir_comissario"
DESCRICAO_PERMISSAO = "Definir o comissario responsavel por uma crianca"

# As mesmas de "Comissario". Escritas aqui porque a migracao nao importa o
# seed: ela tem de continuar valendo mesmo que o seed mude depois.
DO_COMISSARIO = (
    "ver_painel",
    "ver_criancas",
    "ver_padrinhos",
    "editar_padrinhos",
    "registrar_pagamentos_padrinho",
    "enviar_cartoes",
)


def upgrade() -> None:
    op.execute(
        f"UPDATE perfis SET nome = '{COMISSARIO}', descricao = '{DESCRICAO_COMISSARIO}' "
        f"WHERE nome = '{ANTIGO}'"
    )
    op.execute(
        f"INSERT INTO permissoes (codigo, descricao) "
        f"VALUES ('{PERMISSAO}', '{DESCRICAO_PERMISSAO}') ON CONFLICT (codigo) DO NOTHING"
    )
    op.execute(
        f"INSERT INTO perfis (nome, descricao) "
        f"VALUES ('{COORDENACAO_CAPTACAO}', '{DESCRICAO_COORDENACAO}') "
        "ON CONFLICT (nome) DO NOTHING"
    )

    lista = ", ".join(f"'{p}'" for p in (*DO_COMISSARIO, PERMISSAO))
    op.execute(
        f"""
        INSERT INTO perfil_permissoes (perfil_id, permissao_id)
        SELECT pf.id, pm.id FROM perfis pf, permissoes pm
        WHERE pf.nome = '{COORDENACAO_CAPTACAO}' AND pm.codigo IN ({lista})
        ON CONFLICT DO NOTHING
        """
    )
    # A coordenacao da cidade tem todas as permissoes, inclusive as que nascem
    # depois dela.
    op.execute(
        f"""
        INSERT INTO perfil_permissoes (perfil_id, permissao_id)
        SELECT pf.id, pm.id FROM perfis pf, permissoes pm
        WHERE pf.nome = 'Coordenacao' AND pm.codigo = '{PERMISSAO}'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM perfil_permissoes WHERE perfil_id = "
        f"(SELECT id FROM perfis WHERE nome = '{COORDENACAO_CAPTACAO}')"
    )
    # So sai se ninguem estiver nele: apagar o perfil levaria os vinculos junto
    # no cascade, e com eles o acesso de quem ja foi cadastrado ali.
    op.execute(
        f"""
        DELETE FROM perfis WHERE nome = '{COORDENACAO_CAPTACAO}'
        AND NOT EXISTS (SELECT 1 FROM usuario_edicao WHERE perfil_id = perfis.id)
        """
    )
    op.execute(
        f"DELETE FROM perfil_permissoes WHERE permissao_id = "
        f"(SELECT id FROM permissoes WHERE codigo = '{PERMISSAO}')"
    )
    op.execute(f"DELETE FROM permissoes WHERE codigo = '{PERMISSAO}'")
    op.execute(
        f"UPDATE perfis SET nome = '{ANTIGO}', "
        "descricao = 'Capta padrinhos e envia os cartoes' "
        f"WHERE nome = '{COMISSARIO}'"
    )
