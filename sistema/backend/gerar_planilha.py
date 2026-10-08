#!/usr/bin/env python
"""Gera a planilha consolidada de cada edicao ativa e manda para o Drive.

Roda toda noite, chamado pelo `backup.sh` logo depois do backup. Existe para o
dia em que o sistema cair: a equipe continua acompanhando pela planilha da
noite anterior. O que vai nela esta em app/servicos/planilha.py.

Cada noite e um arquivo NOVO ("Fortaleza 2026 — 2026-10-08"): os anteriores
ficam, e da para ver como estava num dia que deu problema.

Sobe para uma subpasta propria do Drive, separada dos comprovantes e dos
backups: tem o nome e a idade de todas as criancas e o contato dos padrinhos,
e o acesso a ela deve ser so da coordenacao.

    ./.venv/bin/python gerar_planilha.py              gera e manda ao Drive
    ./.venv/bin/python gerar_planilha.py /uma/pasta   tambem guarda o .xlsx la
"""

import sys
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Edicao
from app.servicos import drive, planilha

PASTA = "Planilhas diárias"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PLANILHA_GOOGLE = "application/vnd.google-apps.spreadsheet"


def main(argumentos: list[str]) -> int:
    destino = Path(argumentos[0]) if argumentos else None
    db = SessionLocal()
    problemas = 0

    try:
        # Edicao de teste (ZZ) nunca vai para o Drive da equipe.
        edicoes = [
            e for e in db.scalars(select(Edicao).where(Edicao.ativa.is_(True))).all()
            if not e.nome.upper().startswith("ZZ")
        ]

        pasta_id = None
        if drive.configurado():
            try:
                pasta_id = drive.garantir_subpasta(PASTA)
            except drive.ErroDrive as erro:
                print(f"FALHOU ao abrir a pasta no Drive: {erro.mensagem}", file=sys.stderr)
                problemas += 1
        else:
            print("Drive nao configurado neste servidor: a planilha nao sobe.")

        for edicao in edicoes:
            nome = planilha.nome_do_arquivo(edicao)
            conteudo = planilha.montar(db, edicao)

            if destino:
                destino.mkdir(parents=True, exist_ok=True)
                (destino / f"{nome}.xlsx").write_bytes(conteudo)
                print(f"  {nome}.xlsx -> {destino}")

            if pasta_id:
                try:
                    enviado = drive.enviar(
                        conteudo, nome, XLSX, pasta_id, converter_para=PLANILHA_GOOGLE
                    )
                    print(f"  {nome} -> Drive ({enviado.link or enviado.id})")
                except drive.ErroDrive as erro:
                    print(f"  FALHOU {nome}: {erro.mensagem}", file=sys.stderr)
                    problemas += 1
    finally:
        db.close()

    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
