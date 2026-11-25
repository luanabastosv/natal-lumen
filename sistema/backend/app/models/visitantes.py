"""Visitantes do evento: quem leu o QR Code da pulseira para ver as fotos."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tipos import CriadoEm


class Visitante(Base):
    """Uma pessoa que foi ao evento e deixou nome e celular para ver as fotos.

    E da edicao, e nao do dia: o QR Code e um so para os dois dias (a pulseira
    que sobra no sabado serve no domingo), entao nao ha como saber em qual
    a pessoa foi — e nao precisa.

    Um celular conta uma vez por edicao. Quem preenche de novo (outro
    aparelho, voltou para rever as fotos) atualiza o nome, sem virar outra
    linha na planilha.
    """

    __tablename__ = "visitantes"
    __table_args__ = (
        UniqueConstraint("edicao_id", "celular", name="uq_visitantes_edicao_celular"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    edicao_id: Mapped[int] = mapped_column(
        ForeignKey("edicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    # So os digitos, com DDD: "85988887777".
    celular: Mapped[str] = mapped_column(String(11), nullable=False)
    criado_em: Mapped[CriadoEm]
