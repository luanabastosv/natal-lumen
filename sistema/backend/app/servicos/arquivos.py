"""Nomes e caminhos dos arquivos guardados em ARQUIVOS_DIR.

Nada aqui e servido publicamente: os arquivos vivem fora das pastas do
frontend e so saem por rota autenticada que confere permissao e edicao.
"""

import re
import unicodedata
from pathlib import Path

from app.config import config


def limpar_texto(texto: str) -> str:
    """Maiusculas, sem acento, espacos viram "_", so A-Z 0-9 e "_"."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))

    limpo = re.sub(r"[\s\-]+", "_", sem_acento.upper().strip())
    limpo = re.sub(r"[^A-Z0-9_]", "", limpo)
    return re.sub(r"_{2,}", "_", limpo).strip("_")


def nome_do_cartao(instituicao: str, nome_crianca: str, tipo: str) -> str:
    """{INSTITUICAO}_{NOME_DA_CRIANCA}_{TIPO}.jpg"""
    partes = [limpar_texto(p) for p in (instituicao, nome_crianca, tipo)]
    base = "_".join(p for p in partes if p) or "CARTAO"
    return f"{base}.jpg"


def pasta_dos_cartoes(cidade: str, ano: int) -> Path:
    """{ARQUIVOS_DIR}/cartoes/{cidade}/{ano}/"""
    return config.caminho_arquivos / "cartoes" / limpar_texto(cidade) / str(ano)


def caminho_disponivel(pasta: Path, nome_arquivo: str) -> Path:
    """Caminho que ainda nao existe, acrescentando _2, _3 ... se preciso."""
    destino = pasta / nome_arquivo
    if not destino.exists():
        return destino

    base, extensao = destino.stem, destino.suffix
    contador = 2
    while True:
        candidato = pasta / f"{base}_{contador}{extensao}"
        if not candidato.exists():
            return candidato
        contador += 1


def dentro_da_pasta(caminho_relativo: str) -> Path:
    """Resolve um caminho relativo e garante que ele nao escapa de ARQUIVOS_DIR.

    Sem isto, um caminho como "../../etc/passwd" gravado na base viraria leitura
    de arquivo do servidor.
    """
    raiz = config.caminho_arquivos.resolve()
    destino = (raiz / caminho_relativo).resolve()

    if not destino.is_relative_to(raiz):
        raise ValueError("Caminho fora da pasta de arquivos.")

    return destino
