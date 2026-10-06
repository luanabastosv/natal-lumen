"""Entrada e saida de kits e check-in.

As compras viraram as SAIDAS do financeiro e moram em schemas/financeiro.py.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


class KitOut(BaseModel):
    id: int | None
    crianca_id: int
    # O que a equipe de estrutura precisa TER NA MAO para montar: o codigo e o
    # nome para achar a crianca na pilha, a instituicao para separar as caixas,
    # e idade e sexo porque e por eles que se escolhe o presente.
    crianca_codigo: str
    crianca_nome: str
    idade: int
    sexo: str
    instituicao_id: int
    instituicao: str
    dia_evento: date | None
    dia_evento_descricao: str | None = None
    status: str
    montado_em: datetime | None
    # Kit de quem desistiu nao deve ser montado. Vem para a lista em vez de ser
    # filtrado fora: some-lo faria a conta da equipe nao bater com a lista
    # impressa, e ninguem entenderia por que faltam tres caixas.
    desistiu_em: datetime | None
    observacoes: str | None


class InstituicaoKits(BaseModel):
    """Uma aba da tela de kits: a instituicao e o que falta montar nela."""

    instituicao_id: int
    instituicao: str
    sigla: str | None
    total: int
    montados: int
    # Contadas a parte: elas entram no total (a lista as mostra), mas nao sao
    # trabalho — a equipe precisa saber que aquelas nao viram caixa.
    desistentes: int


class PaginaKits(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    itens: list[KitOut]
    # Quantas em cada estado, para a equipe saber onde esta.
    resumo: dict[str, int]


class KitMudar(BaseModel):
    criancas: list[int] = Field(min_length=1)
    status: str = Field(pattern="^(pendente|montado)$")
    observacoes: str | None = None


class CheckinIn(BaseModel):
    # O QR do cracha traz edicao e codigo; digitado, so o codigo.
    codigo: str = Field(min_length=1, max_length=40)
    edicao_id: int


class DiaCheckin(BaseModel):
    data: date
    descricao: str | None = None


class CheckinAberto(BaseModel):
    """Se o check-in desta edicao esta aberto hoje, e quando ele abre."""

    aberto: bool
    # O dia de hoje no fuso de Sao Paulo, que e o que vale para o evento.
    hoje: date
    # Os dias do evento da edicao, para a tela dizer quando o check-in abre.
    dias: list[DiaCheckin]


class CheckinLinha(BaseModel):
    """Uma crianca na lista de check-in do monitor.

    So o que se le de relance no onibus: codigo, nome e se ja confirmou. Kit e
    padrinho nao entram — nao sao assunto da monitoria.
    """

    crianca_id: int
    codigo: str
    nome: str
    instituicao_id: int
    instituicao: str
    checkin_em: datetime | None
    # Quem desistiu continua na lista, riscado, como nas outras telas: some-la
    # faria a conta do monitor nao bater com a lista de papel.
    desistiu_em: datetime | None


class CheckinOut(BaseModel):
    crianca_id: int
    nome: str
    idade: int
    instituicao: str
    dia_evento: date | None
    dia_evento_descricao: str | None = None
    ja_tinha_checkin: bool
    checkin_em: datetime
    # Nulo = quem fez o check-in nao monta kit, e nao recebe o estado dele.
    kit_status: str | None = None
    # Avisos para quem esta na porta: dia errado, sem padrinho, etc.
    avisos: list[str]
