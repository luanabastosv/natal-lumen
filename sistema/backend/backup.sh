#!/usr/bin/env bash
# Backup do sistema Natal Lumen.
#
# Duas coisas nao dao para refazer: a base de dados e a pasta de arquivos
# (imagens dos cartoes e comprovantes de pagamento).
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
  echo "==> Cartoes e comprovantes"
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

# ---------------------------------------------------------------- fora daqui
# Backup que mora no mesmo disco do banco nao e backup: o disco que morre leva
# os dois. Por isso o envio ao Drive faz parte do script, e nao e um passo
# opcional que alguem lembra de fazer.
#
# Falha aqui NAO derruba o backup: o arquivo local ja existe, e perder o envio e
# muito melhor que perder a copia. Por isso o `|| true` — com `set -e` ligado, um
# erro do Google abortaria o script antes das instrucoes de restauracao.
if [ -x "$AQUI/.venv/bin/python" ] && [ -f "$AQUI/guardar_backup.py" ]; then
  echo
  echo "==> Enviando para o Drive"
  (cd "$AQUI" && ./.venv/bin/python guardar_backup.py \
      "$DESTINO/natal-lumen_$QUANDO.dump" \
      "$DESTINO/arquivos_$QUANDO.tar.gz") || echo "    (o envio falhou; a copia local esta feita)"
fi

# ------------------------------------------------------------------- limpeza
# Sem isto o disco enche sozinho: sao ~4 MB por dia, e ninguem visita essa
# pasta ate o dia em que precisa dela. Guarda os 14 ultimos de cada tipo — o
# suficiente para perceber um estrago que passou despercebido por uma semana.
GUARDAR="${GUARDAR:-14}"
for TIPO in "natal-lumen_*.dump" "arquivos_*.tar.gz"; do
  # shellcheck disable=SC2086
  ls -1t $DESTINO/$TIPO 2>/dev/null | tail -n +$((GUARDAR + 1)) | while read -r VELHO; do
    rm -f "$VELHO" && echo "    removido antigo: $(basename "$VELHO")"
  done
done

echo
echo "Guarde uma copia FORA deste computador — nuvem, pen drive, outro disco."
