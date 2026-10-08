"""As ave-marias rezadas por cada crianca."""

from datetime import date

from sqlalchemy import Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tipos import CriadoEm


class AveMaria(Base):
    """Um convite de oracao que apareceu: uma ave-maria por aquela crianca.

    A linha nasce quando o convite do dia e entregue a alguem (ver
    servicos/oracao.py), e a ficha da crianca conta as linhas dela. A mesma
    crianca aparecendo para outra pessoa, ou para a mesma pessoa noutro dia, e
    mais uma ave-maria — e a conta que se quer ter na mao no dia do evento.

    A chave unica e o que impede a conta de inflar: o convite de uma pessoa
    num dia e sempre a mesma crianca, e quem abre no celular e depois no
    computador viu UM convite, nao dois.
    """

    __tablename__ = "ave_marias"
    __table_args__ = (
        UniqueConstraint("crianca_id", "usuario_id", "dia", name="uq_ave_marias_crianca_usuario_dia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crianca_id: Mapped[int] = mapped_column(
        ForeignKey("criancas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SET NULL e nao CASCADE: quem rezou pode sair do sistema, e a ave-maria
    # que ela rezou continua rezada.
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    # O dia no fuso de Brasilia, o mesmo que escolheu a crianca.
    dia: Mapped[date] = mapped_column(Date, nullable=False)
    criado_em: Mapped[CriadoEm]
