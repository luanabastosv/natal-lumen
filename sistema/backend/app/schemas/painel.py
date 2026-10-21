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

from datetime import date, datetime

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
    # De quantas criancas a festa e de quem olha. Para a coordenacao e o total
    # de criancas; para o comissario, as que a coordenacao passou para ele —
    # que nao sao as da lista de cesta dele, e podem ser de outra instituicao.
    festa_criancas: int = 0

    # Crianca completa: tem os dois. O que falta dela — `criancas - completas` —
    # e o tanto de trabalho que ainda sobra de quem esta olhando.
    completas: int

    # Apadrinhamentos registrados que ainda esperam o pagamento. Nao entram em
    # NENHUMA conta acima — promessa nao e apadrinhamento — e existem aqui para
    # a tela poder explicar por que os numeros sao menores do que o time lembra
    # de ter captado, e para a coordenacao saber quanto ha a cobrar.
    prometidos: int = 0

    # A coordenacao geral ja comecou a campanha da festa. Antes disso o painel
    # avisa que ela ainda nao foi liberada, e o que falta e so a cesta.
    festa_liberada: bool = False


class LinhaInstituicao(BaseModel):
    instituicao_id: int
    instituicao: str
    # O prefixo do codigo das criancas (ES, MA, KN...). A equipe conversa por
    # ele — "faltam tres da KN" — e e assim que a lista antiga era lida.
    sigla: str | None
    criancas: int
    cesta: int
    festa: int
    # De quantas a festa e de quem olha. Nulo = as mesmas `criancas` (a
    # coordenacao). Para o comissario sao as que a coordenacao passou para ele
    # nesta instituicao, que nao precisam ser as da lista de cesta dele.
    festa_criancas: int | None = None
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
    # Com a campanha da festa ligada, a festa e outra lista: de quantas
    # criancas a festa esta com ele (na linha "Sem comissario", com a
    # coordenacao), e `festa` passa a contar as feitas dessa lista. Nulo =
    # campanha desligada.
    festa_criancas: int | None = None
    # Crianca completa: tem cesta E festa. `faltam` sao as que ainda nao tem
    # os dois, que e o que sobra de trabalho para o comissario. Com a festa
    # ligada, e o que falta das duas listas.
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
    # O painel da estrutura: so valem as quebras por dia, por idade e por
    # instituicao. O resumo vem para dar nome a edicao, mas a tela nao o mostra
    # como numero, e as promessas e a lista de comissarios vem zeradas.
    so_logistica: bool = False
    por_instituicao: list[LinhaInstituicao]
    # Vazia para o comissario: a lista existe para a coordenacao distribuir e
    # cobrar, e para ele so traria os colegas zerados pelo proprio filtro.
    por_comissario: list[LinhaComissario]
    por_idade: list[FaixaIdade]
    # Vazia enquanto a edicao nao tem dias cadastrados — uma so linha de "sem
    # dia" nao seria uma quebra, seria o total repetido.
    por_dia: list[LinhaDia]


# ------------------------------------------------------------------ atividade
# A janela "Ver atividade" do painel da coordenacao: quem da equipe esta
# trabalhando, e o que cada um fez. Ver servicos/atividade.py.


class PessoaAtividade(BaseModel):
    usuario_id: int
    nome: str
    perfil: str
    # Nunca definiu a senha: o convite foi mandado e nao foi aceito.
    sem_senha: bool
    ultimo_acesso: datetime | None
    ultima_acao: str | None
    ultima_acao_em: datetime | None
    # Acoes de trabalho (sem entrar, sair e buscar), no dia de hoje em
    # Fortaleza e nos ultimos 7 dias.
    hoje: int
    semana: int


class ItemAtividade(BaseModel):
    id: int
    quando: datetime
    texto: str


class LinhaDoTempo(BaseModel):
    usuario_id: int
    nome: str
    itens: list[ItemAtividade]
    # Ha mais antigas: a tela pede a proxima pagina com `antes` = o ultimo id.
    mais: bool
