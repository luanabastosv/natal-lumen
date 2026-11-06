"""A intercessao da equipe que reza pelas criancas."""

from datetime import datetime

from pydantic import BaseModel


class MarcaIntercessao(BaseModel):
    """Uma vivencia marcada numa crianca: qual, por quem e quando."""

    tipo: str
    usuario_id: int | None
    # Nulo quando a pessoa saiu do sistema: a marcacao fica, sem nome.
    nome: str | None
    em: datetime


class PainelIntercessao(BaseModel):
    """O quantitativo da planilha antiga de intercessao.

    Missas, adoracoes e jejuns sao as marcacoes divididas por 5, e os tercos os
    misterios divididos por 15: e a regra da planilha (cinco criancas por
    vivencia, tres por misterio, cinco misterios por terco). Por isso podem ser
    quebrados, como 41,2.
    """

    edicao: str
    criancas: int
    receberam: int
    faltam: int
    marcacoes_missa: int
    marcacoes_adoracao: int
    marcacoes_terco: int
    marcacoes_jejum: int
    missas: float
    adoracoes: float
    tercos: float
    jejuns: float
    ave_marias: int
