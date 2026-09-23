"""Entrada e saida de padrinhos, apadrinhamentos e pagamentos."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class PadrinhoIn(BaseModel):
    edicao_id: int
    nome: str = Field(min_length=3, max_length=180)
    whatsapp: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    observacoes: str | None = None


class PadrinhoEditar(BaseModel):
    nome: str | None = Field(default=None, min_length=3, max_length=180)
    whatsapp: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    observacoes: str | None = None


class ApadrinhamentoResumo(BaseModel):
    id: int
    crianca_id: int
    # O padrinho recebe so o primeiro nome e a idade da crianca.
    crianca_primeiro_nome: str
    crianca_idade: int
    tipo: str
    valor: Decimal
    pago: bool
    vai_ao_evento: bool | None


class PadrinhoOut(BaseModel):
    id: int
    edicao_id: int
    edicao: str
    cidade: str
    ano: int
    nome: str
    whatsapp: str | None
    email: str | None
    observacoes: str | None
    criado_em: datetime
    apadrinhamentos: list[ApadrinhamentoResumo]
    total_combinado: Decimal
    total_pago: Decimal


class PaginaPadrinhos(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    itens: list[PadrinhoOut]


class ApadrinhamentoIn(BaseModel):
    crianca_id: int
    padrinho_id: int
    tipo: str = Field(pattern="^(cesta|festa)$")
    # Em branco usa o valor da edicao da crianca.
    valor: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    vai_ao_evento: bool | None = None


class ApadrinhamentoEditar(BaseModel):
    valor: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    vai_ao_evento: bool | None = None


class PagamentoIn(BaseModel):
    padrinho_id: int
    valor: Decimal = Field(gt=0, decimal_places=2)
    data: date
    forma: str | None = Field(default=None, max_length=40)
    # Apadrinhamentos que este pagamento quita.
    apadrinhamentos: list[int] = Field(default_factory=list)


class PagamentoEditar(BaseModel):
    valor: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    data: date | None = None
    forma: str | None = Field(default=None, max_length=40)
    conferido: bool | None = None
    apadrinhamentos: list[int] | None = None


class PagamentoOut(BaseModel):
    id: int
    padrinho_id: int
    padrinho: str
    valor: Decimal
    data: date
    forma: str | None
    conferido: bool
    comprovante_arquivo: str | None
    apadrinhamentos: list[int]


class PaginaPagamentos(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    itens: list[PagamentoOut]
