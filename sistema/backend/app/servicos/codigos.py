"""Geracao dos codigos das criancas.

As instituicoes mandam a lista sem codigo — nome, idade, sexo e instituicao. O
codigo e montado aqui: a sigla da instituicao mais um numero sequencial.

A ordem do numero nao e a da planilha. E sempre:

    1. meninas primeiro, depois meninos
    2. dentro de cada grupo, da menor para a maior idade
    3. dentro de cada idade, ordem alfabetica

Assim o codigo ES04 significa a mesma coisa em qualquer lista impressa, e quem
procura uma crianca no dia do evento sabe onde olhar.
"""

import re
import unicodedata
from dataclasses import dataclass

TAMANHO_SIGLA = 2
DIGITOS = 2


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in normalizado if not unicodedata.combining(c))


# Palavras que nao ajudam a distinguir uma instituicao da outra.
IGNORADAS = {"de", "da", "do", "das", "dos", "e", "a", "o", "as", "os"}


def sugerir_sigla(nome: str, usadas: set[str] | None = None) -> str:
    """Sigla a partir do nome da instituicao.

        "Escolinha Sol"            -> ES
        "Creche Lar da Crianca"    -> CL
        "Instituto Semear"         -> IS

    Se a sigla ja estiver em uso na cidade, acrescenta letras da primeira
    palavra ate ficar unica — e, no limite, um numero.
    """
    usadas = usadas or set()

    palavras = [
        p for p in re.split(r"[\s\-]+", _sem_acento(nome).upper())
        if p and p.lower() not in IGNORADAS
    ]
    if not palavras:
        palavras = ["X"]

    base = "".join(p[0] for p in palavras)[:TAMANHO_SIGLA]
    if len(base) < TAMANHO_SIGLA:
        base = (palavras[0] + "XX")[:TAMANHO_SIGLA]

    if base not in usadas:
        return base

    # Colisao: puxa mais letras da primeira palavra.
    primeira = palavras[0]
    for tamanho in range(TAMANHO_SIGLA + 1, min(len(primeira), 6) + 1):
        tentativa = primeira[:tamanho]
        if tentativa not in usadas:
            return tentativa

    contador = 2
    while f"{base}{contador}" in usadas:
        contador += 1
    return f"{base}{contador}"


@dataclass
class ParaOrdenar:
    """O minimo que a ordenacao precisa saber sobre uma crianca."""

    nome: str
    idade: int | None
    sexo: str | None


def chave_de_ordem(crianca: ParaOrdenar) -> tuple:
    """Meninas primeiro, depois idade crescente, depois ordem alfabetica.

    sexo != "F" vira False para as meninas, e False vem antes de True.
    Idade ausente vai para o fim do grupo, nao para o comeco — senao uma
    planilha incompleta bagunçaria a numeracao das demais.
    """
    return (
        crianca.sexo != "F",
        crianca.idade if crianca.idade is not None else 999,
        _sem_acento(crianca.nome).upper(),
    )


def ordenar(criancas: list) -> list:
    """Ordena pela regra do projeto. Aceita qualquer objeto com nome/idade/sexo."""
    return sorted(criancas, key=chave_de_ordem)


def montar_codigo(sigla: str, numero: int) -> str:
    return f"{sigla}{numero:0{DIGITOS}d}"


def gerar_codigos(criancas: list, sigla: str, comecar_em: int = 0) -> list[tuple]:
    """Devolve [(crianca, codigo)] na ordem certa.

    comecar_em serve para uma segunda importacao continuar de onde a primeira
    parou, em vez de repetir codigos ja usados.
    """
    return [
        (crianca, montar_codigo(sigla, comecar_em + i))
        for i, crianca in enumerate(ordenar(criancas))
    ]


def proximo_numero(codigos_existentes: list[str], sigla: str) -> int:
    """Primeiro numero livre para esta sigla."""
    maior = -1
    padrao = re.compile(rf"^{re.escape(sigla)}(\d+)$", re.IGNORECASE)

    for codigo in codigos_existentes:
        achado = padrao.match(codigo.strip())
        if achado:
            maior = max(maior, int(achado.group(1)))

    return maior + 1
