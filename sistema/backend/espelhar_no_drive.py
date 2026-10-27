#!/usr/bin/env python
"""Manda ao Drive os cartoes e as autorizacoes que ainda nao tem copia la.

Cada imagem ja vai para o Drive logo depois de subir (app/servicos/espelho.py).
Este script pega o que ficou para tras: o que falhou durante o dia (Google
fora do ar, credencial trocada) e o que subiu antes de o espelho existir.

Roda toda noite, chamado pelo `backup.sh`. Tambem pode rodar a mao:

    ./.venv/bin/python espelhar_no_drive.py
"""

import sys

from app.database import SessionLocal
from app.servicos import drive, espelho


def main() -> int:
    if not drive.configurado():
        print("Drive nao configurado neste servidor: cartoes e autorizacoes ficam so no disco.")
        return 0

    db = SessionLocal()
    try:
        foram, falharam = espelho.pendentes(db)
    finally:
        db.close()

    print(f"  {foram} imagem(ns) enviada(s) ao Drive")
    if falharam:
        print(f"  {falharam} nao foram (ver o log de atividade)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
