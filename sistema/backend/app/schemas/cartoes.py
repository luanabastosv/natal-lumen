"""Entrada e saida dos cartoes de agradecimento."""

from datetime import datetime

from pydantic import BaseModel, Field


class ArquivoDoLote(BaseModel):
    """Uma foto do lote, ja casada (ou nao) com uma crianca."""

    # Posicao no lote. E por ele que a conferencia pede a imagem grande:
    # `/cartoes/lote/{id}/{indice}/imagem`.
    indice: int
    arquivo: str
    codigo: str | None = None
    crianca_id: int | None = None
    crianca_nome: str | None = None
    instituicao: str | None = None
    # Miniatura em base64, para conferir a foto certa antes de gravar.
    miniatura: str | None = None
    erros: list[str] = []
    avisos: list[str] = []
    valida: bool = False


class PreviaLote(BaseModel):
    id: str
    tipo: str
    total: int
    validas: int
    com_erro: int
    arquivos: list[ArquivoDoLote]


class ResultadoLote(BaseModel):
    gravados: int
    ignorados: int


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
