"""Entrada e saida de criancas e da importacao de listas."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class CriancaIn(BaseModel):
    edicao_id: int
    instituicao_id: int
    codigo: str = Field(min_length=1, max_length=40)
    nome: str = Field(min_length=3, max_length=180)
    idade: int = Field(ge=0, le=21)
    sexo: str = Field(pattern="^[MF]$")
    dia_evento_id: int | None = None
    observacoes: str | None = None


class CriancaEditar(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=40)
    nome: str | None = Field(default=None, min_length=3, max_length=180)
    idade: int | None = Field(default=None, ge=0, le=21)
    sexo: str | None = Field(default=None, pattern="^[MF]$")
    dia_evento_id: int | None = None
    observacoes: str | None = None


class CriancaOut(BaseModel):
    id: int
    edicao_id: int
    instituicao_id: int
    instituicao: str
    codigo: str
    nome: str
    idade: int
    sexo: str
    dia_evento_id: int | None
    dia_evento: date | None
    observacoes: str | None
    checkin_em: datetime | None

    # O panorama da crianca, para a tela ser um painel de controle e nao so
    # uma lista de nomes.
    tem_padrinho_cesta: bool = False
    tem_padrinho_festa: bool = False
    cartoes: int = 0
    kit_status: str = "pendente"


class PaginaCriancas(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    itens: list[CriancaOut]


class LinhaImportada(BaseModel):
    linha: int
    codigo: str
    nome: str
    idade: int | None
    sexo: str | None
    instituicao_id: int | None
    instituicao: str | None
    observacoes: str | None
    erros: list[str]
    avisos: list[str]
    valida: bool


class PreviaImportacao(BaseModel):
    id: str
    total: int
    validas: int
    com_erro: int
    com_aviso: int
    colunas_reconhecidas: dict[str, str]
    colunas_ignoradas: list[str]
    linhas: list[LinhaImportada]


class ResultadoImportacao(BaseModel):
    importadas: int
    ignoradas: int


class CriancasEmLote(BaseModel):
    """Mudanca aplicada a varias criancas de uma vez."""

    criancas: list[int] = Field(min_length=1)
    # None e um valor legitimo: tira a crianca do dia.
    dia_evento_id: int | None = None
    definir_dia: bool = False
    instituicao_id: int | None = None


class ResumoInstituicao(BaseModel):
    """Uma aba da tela de criancas."""

    instituicao_id: int
    instituicao: str
    criancas: int
    sem_padrinho: int
    sem_cartao: int
    sem_dia: int
