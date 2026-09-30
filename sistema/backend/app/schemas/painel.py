"""Numeros do painel.

O painel responde a duas perguntas, e so a elas: quanto do apadrinhamento de
cesta e de festa ja esta feito, e quem ainda tem trabalho pela frente —
instituicao por instituicao, comissario por comissario, dia por dia. Numero que
nao ajuda a decidir o que fazer hoje mora na tela do assunto dele, nao aqui.

As mesmas perguntas mudam de tamanho conforme quem olha: para a coordenacao
sao as da edicao inteira; para o comissario, so as criancas na mao dele.

Os percentuais nao saem daqui: a API manda os dois inteiros (feito e total) e
a tela divide. Mandar a conta pronta ao lado das parcelas so abriria caminho
para as duas discordarem num arredondamento.
"""

from datetime import date

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

    # Apadrinhamentos registrados que ainda esperam o pagamento. Nao entram em
    # NENHUMA conta acima — promessa nao e apadrinhamento — e existem aqui para
    # a tela poder explicar por que os numeros sao menores do que o time lembra
    # de ter captado, e para a coordenacao saber quanto ha a cobrar.
    prometidos: int = 0


class LinhaInstituicao(BaseModel):
    instituicao_id: int
    instituicao: str
    # O prefixo do codigo das criancas (ES, MA, KN...). A equipe conversa por
    # ele — "faltam tres da KN" — e e assim que a lista antiga era lida.
    sigla: str | None
    criancas: int
    cesta: int
    festa: int
    # Completa e a crianca que tem os dois padrinhos; `faltam` e o resto. Sao o
    # "APADRINHADO" e o "FALTA APADRINHAR" da planilha, que contavam a crianca
    # inteira — nao cesta e festa em separado.
    completas: int
    faltam: int
    # Em que dia esta instituicao vai, e quantos onibus a buscam. Vazios
    # enquanto a coordenacao nao marcou o dia.
    dia_evento_id: int | None
    dia_evento: date | None
    dia_evento_descricao: str | None
    onibus: int


class FaixaIdade(BaseModel):
    """Quantas criancas de uma idade, separadas por sexo.

    A linha existe mesmo zerada dentro da faixa que a edicao atende: um zero em
    "7 anos" e informacao — diz que aquela idade nao veio —, e sem ele a tabela
    pularia de 6 para 8 e ninguem notaria a falta.
    """

    idade: int
    masculino: int
    feminino: int


class LinhaDia(BaseModel):
    """O total de um dia do evento: quanto sai de onibus, e quanto falta.

    `dia_evento_id` nulo e a linha das instituicoes ainda sem dia marcado. Elas
    contam no total da edicao e precisam aparecer: uma escola sem dia e uma
    escola que ninguem vai buscar.
    """

    dia_evento_id: int | None
    data: date | None
    descricao: str | None
    instituicoes: int
    criancas: int
    onibus: int
    completas: int
    faltam: int


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
    por_idade: list[FaixaIdade]
    # Vazia enquanto a edicao nao tem dias cadastrados — uma so linha de "sem
    # dia" nao seria uma quebra, seria o total repetido.
    por_dia: list[LinhaDia]
