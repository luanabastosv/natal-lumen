"""Visitantes do evento: quem leu o QR Code da pulseira para ver as fotos."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.operacao import DiaEvento
from app.models.tipos import CriadoEm


class Visitante(Base):
    """Uma pessoa que foi ao evento e deixou nome e celular para ver as fotos.

    O dia vem do QR Code da pulseira, e nao de quando a pessoa preencheu: as
    fotos ficam prontas dias depois, e e so entao que a maioria le o QR.

    Um celular conta uma vez por dia. Quem preenche de novo (outro aparelho,
    voltou outro dia para rever as fotos) atualiza o nome, sem virar outra
    linha na planilha.
    """

    __tablename__ = "visitantes"
    __table_args__ = (
        UniqueConstraint("dia_evento_id", "celular", name="uq_visitantes_dia_celular"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    edicao_id: Mapped[int] = mapped_column(
        ForeignKey("edicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dia_evento_id: Mapped[int] = mapped_column(
        ForeignKey("dias_evento.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    # So os digitos, com DDD: "85988887777".
    celular: Mapped[str] = mapped_column(String(11), nullable=False)
    criado_em: Mapped[CriadoEm]

    dia_evento: Mapped[DiaEvento] = relationship()
