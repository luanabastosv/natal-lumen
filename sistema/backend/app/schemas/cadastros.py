"""Entrada e saida dos cadastros base."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CidadeIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    uf: str = Field(min_length=2, max_length=2)
    ativo: bool = True


class CidadeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    uf: str
    ativo: bool


class EdicaoIn(BaseModel):
    cidade_id: int
    ano: int = Field(ge=2000, le=2100)
    nome: str = Field(min_length=2, max_length=160)
    valor_cesta: Decimal = Field(ge=0, decimal_places=2)
    valor_festa: Decimal = Field(ge=0, decimal_places=2)
    ativa: bool = True


class EdicaoEditar(BaseModel):
    """Cidade e ano nao mudam: sao a identidade da edicao."""

    nome: str | None = Field(default=None, min_length=2, max_length=160)
    valor_cesta: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    valor_festa: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    ativa: bool | None = None


class EdicaoOut(BaseModel):
    id: int
    cidade_id: int
    cidade: str
    uf: str
    ano: int
    nome: str
    valor_cesta: Decimal
    valor_festa: Decimal
    ativa: bool


class DiaIn(BaseModel):
    data: date
    descricao: str | None = Field(default=None, max_length=160)


class DiaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    edicao_id: int
    data: date
    descricao: str | None
    total_criancas: int = 0


class InstituicaoIn(BaseModel):
    cidade_id: int
    nome: str = Field(min_length=2, max_length=180)
    # Em branco o sistema sugere a partir do nome.
    sigla: str | None = Field(default=None, min_length=1, max_length=6)
    responsavel: str | None = Field(default=None, max_length=160)
    telefone: str | None = Field(default=None, max_length=30)
    endereco: str | None = Field(default=None, max_length=255)
    ativo: bool = True


class InstituicaoEditar(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=180)
    sigla: str | None = Field(default=None, min_length=1, max_length=6)
    responsavel: str | None = Field(default=None, max_length=160)
    telefone: str | None = Field(default=None, max_length=30)
    endereco: str | None = Field(default=None, max_length=255)
    ativo: bool | None = None


class InstituicaoOut(BaseModel):
    id: int
    cidade_id: int
    cidade: str
    nome: str
    sigla: str | None
    responsavel: str | None
    telefone: str | None
    endereco: str | None
    ativo: bool


class PerfilOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    descricao: str | None
