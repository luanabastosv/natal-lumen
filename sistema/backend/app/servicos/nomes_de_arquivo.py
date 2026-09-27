"""Acha o codigo da crianca no nome do arquivo do cartao.

O monitor digitaliza a pilha de cartoes e nomeia cada arquivo com o codigo da
crianca. E o codigo, e nao o nome escrito no cartao, que identifica: codigo e
unico por edicao, nao tem acento, nao tem letra de crianca de oito anos, e o
sistema ja o conhece.

Na pratica o nome chega sujo. O scanner poe prefixo, o celular poe data, o
Windows poe "(1)" quando repete, e ninguem digita maiusculo:

    SL12.jpg
    sl12.jpeg
    IMG_20261110_SL12.jpg
    SL12 (1).png
    Digitalizado_KN1721_frente.jpg

Todos esses tem de cair na mesma crianca. Por isso a busca e por CONTEUDO, e
nao por igualdade: normaliza o nome, normaliza os codigos da edicao, e procura
um dentro do outro.
"""

import re
import unicodedata
from dataclasses import dataclass


def normalizar(texto: str) -> str:
    """Maiusculas, sem acento, so A-Z e 0-9."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]", "", sem_acento.upper())


def _sem_extensao(nome: str) -> str:
    """Tira so a ultima extensao. "SL12.frente.jpg" vira "SL12.frente"."""
    return nome.rsplit(".", 1)[0] if "." in nome else nome


@dataclass
class Acerto:
    codigo: str | None
    # Por que nao achou, ou por que achou de um jeito que merece conferencia.
    erro: str | None = None
    aviso: str | None = None


def casar(nome_arquivo: str, codigos: list[str]) -> Acerto:
    """Descobre de qual codigo este arquivo e.

    `codigos` sao os codigos reais daquela edicao — a busca nunca inventa um
    codigo que nao exista.
    """
    alvo = normalizar(_sem_extensao(nome_arquivo))
    if not alvo:
        return Acerto(None, erro="O nome do arquivo nao tem nenhuma letra ou numero.")

    # Um mapa do codigo normalizado para o original: o codigo no banco pode ter
    # sido digitado com espaco ou tracinho por alguem.
    por_normal: dict[str, list[str]] = {}
    for c in codigos:
        por_normal.setdefault(normalizar(c), []).append(c)

    # 1. O nome inteiro E o codigo. O caso limpo, e o que a instrucao pede.
    if alvo in por_normal:
        return _um_so(por_normal[alvo], alvo)

    # 2. O codigo esta em algum lugar do nome — mas so procuramos assim
    #    codigo que tenha LETRA.
    #
    #    Codigo puramente numerico e curto demais para ser procurado dentro de
    #    um nome sujo: "IMG_20261110_010.jpg" contem "010" e tambem contem
    #    "001", que pode ser outra crianca. A data do celular vira um campo
    #    minado de codigos falsos. Com sigla ("SL12", "KN1721") o acaso
    #    praticamente some.
    #
    #    Quem usa codigo so numerico ainda e atendido pela regra 1: o nome do
    #    arquivo tem de ser exatamente o codigo.
    candidatos = [n for n in por_normal if n and any(c.isalpha() for c in n)]
    contidos = sorted((n for n in candidatos if n in alvo), key=len, reverse=True)
    if not contidos:
        return Acerto(
            None,
            erro=(
                "Nenhum codigo desta edicao aparece no nome do arquivo. "
                "Renomeie o arquivo com o codigo da crianca."
            ),
        )

    vencedor = contidos[0]

    # Aqui ha DOIS casos que parecem um so, e trata-los igual manda cartao
    # para a crianca errada:
    #
    #   aninhado   "SL12" contem "SL1"      -> o mais longo ganha, e correto
    #   rival      "SL12_KN1721" tem os dois -> ambiguidade, tem de recusar
    #
    # A diferenca e se o outro codigo e pedaco do vencedor ou nao.
    rivais = [n for n in contidos if n != vencedor and n not in vencedor]
    if rivais:
        nomes = sorted(por_normal[n][0] for n in [vencedor, *rivais])
        return Acerto(
            None,
            erro=(
                f"O nome do arquivo casa com mais de um codigo ({', '.join(nomes)}). "
                "Renomeie deixando so o codigo."
            ),
        )

    return _um_so(
        por_normal[vencedor],
        vencedor,
        aviso=(
            "O codigo foi encontrado dentro de um nome maior; confira se e a "
            "crianca certa."
        ),
    )


def _um_so(originais: list[str], normal: str, aviso: str | None = None) -> Acerto:
    """Dois codigos diferentes que normalizam igual sao ambiguidade real."""
    if len(originais) > 1:
        return Acerto(
            None,
            erro=(
                f"Ha mais de uma crianca com o codigo {normal} nesta edicao "
                f"({', '.join(sorted(originais))}). Corrija os codigos antes."
            ),
        )
    return Acerto(originais[0], aviso=aviso)
