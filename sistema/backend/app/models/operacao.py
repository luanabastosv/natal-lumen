"""Modelos de operacao: cidades, edicoes, dias, instituicoes e criancas."""

from datetime import date

from sqlalchemy import (
    Boolean,
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
from app.models.tipos import Dinheiro, MomentoOpcional, Sexo, valores


class Cidade(Base):
    __tablename__ = "cidades"
    __table_args__ = (UniqueConstraint("nome", "uf", name="uq_cidades_nome_uf"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    uf: Mapped[str] = mapped_column(String(2), nullable=False)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    edicoes: Mapped[list["Edicao"]] = relationship(back_populates="cidade")
    instituicoes: Mapped[list["Instituicao"]] = relationship(back_populates="cidade")


class Edicao(Base):
    """Uma cidade num ano. E a unidade de isolamento de dados do sistema."""

    __tablename__ = "edicoes"
    __table_args__ = (UniqueConstraint("cidade_id", "ano", name="uq_edicoes_cidade_ano"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cidade_id: Mapped[int] = mapped_column(
        ForeignKey("cidades.id"), nullable=False, index=True
    )
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)

    # Valores padrao do apadrinhamento nesta edicao; podem mudar de ano para ano.
    valor_cesta: Mapped[Dinheiro] = mapped_column(nullable=False)
    valor_festa: Mapped[Dinheiro] = mapped_column(nullable=False)

    ativa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    cidade: Mapped[Cidade] = relationship(back_populates="edicoes")
    dias: Mapped[list["DiaEvento"]] = relationship(back_populates="edicao")
    criancas: Mapped[list["Crianca"]] = relationship(back_populates="edicao")
    padrinhos: Mapped[list["Padrinho"]] = relationship(back_populates="edicao")  # noqa: F821
    usuarios: Mapped[list["UsuarioEdicao"]] = relationship(  # noqa: F821
        back_populates="edicao"
    )


class DiaEvento(Base):
    """Uma edicao pode ter varios dias; cada crianca vai a apenas um."""

    __tablename__ = "dias_evento"

    id: Mapped[int] = mapped_column(primary_key=True)
    edicao_id: Mapped[int] = mapped_column(
        ForeignKey("edicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data: Mapped[date] = mapped_column(Date, nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(160))

    edicao: Mapped[Edicao] = relationship(back_populates="dias")
    criancas: Mapped[list["Crianca"]] = relationship(back_populates="dia_evento")


class Instituicao(Base):
    """Pertence a uma cidade e persiste entre anos (as criancas, nao)."""

    __tablename__ = "instituicoes"
    __table_args__ = (
        UniqueConstraint("cidade_id", "nome", name="uq_instituicoes_cidade_nome"),
        UniqueConstraint("cidade_id", "sigla", name="uq_instituicoes_cidade_sigla"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cidade_id: Mapped[int] = mapped_column(
        ForeignKey("cidades.id"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(180), nullable=False)

    # Prefixo do codigo das criancas: "ES" gera ES00, ES01, ES02...
    # Unica dentro da cidade, para dois codigos iguais nunca apontarem para
    # instituicoes diferentes.
    sigla: Mapped[str | None] = mapped_column(String(6))
    responsavel: Mapped[str | None] = mapped_column(String(160))
    telefone: Mapped[str | None] = mapped_column(String(30))
    endereco: Mapped[str | None] = mapped_column(String(255))
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    cidade: Mapped[Cidade] = relationship(back_populates="instituicoes")
    criancas: Mapped[list["Crianca"]] = relationship(back_populates="instituicao")


class InstituicaoDia(Base):
    """Em que dia da edicao esta instituicao vai.

    O dia e da INSTITUICAO, nao da crianca: se a Escolinha Sol vai no sabado,
    todas as criancas dela vao no sabado. Guardar por crianca deixaria duas
    da mesma escola caindo em dias diferentes.

    criancas.dia_evento_id continua existindo e e mantido em dia a partir daqui
    — as telas de kit, check-in e painel filtram por ele.
    """

    __tablename__ = "instituicao_dia"
    __table_args__ = (
        UniqueConstraint("edicao_id", "instituicao_id", name="uq_instituicao_dia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    edicao_id: Mapped[int] = mapped_column(
        ForeignKey("edicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instituicao_id: Mapped[int] = mapped_column(
        ForeignKey("instituicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dia_evento_id: Mapped[int] = mapped_column(
        ForeignKey("dias_evento.id", ondelete="CASCADE"), nullable=False, index=True
    )

    edicao: Mapped["Edicao"] = relationship()
    instituicao: Mapped["Instituicao"] = relationship()
    dia_evento: Mapped["DiaEvento"] = relationship()


class Crianca(Base):
    """Dado sensivel (LGPD): acesso sempre autenticado, isolado e registrado em log."""

    __tablename__ = "criancas"
    __table_args__ = (
        UniqueConstraint(
            "edicao_id", "instituicao_id", "codigo", name="uq_criancas_edicao_inst_codigo"
        ),
        CheckConstraint("sexo IN " + str(valores(Sexo)), name="ck_criancas_sexo"),
        CheckConstraint("idade >= 0 AND idade <= 21", name="ck_criancas_idade"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    edicao_id: Mapped[int] = mapped_column(
        ForeignKey("edicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instituicao_id: Mapped[int] = mapped_column(
        ForeignKey("instituicoes.id"), nullable=False, index=True
    )
    # Vem do dia da INSTITUICAO (ver InstituicaoDia), nao e editado crianca a
    # crianca. Fica gravado aqui porque kit, check-in e painel filtram por ele.
    dia_evento_id: Mapped[int | None] = mapped_column(
        ForeignKey("dias_evento.id", ondelete="SET NULL"), index=True
    )

    codigo: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(180), nullable=False)
    idade: Mapped[int] = mapped_column(Integer, nullable=False)
    sexo: Mapped[str] = mapped_column(String(1), nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text)

    checkin_em: Mapped[MomentoOpcional]
    checkin_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )

    edicao: Mapped[Edicao] = relationship(back_populates="criancas")
    instituicao: Mapped[Instituicao] = relationship(back_populates="criancas")
    dia_evento: Mapped[DiaEvento | None] = relationship(back_populates="criancas")
    apadrinhamentos: Mapped[list["Apadrinhamento"]] = relationship(  # noqa: F821
        back_populates="crianca"
    )
    cartoes: Mapped[list["Cartao"]] = relationship(back_populates="crianca")  # noqa: F821
    kit: Mapped["Kit | None"] = relationship(back_populates="crianca")  # noqa: F821

    @property
    def primeiro_nome(self) -> str:
        """O padrinho recebe apenas o primeiro nome e a idade da crianca."""
        return self.nome.strip().split(" ")[0]
