"""Entrada e saida das rotas de autenticacao."""

from pydantic import BaseModel, EmailStr, Field


class LoginIn(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1)


class DefinirSenhaIn(BaseModel):
    token: str = Field(min_length=10)
    senha: str = Field(min_length=8)


class EsqueciSenhaIn(BaseModel):
    email: EmailStr


class VinculoOut(BaseModel):
    edicao_id: int
    edicao: str
    cidade: str
    ano: int
    perfil: str
    permissoes: list[str]
    # So preenchido para comissario e monitor, que respondem por instituicoes.
    instituicoes: list[int] | None = None
    # O comissario ve apenas as criancas atribuidas a ele, e nao a lista
    # inteira da instituicao. O frontend usa isto para nao oferecer o filtro
    # por responsavel a quem so tem um responsavel possivel: ele mesmo.
    so_criancas_atribuidas: bool = False


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    admin_geral: bool
    # Uniao das permissoes, para o frontend esconder menus. A decisao real e
    # sempre do backend, por edicao.
    permissoes: list[str]
    vinculos: list[VinculoOut]


class MensagemOut(BaseModel):
    mensagem: str
    # Em desenvolvimento devolvemos o link, que em producao iria por email.
    link: str | None = None
