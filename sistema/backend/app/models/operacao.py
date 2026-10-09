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


class Grupo(Base):
    """Grupo da comunidade a que um comissario pertence.

    Pertence a CIDADE e atravessa os anos, como a instituicao: o grupo Elyon de
    2026 e o mesmo de 2027, ainda que o comissario mude. Por isso a sugestao
    continua aparecendo na edicao seguinte, em vez de a cidade recomecar do zero
    todo mes de janeiro.

    Nao ha tela de cadastro de grupos: eles nascem do proprio formulario de
    usuario, quando a coordenacao atribui a funcao de comissario. Dai o
    `nome_normalizado` — sem ele "Elyon", "elyon" e "Élyon" virariam tres grupos
    diferentes na lista de sugestoes, que existe justamente para isso nao
    acontecer. A unicidade e por ele; `nome` guarda a grafia de quem cadastrou
    primeiro, e e o que aparece na tela.
    """

    __tablename__ = "grupos"
    __table_args__ = (
        UniqueConstraint("cidade_id", "nome_normalizado", name="uq_grupos_cidade_nome"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cidade_id: Mapped[int] = mapped_column(
        ForeignKey("cidades.id"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    nome_normalizado: Mapped[str] = mapped_column(String(120), nullable=False)

    cidade: Mapped[Cidade] = relationship()


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
        CheckConstraint("onibus >= 0", name="ck_instituicao_dia_onibus"),
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

    # Quantos onibus buscam esta instituicao no dia dela. Mora aqui, e nao no
    # cadastro da instituicao, porque e numero de UM ano: a escola que precisou
    # de dois onibus em 2026 pode precisar de um em 2027. Zero e o estado
    # honesto de quem ainda nao fechou o transporte — e nao "nao precisa".
    onibus: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
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

    # Comissario responsavel por ESTA crianca: quem cobra o padrinho, quem
    # busca o cartao. E tambem quem a ALCANCA — a instituicao e atendida por um
    # TIME de comissarios (2, 3), mas cada um so ve as criancas com o nome dele
    # aqui; a lista inteira da instituicao e da coordenacao e do monitor.
    # Nulo = a instituicao ja esta atribuida ao time, mas esta crianca ainda
    # nao tem nome ao lado — e entao nenhum comissario a ve, so a coordenacao,
    # que e quem distribui a lista.
    comissario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), index=True
    )

    checkin_em: Mapped[MomentoOpcional]
    checkin_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    # Faltou ao evento: marcado no check-in, no dia. Exclui o check-in — a
    # crianca chegou OU faltou —, e e diferente de desistir, que e o aviso de
    # antes. Sem nenhum dos dois, ela ainda nao foi marcada.
    falta_em: Mapped[MomentoOpcional]
    falta_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )

    # O recado do comissario sobre a crianca ("a mae pediu tamanho 8", "irmao
    # do EA12"). Separado de `observacoes`, que chega da lista da instituicao:
    # o comissario escrever ali apagaria o que a escola mandou.
    observacao_comissario: Mapped[str | None] = mapped_column(Text)

    # Desistiu de ir ao evento. Nao apaga a crianca: ela continua na lista,
    # riscada, porque o cartao, o kit e o padrinho dela ja existem e alguem
    # ainda vai ter de decidir o que fazer com cada um. Voltar atras e so
    # limpar estes dois campos.
    desistiu_em: Mapped[MomentoOpcional]
    desistiu_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )

    edicao: Mapped[Edicao] = relationship(back_populates="criancas")
    instituicao: Mapped[Instituicao] = relationship(back_populates="criancas")
    dia_evento: Mapped[DiaEvento | None] = relationship(back_populates="criancas")
    comissario: Mapped["Usuario | None"] = relationship(  # noqa: F821
        foreign_keys=[comissario_id]
    )
    apadrinhamentos: Mapped[list["Apadrinhamento"]] = relationship(  # noqa: F821
        back_populates="crianca"
    )
    cartoes: Mapped[list["Cartao"]] = relationship(back_populates="crianca")  # noqa: F821
    kit: Mapped["Kit | None"] = relationship(back_populates="crianca")  # noqa: F821
    autorizacao: Mapped["Autorizacao | None"] = relationship(  # noqa: F821
        back_populates="crianca"
    )

    @property
    def primeiro_nome(self) -> str:
        """O padrinho recebe apenas o primeiro nome e a idade da crianca."""
        return self.nome.strip().split(" ")[0]
