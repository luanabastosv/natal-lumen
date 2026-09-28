"""Modelos do financeiro da edicao: o que sai e o que entra.

Sao as duas metades da tela Financeiro, e ficam juntas aqui porque a pergunta
que elas respondem e uma so: quanto a edicao recebeu, quanto gastou, e o que
sobrou. Kits e cartoes, que sao logistica de verdade, seguem em logistica.py.

O dinheiro que entra tem DUAS origens, e so uma delas mora aqui:

    apadrinhamento   `pagamentos` (models/apadrinhamento.py), lancado quando o
                     padrinho paga o que apadrinhou. Ninguem redigita isso no
                     financeiro — seria a mesma verdade escrita em dois lugares.
    esporadico       `recebimentos`, esta tabela: a doacao que chega solta, o
                     patrocinio, a rifa. Nao tem crianca nem padrinho do outro
                     lado, e por isso nao caberia em `pagamentos`.

A tela soma as duas; a base guarda cada uma onde ela nasce.
"""

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tipos import CategoriaRecebimento, CriadoEm, Dinheiro, valores


class Compra(Base):
    """Uma saida de dinheiro da edicao.

    A tabela continua chamada `compras` porque e o que ela era quando nasceu, e
    renomear so trocaria o rotulo: as linhas ja gravadas, as migrations e o
    historico em `log_atividades` apontam todos para este nome. Na tela ela e a
    aba **Saidas**, que e o nome certo do que a coordenacao lanca ali — compra
    de cesta, mas tambem aluguel de som, combustivel, taxa de cartorio.

    `quantidade` nasceu de compra por item (100 cestas) e vale 1 no gasto que
    nao se conta por unidade. Por isso o CHECK e > 0, e nao >= 0.
    """

    __tablename__ = "compras"
    __table_args__ = (
        CheckConstraint("quantidade > 0", name="ck_compras_quantidade"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    edicao_id: Mapped[int] = mapped_column(
        ForeignKey("edicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    categoria: Mapped[str | None] = mapped_column(String(80), index=True)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    valor_total: Mapped[Dinheiro] = mapped_column(nullable=False)
    fornecedor: Mapped[str | None] = mapped_column(String(180))
    responsavel_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    data: Mapped[date] = mapped_column(Date, nullable=False)


class Recebimento(Base):
    """Dinheiro que entrou na edicao FORA do apadrinhamento.

    Pertence a edicao, e nao a um padrinho: e justamente o dinheiro que chega
    sem ter crianca do outro lado — a doacao de uma empresa, o que sobrou da
    rifa, o patrocinio do buffet. Quem doa entra como texto em `doador`, e nao
    como vinculo com `padrinhos`: o doador esporadico nao apadrinha ninguem, e
    cria-lo como padrinho o faria aparecer na lista de quem tem crianca para
    pagar.

    Guarda comprovante como os pagamentos guardam: no disco, espelhado no
    Drive, servido so por rota autenticada. O recibo de uma doacao vale o mesmo
    que o de um apadrinhamento — e a prova de que aquele dinheiro entrou.
    """

    __tablename__ = "recebimentos"
    __table_args__ = (
        CheckConstraint("valor > 0", name="ck_recebimentos_valor"),
        CheckConstraint(
            "categoria IN " + str(valores(CategoriaRecebimento)),
            name="ck_recebimentos_categoria",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    edicao_id: Mapped[int] = mapped_column(
        ForeignKey("edicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)

    # Conjunto fechado, com CHECK: 'doacao' ou 'outros'. Categoria de
    # apadrinhamento nao entra aqui — ver CategoriaRecebimento.
    categoria: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    valor: Mapped[Dinheiro] = mapped_column(nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    doador: Mapped[str | None] = mapped_column(String(180))
    forma: Mapped[str | None] = mapped_column(String(40))
    observacoes: Mapped[str | None] = mapped_column(Text)

    # Os tres campos do comprovante e o `conferido` sao os mesmos de
    # `pagamentos`, com o mesmo significado — e de proposito: na tela do
    # financeiro as duas origens viram linhas da MESMA lista, com a mesma
    # coluna de comprovante e a mesma etiqueta de conferido. Se so metade das
    # linhas pudesse guardar arquivo, a coluna mentiria na outra metade.
    comprovante_arquivo: Mapped[str | None] = mapped_column(String(500))
    comprovante_drive_id: Mapped[str | None] = mapped_column(String(120))
    comprovante_drive_link: Mapped[str | None] = mapped_column(String(500))

    conferido: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    registrado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    criado_em: Mapped[CriadoEm]
