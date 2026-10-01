"""a monitoria se parte em dois perfis

Revision ID: a9d4f602c1be
Revises: f8c2e5a71b93
Create Date: 2026-10-01 09:40:00.000000

Ate aqui "Monitor" era um perfil so, preso as instituicoes atribuidas. Quem
coordena a monitoria precisa da edicao inteira — abrir qualquer pasta de
cartao, fazer check-in de qualquer instituicao —, e isso nao existia.

Duas mudancas:

  1. "Monitor" passa a se chamar "Monitoria - monitores". Quem ja esta nele
     continua exatamente como estava: o vinculo aponta para o perfil por id, e
     o id nao muda. So o nome na tela.
  2. Nasce "Monitoria - coordenacao", com as MESMAS permissoes e sem o filtro
     de instituicao. O filtro nao esta na base: e a lista
     PERFIS_FILTRADOS_POR_INSTITUICAO, no codigo, e la o nome novo nao entra.

O seed nao roda no deploy, entao o perfil novo precisa vir por aqui.
"""
from alembic import op

revision = "a9d4f602c1be"
down_revision = "f8c2e5a71b93"
branch_labels = None
depends_on = None

ANTIGO = "Monitor"
MONITORES = "Monitoria - monitores"
COORDENACAO = "Monitoria - coordenacao"
DESCRICAO_MONITORES = (
    "Recolhe e digitaliza os cartoes das instituicoes sob sua responsabilidade"
)
DESCRICAO_COORDENACAO = "Coordena a monitoria: todas as instituicoes da edicao"

# As mesmas de "Monitor". Escritas aqui porque a migracao nao importa o seed:
# ela tem de continuar valendo mesmo que o seed mude depois.
PERMISSOES = ("ver_criancas", "subir_cartoes", "fazer_checkin")


def upgrade() -> None:
    op.execute(
        f"UPDATE perfis SET nome = '{MONITORES}', descricao = '{DESCRICAO_MONITORES}' "
        f"WHERE nome = '{ANTIGO}'"
    )
    op.execute(
        f"INSERT INTO perfis (nome, descricao) VALUES ('{COORDENACAO}', '{DESCRICAO_COORDENACAO}') "
        "ON CONFLICT (nome) DO NOTHING"
    )
    lista = ", ".join(f"'{p}'" for p in PERMISSOES)
    op.execute(
        f"""
        INSERT INTO perfil_permissoes (perfil_id, permissao_id)
        SELECT pf.id, pm.id FROM perfis pf, permissoes pm
        WHERE pf.nome = '{COORDENACAO}' AND pm.codigo IN ({lista})
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM perfil_permissoes WHERE perfil_id = "
        f"(SELECT id FROM perfis WHERE nome = '{COORDENACAO}')"
    )
    # So sai se ninguem estiver nele: apagar o perfil levaria os vinculos junto
    # no cascade, e com eles o acesso de quem ja foi cadastrado ali.
    op.execute(
        f"""
        DELETE FROM perfis WHERE nome = '{COORDENACAO}'
        AND NOT EXISTS (SELECT 1 FROM usuario_edicao WHERE perfil_id = perfis.id)
        """
    )
    op.execute(
        f"UPDATE perfis SET nome = '{ANTIGO}', "
        "descricao = 'Recolhe e digitaliza os cartoes das criancas' "
        f"WHERE nome = '{MONITORES}'"
    )
