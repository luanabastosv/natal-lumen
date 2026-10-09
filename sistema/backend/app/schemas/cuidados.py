"""Saida da lista de cuidados especiais."""

from datetime import date, datetime

from pydantic import BaseModel


class CriancaComCuidados(BaseModel):
    """Uma crianca com algum cuidado avisado na autorizacao.

    Cada campo de cuidado traz o "qual" que o monitor escreveu, ou nulo
    quando a resposta foi "Nao".
    """

    crianca_id: int
    codigo: str
    nome: str
    idade: int
    sexo: str
    instituicao_id: int
    instituicao: str
    dia_evento_id: int | None
    dia_evento: date | None
    dia_evento_descricao: str | None = None
    necessidade_especial: str | None = None
    restricao_alimentar: str | None = None
    observacao: str | None = None
    desistiu_em: datetime | None = None
