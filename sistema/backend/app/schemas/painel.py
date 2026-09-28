"""Numeros do painel.

O painel responde a duas perguntas, e so a elas: quanto do apadrinhamento de
cesta e de festa ja esta feito, e quem ainda tem trabalho pela frente —
instituicao por instituicao, comissario por comissario. Numero que nao ajuda a
decidir o que fazer hoje mora na tela do assunto dele, nao aqui.
"""

from pydantic import BaseModel


class ResumoEdicao(BaseModel):
    edicao_id: int
    edicao: str
    cidade: str
    ano: int

    criancas: int
    instituicoes: int

    # Cada crianca precisa de um padrinho de cesta e um de festa. Por isso os
    # dois se comparam sempre ao total de criancas, e nunca entre si.
    cesta_feitos: int
    festa_feitos: int


class LinhaInstituicao(BaseModel):
    instituicao_id: int
    instituicao: str
    criancas: int
    cesta: int
    festa: int


class LinhaComissario(BaseModel):
    """Um comissario e o tanto que falta no time dele.

    `comissario_id` nulo e a linha das criancas que ainda nao tem responsavel:
    elas existem e contam, mas nao estao na mao de ninguem — e essa e
    exatamente a informacao que a coordenacao precisa ver.
    """

    comissario_id: int | None
    comissario: str
    grupo: str | None
    criancas: int
    cesta: int
    festa: int
    # Crianca completa: tem cesta E festa. `faltam` sao as que ainda nao tem
    # os dois, que e o que sobra de trabalho para o comissario.
    completas: int
    faltam: int


class Relatorio(BaseModel):
    resumo: ResumoEdicao
    por_instituicao: list[LinhaInstituicao]
    por_comissario: list[LinhaComissario]
