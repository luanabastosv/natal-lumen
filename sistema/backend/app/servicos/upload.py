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


def ler_limitado(arquivo: UploadFile, limite: int | None = None) -> bytes:
    """Le o arquivo ate o limite. Passou do teto, recusa na hora.

    Sincrono de proposito, e por isso as rotas de upload sao `def`, nao
    `async def`. Numa rota async, tudo o que nao e `await` — a consulta ao
    banco, o Pillow, o envio ao Drive — roda dentro do laco de eventos e PARA o
    servidor inteiro enquanto dura: com um worker so, um comprovante subindo
    para o Drive (ate 60s) congelava o sistema para todo mundo. Rota `def` vai
    para uma thread, e os outros pedidos seguem sendo atendidos.

    `arquivo.file` ja esta inteiro no disco (ou na memoria) quando a rota
    comeca: o Starlette recebe o corpo antes. Ler daqui nao espera a rede.
    """
    teto = limite if limite is not None else config.max_upload_bytes

    pedacos: list[bytes] = []
    total = 0

    while pedaco := arquivo.file.read(PEDACO):
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
