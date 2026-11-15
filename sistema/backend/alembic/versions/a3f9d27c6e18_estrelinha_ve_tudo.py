"""estrelinha ve todos os dados do evento

Revision ID: a3f9d27c6e18
Revises: e7a4c19b5d20
Create Date: 2026-11-15 11:00:00

Decisao da coordenacao (15/11/2026): a Estrelinha so e usada por poucas
pessoas da coordenacao, que ja veem tudo no sistema. Entao ela passa a ver
todas as colunas, com nomes de criancas, contatos e observacoes.

Continua de fora so o que e credencial, e nao informacao do evento: o hash da
senha e os tokens de acesso e de sessao. Ela continua so lendo.

As views usam `select *`, mas o Postgres congela a lista de colunas quando a
view e criada: coluna nova numa tabela so aparece para a Estrelinha depois de
uma migration que rode `recriar()` de novo.
"""
from alembic import op

revision = "a3f9d27c6e18"
down_revision = "e7a4c19b5d20"
branch_labels = None
depends_on = None

TABELAS = [
    "cidades", "edicoes", "dias_evento", "instituicoes", "grupos", "instituicao_dia",
    "criancas", "programacoes", "padrinhos", "pagamentos", "apadrinhamentos",
    "cobrancas_cartao", "envios_cartao", "cartoes", "autorizacoes", "kits",
    "compras", "recebimentos", "ave_marias", "intercessoes", "perfis", "permissoes",
    "perfil_permissoes", "usuario_edicao", "usuario_instituicao", "log_atividades",
]

# Usuarios sem senha_hash, tentativas_falhas e bloqueado_ate.
USUARIOS = """
    select id, nome, email, whatsapp, admin_geral, ativo, ultimo_login,
           pediu_senha_em, criado_em
    from public.usuarios"""


def recriar() -> None:
    op.execute("drop schema if exists estrelinha cascade")
    op.execute("create schema estrelinha")
    for tabela in TABELAS:
        op.execute(f"create view estrelinha.{tabela} as select * from public.{tabela}")
    op.execute(f"create view estrelinha.usuarios as {USUARIOS}")
    op.execute(
        """
        do $$
        begin
          if exists (select 1 from pg_roles where rolname = 'estrelinha') then
            grant usage on schema estrelinha to estrelinha;
            grant select on all tables in schema estrelinha to estrelinha;
          end if;
        end $$
        """
    )


def upgrade() -> None:
    recriar()


def downgrade() -> None:
    # Volta para as views restritas da migration anterior.
    import importlib.util
    from pathlib import Path

    caminho = Path(__file__).with_name("e7a4c19b5d20_estrelinha_views_de_leitura.py")
    spec = importlib.util.spec_from_file_location("anterior", caminho)
    anterior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(anterior)
    op.execute("drop schema if exists estrelinha cascade")
    anterior.upgrade()
