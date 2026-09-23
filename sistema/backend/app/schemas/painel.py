"""Numeros do painel e dos relatorios."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class Contagem(BaseModel):
    rotulo: str
    total: int
    # Para barras de progresso: quanto isto representa do total geral.
    de: int


class ResumoEdicao(BaseModel):
    edicao_id: int
    edicao: str
    cidade: str
    ano: int

    criancas: int
    instituicoes: int

    # Apadrinhamento: cada crianca precisa de dois padrinhos.
    apadrinhamentos_possiveis: int
    apadrinhamentos_feitos: int
    cesta_feitos: int
    festa_feitos: int
    criancas_sem_nenhum_padrinho: int
    criancas_completas: int

    padrinhos: int
    valor_combinado: Decimal
    valor_pago: Decimal

    # Cartoes: dois por crianca.
    cartoes_possiveis: int
    cartoes_digitalizados: int
    cartoes_enviados: int

    kits_pendentes: int
    kits_montados: int
    kits_entregues: int

    compras_total: Decimal

    checkin_feitos: int


class LinhaInstituicao(BaseModel):
    instituicao_id: int
    instituicao: str
    criancas: int
    apadrinhados: int
    cartoes: int
    kits_entregues: int
    checkin: int


class LinhaDia(BaseModel):
    dia_evento_id: int | None
    data: date | None
    descricao: str | None
    criancas: int
    checkin: int


class Relatorio(BaseModel):
    resumo: ResumoEdicao
    por_instituicao: list[LinhaInstituicao]
    por_dia: list[LinhaDia]
