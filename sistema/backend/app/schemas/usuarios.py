"""Entrada e saida de usuarios e vinculos."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UsuarioIn(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    email: EmailStr
    whatsapp: str | None = Field(default=None, max_length=30)


class UsuarioEditar(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=160)
    whatsapp: str | None = Field(default=None, max_length=30)
    ativo: bool | None = None


class VinculoIn(BaseModel):
    edicao_id: int
    perfil_id: int
    # Vazio significa "sem instituicao atribuida" — e para comissario e monitor
    # isso quer dizer que ainda nao alcancam nenhuma crianca.
    instituicoes: list[int] = Field(default_factory=list)


class VinculoEditar(BaseModel):
    perfil_id: int | None = None
    ativo: bool | None = None
    instituicoes: list[int] | None = None


class VinculoDetalhe(BaseModel):
    id: int
    edicao_id: int
    edicao: str
    cidade: str
    ano: int
    perfil_id: int
    perfil: str
    ativo: bool
    instituicoes: list[int]
    # So os perfis filtrados por instituicao usam a lista acima.
    filtrado_por_instituicao: bool


class UsuarioDetalhe(BaseModel):
    id: int
    nome: str
    email: str
    whatsapp: str | None
    admin_geral: bool
    ativo: bool
    tem_senha: bool
    bloqueado: bool
    ultimo_login: datetime | None
    criado_em: datetime
    vinculos: list[VinculoDetalhe]


class UsuarioCriado(BaseModel):
    usuario: UsuarioDetalhe
    # Link de primeiro acesso, para a coordenacao mandar por WhatsApp.
    link: str
    expira_em: datetime
