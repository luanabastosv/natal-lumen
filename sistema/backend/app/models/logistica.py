"""Modelos de logistica: cartoes, kits e compras."""

from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.tipos import (
    CriadoEm,
    Dinheiro,
    MomentoOpcional,
    StatusCartao,
    StatusKit,
    TipoApadrinhamento,
    valores,
)


class Cartao(Base):
    """Cartao de agradecimento escrito pela crianca, um por tipo.

    O destinatario nao fica gravado aqui: e encontrado por
    crianca + tipo -> apadrinhamento -> padrinho. Assim o cartao pode ser
    digitalizado antes de a crianca ter padrinho.
    """

    __tablename__ = "cartoes"
    __table_args__ = (
        UniqueConstraint("crianca_id", "tipo", name="uq_cartoes_crianca_tipo"),
        CheckConstraint(
            "tipo IN " + str(valores(TipoApadrinhamento)), name="ck_cartoes_tipo"
        ),
        CheckConstraint(
            "status IN " + str(valores(StatusCartao)), name="ck_cartoes_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crianca_id: Mapped[int] = mapped_column(
        ForeignKey("criancas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)

    # Caminho relativo dentro de ARQUIVOS_DIR/cartoes/{cidade}/{ano}/.
    arquivo: Mapped[str] = mapped_column(String(500), nullable=False)
    texto_ocr: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=StatusCartao.DIGITALIZADO.value,
        server_default=text(f"'{StatusCartao.DIGITALIZADO.value}'"),
    )

    monitor_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    enviado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    enviado_em: Mapped[MomentoOpcional]
    criado_em: Mapped[CriadoEm]

    crianca: Mapped["Crianca"] = relationship(back_populates="cartoes")  # noqa: F821


class Kit(Base):
    """Cesta/presente/kit de higiene de uma crianca. Um kit por crianca."""

    __tablename__ = "kits"
    __table_args__ = (
        CheckConstraint("status IN " + str(valores(StatusKit)), name="ck_kits_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crianca_id: Mapped[int] = mapped_column(
        ForeignKey("criancas.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=StatusKit.PENDENTE.value,
        server_default=text(f"'{StatusKit.PENDENTE.value}'"),
    )
    entregue_em: Mapped[MomentoOpcional]
    entregue_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    observacoes: Mapped[str | None] = mapped_column(Text)

    crianca: Mapped["Crianca"] = relationship(back_populates="kit")  # noqa: F821


class Compra(Base):
    """Compra feita pela equipe de estrutura para uma edicao."""

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
