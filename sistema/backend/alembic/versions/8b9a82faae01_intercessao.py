"""a equipe de intercessao

Revision ID: 8b9a82faae01
Revises: c7d1f3a92b54
Create Date: 2026-11-06 20:05:20.347287

A planilha manual de intercessao vira sistema:

  1. Nasce a tabela `intercessoes`: uma linha por vivencia (missa, adoracao,
     misterio do terco, jejum) que uma pessoa ofereceu por uma crianca. Uma
     por pessoa, por crianca e por vivencia.
  2. Nascem as permissoes `interceder` (marcar) e `ver_painel_intercessao`
     (o quantitativo no painel).
  3. Nasce o perfil "Intercessao", com ver_criancas e as duas novas. A
     coordenacao da cidade recebe so o painel: marcar e da equipe.

O seed nao roda no deploy, entao tudo vem por aqui.
"""
from alembic import op
import sqlalchemy as sa

revision = "8b9a82faae01"
down_revision = "c7d1f3a92b54"
branch_labels = None
depends_on = None

PERFIL = "Intercessao"
DESCRICAO_PERFIL = "Reza pelas criancas e marca as vivencias de intercessao"
COORDENACAO = "Coordenacao"

# Escritas aqui porque a migracao nao importa o seed.
PERMISSOES = {
    "interceder": "Marcar as intercessoes pelas criancas: missa, adoracao, terco e jejum",
    "ver_painel_intercessao": "Ver o quantitativo da intercessao no painel",
}
DO_PERFIL = ("ver_criancas", "interceder", "ver_painel_intercessao")


def upgrade() -> None:
    op.create_table(
        "intercessoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("crianca_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["crianca_id"], ["criancas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "crianca_id", "usuario_id", "tipo", name="uq_intercessoes_crianca_usuario_tipo"
        ),
        sa.CheckConstraint(
            "tipo IN ('missa', 'adoracao', 'terco', 'jejum')", name="ck_intercessoes_tipo"
        ),
    )
    op.create_index("ix_intercessoes_crianca_id", "intercessoes", ["crianca_id"])

    for codigo, descricao in PERMISSOES.items():
        op.execute(
            f"INSERT INTO permissoes (codigo, descricao) VALUES ('{codigo}', '{descricao}') "
            "ON CONFLICT (codigo) DO NOTHING"
        )
    op.execute(
        f"INSERT INTO perfis (nome, descricao) VALUES ('{PERFIL}', '{DESCRICAO_PERFIL}') "
        "ON CONFLICT (nome) DO NOTHING"
    )
    lista = ", ".join(f"'{p}'" for p in DO_PERFIL)
    op.execute(
        f"""
        INSERT INTO perfil_permissoes (perfil_id, permissao_id)
        SELECT pf.id, pm.id FROM perfis pf, permissoes pm
        WHERE pf.nome = '{PERFIL}' AND pm.codigo IN ({lista})
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO perfil_permissoes (perfil_id, permissao_id)
        SELECT pf.id, pm.id FROM perfis pf, permissoes pm
        WHERE pf.nome = '{COORDENACAO}' AND pm.codigo = 'ver_painel_intercessao'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    lista = ", ".join(f"'{p}'" for p in PERMISSOES)
    op.execute(
        f"DELETE FROM perfil_permissoes WHERE permissao_id IN "
        f"(SELECT id FROM permissoes WHERE codigo IN ({lista}))"
    )
    op.execute(
        f"DELETE FROM perfil_permissoes WHERE perfil_id = (SELECT id FROM perfis WHERE nome = '{PERFIL}')"
    )
    # So sai se ninguem estiver nele, como na monitoria.
    op.execute(
        f"""
        DELETE FROM perfis WHERE nome = '{PERFIL}'
        AND NOT EXISTS (SELECT 1 FROM usuario_edicao WHERE perfil_id = perfis.id)
        """
    )
    op.execute(f"DELETE FROM permissoes WHERE codigo IN ({lista})")
    op.drop_index("ix_intercessoes_crianca_id", table_name="intercessoes")
    op.drop_table("intercessoes")
