"""Entrada e saida de kits, compras e check-in."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class KitOut(BaseModel):
    id: int | None
    crianca_id: int
    crianca_nome: str
    instituicao: str
    dia_evento: date | None
    status: str
    entregue_em: datetime | None
    observacoes: str | None


class PaginaKits(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    itens: list[KitOut]
    # Quantas em cada estado, para a equipe saber onde esta.
    resumo: dict[str, int]


class KitMudar(BaseModel):
    criancas: list[int] = Field(min_length=1)
    status: str = Field(pattern="^(pendente|montado|entregue)$")
    observacoes: str | None = None


class CompraIn(BaseModel):
    edicao_id: int
    descricao: str = Field(min_length=2, max_length=255)
    categoria: str | None = Field(default=None, max_length=80)
    quantidade: int = Field(default=1, gt=0)
    valor_total: Decimal = Field(ge=0, decimal_places=2)
    fornecedor: str | None = Field(default=None, max_length=180)
    data: date


class CompraEditar(BaseModel):
    descricao: str | None = Field(default=None, min_length=2, max_length=255)
    categoria: str | None = Field(default=None, max_length=80)
    quantidade: int | None = Field(default=None, gt=0)
    valor_total: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    fornecedor: str | None = Field(default=None, max_length=180)
    data: date | None = None


class CompraOut(BaseModel):
    id: int
    edicao_id: int
    descricao: str
    categoria: str | None
    quantidade: int
    valor_total: Decimal
    fornecedor: str | None
    data: date
    responsavel: str | None


class PaginaCompras(BaseModel):
    total: int
    itens: list[CompraOut]
    total_gasto: Decimal
    # Gasto por categoria, para o relatorio da edicao.
    por_categoria: dict[str, Decimal]


class CheckinIn(BaseModel):
    # O QR do cracha traz edicao e codigo; digitado, so o codigo.
    codigo: str = Field(min_length=1, max_length=40)
    edicao_id: int


class CheckinOut(BaseModel):
    crianca_id: int
    nome: str
    idade: int
    instituicao: str
    dia_evento: date | None
    ja_tinha_checkin: bool
    checkin_em: datetime
    kit_status: str
    # Avisos para quem esta na porta: dia errado, sem padrinho, etc.
    avisos: list[str]
