"""Limpeza de nomes de arquivo."""

import re
import unicodedata
from pathlib import Path


def limpar_texto(texto: str) -> str:
    """Devolve o texto em maiusculas, sem acentos, com espacos trocados por "_".

    Mantem apenas A-Z, 0-9 e "_":
        "Maria Joao d'Avila" -> "MARIA_JOAO_DAVILA"
    """
    # NFKD separa a letra do acento; o filtro seguinte descarta os acentos.
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))

    limpo = sem_acento.upper()
    limpo = re.sub(r"[\s\-]+", "_", limpo.strip())
    limpo = re.sub(r"[^A-Z0-9_]", "", limpo)
    limpo = re.sub(r"_{2,}", "_", limpo).strip("_")

    return limpo


def montar_nome_arquivo(instituicao: str, nome: str, extensao: str = ".jpg") -> str:
    """Monta o nome no formato INSTITUICAO_NOME.jpg."""
    partes = [p for p in (limpar_texto(instituicao), limpar_texto(nome)) if p]
    base = "_".join(partes) or "CARTAO"
    return f"{base}{extensao}"


def caminho_disponivel(pasta: Path, nome_arquivo: str) -> Path:
    """Devolve um caminho que ainda nao existe, acrescentando _2, _3 ... se preciso."""
    destino = pasta / nome_arquivo
    if not destino.exists():
        return destino

    base = destino.stem
    extensao = destino.suffix
    contador = 2
    while True:
        candidato = pasta / f"{base}_{contador}{extensao}"
        if not candidato.exists():
            return candidato
        contador += 1
