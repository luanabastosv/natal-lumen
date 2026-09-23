"""Modelos de acesso: usuarios, perfis, permissoes, vinculos e log."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.tipos import CriadoEm, MomentoOpcional, TipoToken, valores


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    whatsapp: Mapped[str | None] = mapped_column(String(30))

    # Nulo ate o voluntario definir a senha pelo link de primeiro acesso.
    senha_hash: Mapped[str | None] = mapped_column(String(255))

    admin_geral: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    ultimo_login: Mapped[MomentoOpcional]
    tentativas_falhas: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    bloqueado_ate: Mapped[MomentoOpcional]
    criado_em: Mapped[CriadoEm]

    # passive_deletes deixa o CASCADE do banco fazer o trabalho. Sem isso o
    # SQLAlchemy tenta anular usuario_id, que e NOT NULL, e a remocao quebra.
    edicoes: Mapped[list["UsuarioEdicao"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", passive_deletes=True
    )
    tokens: Mapped[list["TokenAcesso"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def tem_senha(self) -> bool:
        return self.senha_hash is not None


class Perfil(Base):
    __tablename__ = "perfis"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(255))

    permissoes: Mapped[list["Permissao"]] = relationship(
        secondary="perfil_permissoes", back_populates="perfis"
    )


class Permissao(Base):
    __tablename__ = "permissoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    descricao: Mapped[str | None] = mapped_column(String(255))

    perfis: Mapped[list[Perfil]] = relationship(
        secondary="perfil_permissoes", back_populates="permissoes"
    )


class PerfilPermissao(Base):
    """Tabela de ligacao entre perfil e permissao (chave composta)."""

    __tablename__ = "perfil_permissoes"

    perfil_id: Mapped[int] = mapped_column(
        ForeignKey("perfis.id", ondelete="CASCADE"), primary_key=True
    )
    permissao_id: Mapped[int] = mapped_column(
        ForeignKey("permissoes.id", ondelete="CASCADE"), primary_key=True
    )


class UsuarioEdicao(Base):
    """Vinculo do usuario com uma edicao, e o perfil que ele exerce nela.

    E a base de todo o isolamento de dados: as consultas sao filtradas pelas
    edicoes em que o usuario tem vinculo ativo.
    """

    __tablename__ = "usuario_edicao"
    __table_args__ = (
        UniqueConstraint("usuario_id", "edicao_id", name="uq_usuario_edicao"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edicao_id: Mapped[int] = mapped_column(
        ForeignKey("edicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    perfil_id: Mapped[int] = mapped_column(ForeignKey("perfis.id"), nullable=False)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    usuario: Mapped[Usuario] = relationship(back_populates="edicoes")
    edicao: Mapped["Edicao"] = relationship(back_populates="usuarios")  # noqa: F821
    perfil: Mapped[Perfil] = relationship()
    instituicoes: Mapped[list["UsuarioInstituicao"]] = relationship(
        back_populates="usuario_edicao", cascade="all, delete-orphan", passive_deletes=True
    )


class UsuarioInstituicao(Base):
    """Instituicoes sob responsabilidade de um usuario dentro de uma edicao.

    Comissarios e monitores so alcancam criancas destas instituicoes (o escape e
    a busca por codigo exato, registrada em log). Coordenacao e estrutura veem a
    edicao inteira.

    A ligacao e feita ao vinculo (usuario_edicao) e nao a usuario + edicao
    soltos: assim a atribuicao nao pode existir sem o vinculo, e cai junto com ele.

    Atencao: nao ha FK garantindo que a instituicao seja da mesma cidade da
    edicao — instituicoes pertencem a cidade, edicoes tambem, e uma FK simples
    nao cruza as duas. Isso e validado na aplicacao, no momento da atribuicao.
    """

    __tablename__ = "usuario_instituicao"
    __table_args__ = (
        UniqueConstraint(
            "usuario_edicao_id", "instituicao_id", name="uq_usuario_instituicao"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_edicao_id: Mapped[int] = mapped_column(
        ForeignKey("usuario_edicao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instituicao_id: Mapped[int] = mapped_column(
        ForeignKey("instituicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    usuario_edicao: Mapped[UsuarioEdicao] = relationship(back_populates="instituicoes")
    instituicao: Mapped["Instituicao"] = relationship()  # noqa: F821


class TokenAcesso(Base):
    """Token de uso unico para primeiro acesso ou redefinicao de senha.

    Guardado como hash: o valor em claro existe so no link enviado ao voluntario.
    """

    __tablename__ = "tokens_acesso"
    __table_args__ = (
        CheckConstraint(
            "tipo IN " + str(valores(TipoToken)), name="ck_tokens_acesso_tipo"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(nullable=False)
    usado_em: Mapped[MomentoOpcional]

    usuario: Mapped[Usuario] = relationship(back_populates="tokens")


class LogAtividade(Base):
    """Registro de acoes sensiveis (LGPD).

    usuario_id e nulo de proposito: tentativas de login com email inexistente
    tambem precisam ser registradas.
    """

    __tablename__ = "log_atividades"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), index=True
    )
    acao: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    tabela: Mapped[str | None] = mapped_column(String(60))
    registro_id: Mapped[int | None] = mapped_column(Integer)
    detalhes: Mapped[dict | None] = mapped_column(JSONB)
    criado_em: Mapped[CriadoEm]

    usuario: Mapped[Usuario | None] = relationship()
