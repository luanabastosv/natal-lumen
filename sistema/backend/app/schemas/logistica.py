"""Entrada e saida de kits e check-in.

As compras viraram as SAIDAS do financeiro e moram em schemas/financeiro.py.
"""

from datetime import date, datetime

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
