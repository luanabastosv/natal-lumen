"""Numeros do painel.

O painel responde a duas perguntas, e so a elas: quanto do apadrinhamento de
cesta e de festa ja esta feito, e quem ainda tem trabalho pela frente —
instituicao por instituicao, comissario por comissario. Numero que nao ajuda a
decidir o que fazer hoje mora na tela do assunto dele, nao aqui.

As mesmas perguntas mudam de tamanho conforme quem olha: para a coordenacao
sao as da edicao inteira; para o comissario, so as criancas na mao dele.
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

    # Crianca completa: tem os dois. O que falta dela — `criancas - completas` —
    # e o tanto de trabalho que ainda sobra de quem esta olhando.
    completas: int


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
    """Os numeros de quem pediu o relatorio.

    `so_minhas_criancas` diz de que tamanho sao: com ele ligado, tudo aqui fala
    das criancas atribuidas a quem olha, e nao da edicao. A tela precisa saber
    disso para dizer "voce ainda tem 16 criancas" em vez de dar um panorama.
    """

    resumo: ResumoEdicao
    so_minhas_criancas: bool = False
    por_instituicao: list[LinhaInstituicao]
    # Vazia para o comissario: a lista existe para a coordenacao distribuir e
    # cobrar, e para ele so traria os colegas zerados pelo proprio filtro.
    por_comissario: list[LinhaComissario]
