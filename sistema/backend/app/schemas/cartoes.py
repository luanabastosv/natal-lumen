"""Entrada e saida dos cartoes de agradecimento."""

from datetime import datetime

from pydantic import BaseModel, Field


class TextoDetectado(BaseModel):
    texto: str
    confianca: float
    altura: float


class AnaliseCartao(BaseModel):
    id: str
    nome_sugerido: str
    textos: list[TextoDetectado]
    imagem_base64: str
    aviso: str | None = None
    # Crianca encontrada pelo codigo, para o monitor conferir antes de salvar.
    crianca_id: int
    crianca_nome: str
    instituicao: str


class ConfirmarCartao(BaseModel):
    id: str
    crianca_id: int
    tipo: str = Field(pattern="^(cesta|festa)$")
    texto_ocr: str | None = None


class CartaoOut(BaseModel):
    id: int
    crianca_id: int
    crianca_nome: str
    instituicao: str
    tipo: str
    arquivo: str
    texto_ocr: str | None
    status: str
    criado_em: datetime
    enviado_em: datetime | None
    # Quem vai receber este cartao, quando ja houver padrinho.
    padrinho_id: int | None
    padrinho_nome: str | None
    padrinho_whatsapp: str | None


class PaginaCartoes(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    itens: list[CartaoOut]


class MarcarEnviados(BaseModel):
    cartoes: list[int] = Field(min_length=1)
