#!/usr/bin/env bash
# Backup do sistema Natal Lumen.
#
# Duas coisas nao dao para refazer: a base de dados e as imagens dos cartoes.
# O resto (codigo, configuracao) esta no git.
#
#   ./backup.sh                      guarda em ../backups/
#   ./backup.sh /Volumes/PenDrive    guarda onde voce mandar
#
# Restaurar:  ver as instrucoes impressas no fim.

set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESTINO="${1:-$AQUI/../backups}"
QUANDO="$(date +%Y-%m-%d_%H%M)"

# Le a DATABASE_URL do .env sem precisar de python.
if [ ! -f "$AQUI/.env" ]; then
  echo "Nao achei o .env em $AQUI" >&2
  exit 1
fi
URL="$(grep -E '^DATABASE_URL=' "$AQUI/.env" | head -1 | cut -d= -f2-)"

# postgresql+psycopg://usuario:senha@host:porta/base  ->  peças
SEM_ESQUEMA="${URL#*://}"
CREDENCIAIS="${SEM_ESQUEMA%%@*}"
RESTO="${SEM_ESQUEMA#*@}"
USUARIO="${CREDENCIAIS%%:*}"
SENHA="${CREDENCIAIS#*:}"
HOSPEDEIRO="${RESTO%%:*}"
PORTA_E_BASE="${RESTO#*:}"
PORTA="${PORTA_E_BASE%%/*}"
BASE="${PORTA_E_BASE#*/}"

mkdir -p "$DESTINO"

echo "==> Base de dados ($BASE)"
PGPASSWORD="$SENHA" pg_dump \
  -h "$HOSPEDEIRO" -p "$PORTA" -U "$USUARIO" -d "$BASE" \
  --format=custom \
  --file="$DESTINO/natal-lumen_$QUANDO.dump"

ARQUIVOS="$(grep -E '^ARQUIVOS_DIR=' "$AQUI/.env" | head -1 | cut -d= -f2-)"
ARQUIVOS="${ARQUIVOS:-../arquivos}"
case "$ARQUIVOS" in
  /*) PASTA="$ARQUIVOS" ;;
   *) PASTA="$AQUI/$ARQUIVOS" ;;
esac

if [ -d "$PASTA" ] && [ -n "$(ls -A "$PASTA" 2>/dev/null)" ]; then
  echo "==> Imagens dos cartoes"
  tar -czf "$DESTINO/arquivos_$QUANDO.tar.gz" -C "$(dirname "$PASTA")" "$(basename "$PASTA")"
else
  echo "==> Sem imagens ainda, nada a guardar"
fi

echo
echo "Guardado em $DESTINO:"
ls -lh "$DESTINO" | grep "$QUANDO" | awk '{print "   ", $NF, "("$5")"}'
echo
echo "Para restaurar a base:"
echo "   PGPASSWORD=... pg_restore -h $HOSPEDEIRO -p $PORTA -U $USUARIO -d $BASE \\"
echo "       --clean --if-exists $DESTINO/natal-lumen_$QUANDO.dump"
echo
echo "Guarde uma copia FORA deste computador — nuvem, pen drive, outro disco."
