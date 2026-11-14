"""estrelinha: views de leitura para a assistente no Claude

Revision ID: e7a4c19b5d20
Revises: b6d3f8a2e914
Create Date: 2026-11-14 21:30:00

A Estrelinha (conector MCP em app/routers/estrelinha.py) responde perguntas
da coordenacao escrevendo SQL livre. Ela nunca enxerga as tabelas: so estas
views, no schema `estrelinha`, que deixam de fora contato, senha, comprovante,
nome de crianca e texto livre de saude. A usuaria do Postgres `estrelinha`
(criada a mao no servidor, ver docs/ESTRELINHA.md) so tem SELECT aqui.

Para mostrar mais uma coluna a ela, crie uma migration nova que recria a view.
"""
from alembic import op

revision = "e7a4c19b5d20"
down_revision = "b6d3f8a2e914"
branch_labels = None
depends_on = None

VIEWS = {
    "cidades": "select id, nome, uf, ativo from public.cidades",
    "edicoes": """
        select e.id, e.ano, e.nome, e.cidade_id, c.nome as cidade, c.uf,
               e.valor_cesta, e.valor_festa, e.ativa, e.festa_liberada_em
        from public.edicoes e join public.cidades c on c.id = e.cidade_id""",
    "dias_evento": "select id, edicao_id, data, descricao from public.dias_evento",
    "instituicoes": "select id, cidade_id, nome, sigla, ativo from public.instituicoes",
    "grupos": "select id, cidade_id, nome from public.grupos",
    "instituicao_dia": """
        select id, edicao_id, instituicao_id, dia_evento_id, onibus, nucleo, cor_bata_nome
        from public.instituicao_dia""",
    # Sem nome da crianca: a Estrelinha conta e cruza, nao identifica.
    "criancas": """
        select id, edicao_id, instituicao_id, dia_evento_id, codigo, idade, sexo,
               checkin_em, falta_em, desistiu_em
        from public.criancas""",
    # Sem whatsapp, email e observacoes.
    "padrinhos": """
        select id, edicao_id, nome, membro_ser_feliz, interesse_mensal, criado_em
        from public.padrinhos""",
    "apadrinhamentos": """
        select id, crianca_id, padrinho_id, tipo, valor, pagamento_id, vai_ao_evento, criado_em
        from public.apadrinhamentos""",
    # Sem comprovante nem id do Mercado Pago.
    "pagamentos": "select id, padrinho_id, valor, data, forma, conferido from public.pagamentos",
    "cobrancas_cartao": """
        select id, padrinho_id, valor, status, status_mercadopago, expira_em,
               criado_em, encerrada_em, pagamento_id
        from public.cobrancas_cartao""",
    "envios_cartao": "select id, apadrinhamento_id, status, criado_em from public.envios_cartao",
    "cartoes": "select id, crianca_id, tipo, status, enviado_em, criado_em from public.cartoes",
    # So os sim/nao; o texto de qual necessidade ou restricao fica de fora.
    "autorizacoes": """
        select id, crianca_id, necessidade_especial, restricao_alimentar, tem_observacao, criado_em
        from public.autorizacoes""",
    "kits": "select id, crianca_id, status, montado_em, conferido_em from public.kits",
    "compras": """
        select id, edicao_id, descricao, categoria, quantidade, valor_total, fornecedor, data
        from public.compras""",
    # Sem o nome do doador.
    "recebimentos": """
        select id, edicao_id, descricao, categoria, valor, data, forma, conferido, criado_em
        from public.recebimentos""",
}


def upgrade() -> None:
    op.execute("create schema if not exists estrelinha")
    for nome, consulta in VIEWS.items():
        op.execute(f"create or replace view estrelinha.{nome} as {consulta}")
    # A usuaria e criada a mao no servidor (tem senha). Se ja existir, recebe
    # leitura nas views; se nao, o comando do docs/ESTRELINHA.md faz o grant.
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


def downgrade() -> None:
    op.execute("drop schema if exists estrelinha cascade")
