#!/usr/bin/env python
"""Manda os arquivos de backup para o Drive Compartilhado do evento.

Chamado pelo `backup.sh` logo depois de gerar o dump. Existe separado porque o
backup tem de funcionar mesmo sem Drive: se o envio falhar, o arquivo local
continua la, e o script diz o que houve em vez de fingir que guardou.

Vai para uma SUBPASTA propria, e nao junto dos comprovantes: um comprovante e o
recibo de uma pessoa; este dump tem o nome e a idade de todas as criancas, o
contato dos padrinhos e os hashes de senha. Em pasta separada da para restringir
quem ve uma coisa sem restringir a outra.

    ./.venv/bin/python guardar_backup.py arquivo1 arquivo2 ...
"""

import mimetypes
import sys
from pathlib import Path

from app.servicos import drive

PASTA = "Backups do sistema"


def main(caminhos: list[str]) -> int:
    if not drive.configurado():
        print("Drive nao configurado neste servidor: o backup ficou so no disco.")
        return 0

    try:
        pasta_id = drive.garantir_subpasta(PASTA)
    except drive.ErroDrive as erro:
        print(f"FALHOU ao abrir a pasta no Drive: {erro.mensagem}", file=sys.stderr)
        return 1

    problemas = 0
    for caminho in caminhos:
        arquivo = Path(caminho)
        if not arquivo.is_file():
            print(f"  nao achei {arquivo}", file=sys.stderr)
            problemas += 1
            continue

        tipo = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
        try:
            enviado = drive.enviar(arquivo.read_bytes(), arquivo.name, tipo, pasta_id)
            print(f"  {arquivo.name} -> Drive ({enviado.link or enviado.id})")
        except drive.ErroDrive as erro:
            print(f"  FALHOU {arquivo.name}: {erro.mensagem}", file=sys.stderr)
            problemas += 1

    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
