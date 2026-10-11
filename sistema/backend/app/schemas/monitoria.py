"""O painel da coordenacao da monitoria e a divisao dos dias em nucleos."""

from datetime import date

from pydantic import BaseModel, Field


class CuidadoCrianca(BaseModel):
    """Uma crianca com necessidade especial ou restricao alimentar."""

    crianca_id: int
    codigo: str
    nome: str
    necessidade_especial: str | None
    restricao_alimentar: str | None


class InstituicaoMonitoria(BaseModel):
    instituicao_id: int
    instituicao: str
    sigla: str | None
    dia_evento_id: int | None
    dia_data: date | None
    dia_descricao: str | None
    nucleo: str | None
    cor_bata_nome: str | None
    cor_bata_hex: str | None
    # Sem as desistentes: e quem vai ao evento, e o total contra o qual os
    # cartoes e as autorizacoes se medem.
    criancas: int
    # Cartoes de PAPEL ja digitalizados — o que a crianca escreveu para o
    # padrinho de cesta e o de festa. Nao e quantidade de apadrinhamento.
    cartoes_cesta: int
    cartoes_festa: int
    autorizacoes: int
    cuidados: list[CuidadoCrianca]


class DiaMonitoria(BaseModel):
    dia_evento_id: int | None
    data: date | None
    descricao: str | None
    instituicoes: int
    criancas: int
    necessidade_especial: int
    restricao_alimentar: int


class PainelMonitoria(BaseModel):
    edicao: str
    criancas: int
    cartoes_cesta: int
    cartoes_festa: int
    autorizacoes: int
    necessidade_especial: int
    restricao_alimentar: int
    por_dia: list[DiaMonitoria]
    por_instituicao: list[InstituicaoMonitoria]


class NucleoIn(BaseModel):
    instituicao_id: int
    nucleo: str | None = Field(default=None, pattern="^[ABCD]$")
    cor_bata_nome: str | None = Field(default=None, max_length=40)
    cor_bata_hex: str | None = Field(default=None, pattern="^#[0-9a-fA-F]{6}$")


class NucleosIn(BaseModel):
    instituicoes: list[NucleoIn]
