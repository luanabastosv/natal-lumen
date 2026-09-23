"""Leitura segura de arquivos enviados.

A aplicacao precisa do arquivo inteiro na memoria (a foto vai para o OpenCV, a
planilha para o pandas). Por isso o teto tem de ser conferido AQUI, e nao so no
nginx: em desenvolvimento nao ha nginx nenhum, e em producao uma configuracao
errada deixaria passar.
"""

from fastapi import HTTPException, UploadFile, status

from app.config import config

# Lido aos poucos: conferir o tamanho depois de ja ter carregado tudo na
# memoria nao protege de nada.
PEDACO = 1024 * 1024


async def ler_limitado(arquivo: UploadFile, limite: int | None = None) -> bytes:
    """Le o arquivo ate o limite. Passou do teto, recusa na hora."""
    teto = limite if limite is not None else config.max_upload_bytes

    pedacos: list[bytes] = []
    total = 0

    while pedaco := await arquivo.read(PEDACO):
        total += len(pedaco)
        if total > teto:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"Arquivo muito grande. O limite e {config.max_upload_mb} MB.",
            )
        pedacos.append(pedaco)

    if total == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arquivo vazio.")

    return b"".join(pedacos)
