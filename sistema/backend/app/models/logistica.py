"""Modelos de logistica: os cartoes e as autorizacoes das criancas, e os kits.

Compras saiu daqui para models/financeiro.py: ela e uma SAIDA de dinheiro,
e passou a dividir tela com os recebimentos.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.tipos import (
    CriadoEm,
    MomentoOpcional,
    StatusCartao,
    StatusKit,
    TipoApadrinhamento,
    valores,
)


class Cartao(Base):
    """O cartao que a crianca escreve para o padrinho, um por tipo (cesta e festa).

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


class Autorizacao(Base):
    """A autorizacao assinada pelo responsavel da crianca, uma por crianca.

    Sobe pelo mesmo caminho dos cartoes — a pilha digitalizada, com o codigo
    da crianca no nome do arquivo — e mora na mesma tela, numa aba propria.
    Tabela separada, e nao um terceiro tipo de cartao, porque ela nao e
    agradecimento: nao tem padrinho, nao e enviada a ninguem, e vai ganhar
    campos que so ela tem.
    """

    __tablename__ = "autorizacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    crianca_id: Mapped[int] = mapped_column(
        ForeignKey("criancas.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Caminho relativo dentro de ARQUIVOS_DIR/autorizacoes/{cidade}/{ano}/.
    arquivo: Mapped[str] = mapped_column(String(500), nullable=False)

    # O que o monitor le na autorizacao e marca na conferencia, uma crianca por
    # vez. Sim/nao obrigatorio na entrada; o "qual" so existe quando e sim.
    # Nulos so nas autorizacoes que subiram antes de o formulario existir.
    necessidade_especial: Mapped[bool | None] = mapped_column(Boolean)
    necessidade_especial_qual: Mapped[str | None] = mapped_column(Text)
    restricao_alimentar: Mapped[bool | None] = mapped_column(Boolean)
    restricao_alimentar_qual: Mapped[str | None] = mapped_column(Text)
    tem_observacao: Mapped[bool | None] = mapped_column(Boolean)
    observacao: Mapped[str | None] = mapped_column(Text)

    monitor_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    criado_em: Mapped[CriadoEm]

    crianca: Mapped["Crianca"] = relationship(back_populates="autorizacao")  # noqa: F821


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
    # Quando e por quem o kit foi MONTADO. Eram `entregue_em`/`entregue_por`,
    # da epoca em que havia um estado de entrega; viraram isto no mesmo dia em
    # que o estado saiu, em vez de serem apagadas — a data de quem ja tinha
    # mexido no kit continua valendo.
    montado_em: Mapped[MomentoOpcional]
    montado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    # A segunda pessoa que abre a caixa e confere: quem monta nao enxerga o
    # proprio erro. So existe em kit montado — desmontar apaga a conferencia.
    conferido_em: Mapped[MomentoOpcional]
    conferido_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    # Os NOMES de quem montou e de quem conferiu, como a equipe escreve na
    # "Montagem + Conferencia" da instituicao. Texto, e nao usuario: quem
    # monta e confere as caixas e voluntario do dia, e quase nunca tem conta
    # no sistema. `montado_por`/`conferido_por` continuam guardando QUEM
    # registrou, para o rastro.
    montado_por_nome: Mapped[str | None] = mapped_column(String(120))
    conferido_por_nome: Mapped[str | None] = mapped_column(String(120))
    observacoes: Mapped[str | None] = mapped_column(Text)

    crianca: Mapped["Crianca"] = relationship(back_populates="kit")  # noqa: F821
    # `selectin`: a lista de kits traz quinhentas linhas de uma vez, e o nome
    # de quem montou e de quem conferiu sai numa consulta so para todas.
    montador: Mapped["Usuario | None"] = relationship(  # noqa: F821
        foreign_keys=[montado_por], lazy="selectin"
    )
    conferente: Mapped["Usuario | None"] = relationship(  # noqa: F821
        foreign_keys=[conferido_por], lazy="selectin"
    )
