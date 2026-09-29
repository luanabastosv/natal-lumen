"""Como um nome de pessoa se escreve, venha ele de onde vier.

As listas das instituicoes chegam em CAIXA ALTA — e o padrao da secretaria que
digitou — e o cadastro na mao chega como a pessoa teclou naquele minuto. Sem um
lugar so que decida a grafia, a mesma tela mostra "MARIA DAS GRACAS" ao lado de
"joao pedro", e a lista fica ilegivel.

Entao a grafia se decide na ENTRADA, e nao em cada tela: assim o cartao de
agradecimento, a planilha exportada, a mensagem do WhatsApp e a lista falam do
mesmo jeito sem nenhuma delas precisar lembrar disso.

A caixa e refeita sempre, nunca so quando o nome parece gritado. Consertar so o
CAPS deixaria "joao pedro" como estava, e "sempre capitalizado" e o que se
espera de uma lista de nomes.
"""

import re

# Ligadores de nome portugues, que vao em minuscula no meio do nome ("Maria das
# Gracas", nunca "Maria Das Gracas"). Os estrangeiros entram porque sobrenome
# de familia imigrante aparece nas listas: "van Gogh", "di Pietro".
LIGADORES = frozenset({
    "de", "da", "do", "das", "dos", "e",
    "di", "du", "del", "della", "dalla", "la", "le",
    "van", "von", "der", "den", "y",
})

# Um bloco de letras dentro da palavra. Separar assim, em vez de usar title(),
# e o que faz "ana-maria" virar "Ana-Maria" e "d'avila" virar "D'Avila": os dois
# lados do hifen e do apostrofo sao nomes, e cada um comeca com maiuscula.
LETRAS = re.compile(r"[^\W\d_]+")


def _palavra(palavra: str) -> str:
    return LETRAS.sub(lambda m: m.group(0).capitalize(), palavra.lower())


def nome_proprio(nome: str | None) -> str:
    """"MARIA DAS GRACAS  SILVA" -> "Maria das Gracas Silva".

    Tambem junta os espacos repetidos e tira os das pontas — era o que os
    pontos de gravacao ja faziam com `" ".join(nome.split())`, e continua
    acontecendo aqui para que trocar um pelo outro nao perca nada.
    """
    palavras = (nome or "").split()
    if not palavras:
        return ""

    # A primeira palavra e sempre maiuscula, mesmo sendo um ligador: existe
    # quem se chame so "Da Silva" na lista, e "da Silva" pareceria erro.
    return " ".join(
        palavra.lower() if i and palavra.lower() in LIGADORES else palavra
        for i, palavra in enumerate(_palavra(p) for p in palavras)
    )
