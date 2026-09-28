"""recebimentos da edicao

O dinheiro que entra fora do apadrinhamento: doacao, patrocinio, rifa. Os
pagamentos dos padrinhos NAO sao copiados para ca — continuam em `pagamentos`,
e a lista do financeiro junta as duas origens na hora de mostrar.

A tabela nasce com comprovante e `conferido` iguais aos de `pagamentos`: na
tela as duas origens viram linhas da mesma lista, com a mesma coluna de
comprovante e a mesma etiqueta de conferido.

Revision ID: c47b3e9a1052
Revises: f2a7c31d94b6
"""

import sqlalchemy as sa
from alembic import op

revision = "c47b3e9a1052"
down_revision = "f2a7c31d94b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recebimentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("edicao_id", sa.Integer(), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=False),
        # Conjunto fechado como texto + CHECK, e nao ENUM nativo: acrescentar
        # uma categoria passa a ser uma migration simples de CHECK.
        sa.Column("categoria", sa.String(length=30), nullable=False),
        sa.Column("valor", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("doador", sa.String(length=180), nullable=True),
        sa.Column("forma", sa.String(length=40), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("comprovante_arquivo", sa.String(length=500), nullable=True),
        sa.Column("comprovante_drive_id", sa.String(length=120), nullable=True),
        sa.Column("comprovante_drive_link", sa.String(length=500), nullable=True),
        sa.Column(
            "conferido",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("registrado_por", sa.Integer(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("valor > 0", name="ck_recebimentos_valor"),
        sa.CheckConstraint(
            "categoria IN ('doacao', 'outros')", name="ck_recebimentos_categoria"
        ),
        # Cai com a edicao, como as compras: recebimento e dinheiro DAQUELA
        # edicao, e nao ha o que fazer com ele depois que ela deixa de existir.
        sa.ForeignKeyConstraint(["edicao_id"], ["edicoes.id"], ondelete="CASCADE"),
        # Quem lancou pode sair do sistema; o lancamento fica.
        sa.ForeignKeyConstraint(["registrado_por"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recebimentos_edicao_id", "recebimentos", ["edicao_id"])
    op.create_index("ix_recebimentos_categoria", "recebimentos", ["categoria"])


def downgrade() -> None:
    op.drop_index("ix_recebimentos_categoria", table_name="recebimentos")
    op.drop_index("ix_recebimentos_edicao_id", table_name="recebimentos")
    op.drop_table("recebimentos")
