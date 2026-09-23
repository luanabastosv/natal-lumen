"""Modelos de apadrinhamento: padrinhos, apadrinhamentos e pagamentos."""

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.tipos import CriadoEm, Dinheiro, TipoApadrinhamento, valores


class Padrinho(Base):
    """Pertence a uma edicao (cidade + ano): todo ano sao padrinhos novos.

    O mesmo doador que participa em 2026 e 2027 tem dois registros, um por
    edicao, sem historico ligando os dois. A cidade vem por edicao -> cidade.
    """

    __tablename__ = "padrinhos"

    id: Mapped[int] = mapped_column(primary_key=True)
    edicao_id: Mapped[int] = mapped_column(
        ForeignKey("edicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    whatsapp: Mapped[str | None] = mapped_column(String(30), index=True)
    email: Mapped[str | None] = mapped_column(String(180))
    observacoes: Mapped[str | None] = mapped_column(Text)

    criado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    criado_em: Mapped[CriadoEm]

    edicao: Mapped["Edicao"] = relationship(back_populates="padrinhos")  # noqa: F821
    apadrinhamentos: Mapped[list["Apadrinhamento"]] = relationship(
        back_populates="padrinho"
    )
    pagamentos: Mapped[list["Pagamento"]] = relationship(back_populates="padrinho")


class Pagamento(Base):
    """Um pagamento pode quitar varios apadrinhamentos."""

    __tablename__ = "pagamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    padrinho_id: Mapped[int] = mapped_column(
        ForeignKey("padrinhos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    valor: Mapped[Dinheiro] = mapped_column(nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    forma: Mapped[str | None] = mapped_column(String(40))

    # Caminho relativo dentro de ARQUIVOS_DIR; nunca servido publicamente.
    comprovante_arquivo: Mapped[str | None] = mapped_column(String(500))

    registrado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    conferido: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    padrinho: Mapped[Padrinho] = relationship(back_populates="pagamentos")
    apadrinhamentos: Mapped[list["Apadrinhamento"]] = relationship(
        back_populates="pagamento"
    )


class Apadrinhamento(Base):
    """Liga uma crianca a um padrinho, num dos dois tipos.

    A restricao unica e do lado da crianca: ela tem no maximo um padrinho de
    cesta e um de festa. Um mesmo padrinho pode apadrinhar varias criancas.

    O padrinho pode ser de outra edicao/cidade: apadrinhamento entre cidades e
    permitido, e o registro fica visivel pela edicao do padrinho ou da crianca.
    """

    __tablename__ = "apadrinhamentos"
    __table_args__ = (
        UniqueConstraint("crianca_id", "tipo", name="uq_apadrinhamentos_crianca_tipo"),
        CheckConstraint(
            "tipo IN " + str(valores(TipoApadrinhamento)),
            name="ck_apadrinhamentos_tipo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crianca_id: Mapped[int] = mapped_column(
        ForeignKey("criancas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    padrinho_id: Mapped[int] = mapped_column(
        ForeignKey("padrinhos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)

    # Copiado da edicao no momento do registro: se o valor da edicao mudar
    # depois, o que ja foi combinado com o padrinho nao muda.
    valor: Mapped[Dinheiro] = mapped_column(nullable=False)

    pagamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("pagamentos.id", ondelete="SET NULL"), index=True
    )
    comissario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    vai_ao_evento: Mapped[bool | None] = mapped_column(Boolean)
    criado_em: Mapped[CriadoEm]

    crianca: Mapped["Crianca"] = relationship(back_populates="apadrinhamentos")  # noqa: F821
    padrinho: Mapped[Padrinho] = relationship(back_populates="apadrinhamentos")
    pagamento: Mapped[Pagamento | None] = relationship(back_populates="apadrinhamentos")
