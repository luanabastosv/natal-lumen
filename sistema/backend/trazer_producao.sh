#!/usr/bin/env bash
# Traz uma copia exata do banco de producao para o seu computador.
#
#   cd sistema/backend && ./trazer_producao.sh
#
# Para que serve: sem servidor de teste, e AQUI que uma mudanca encontra os
# dados de verdade antes de publicar — a migration rodando sobre mil criancas,
# a planilha com o volume real, o padrinho com vinte apadrinhamentos.
#
# O que faz:
#   1. guarda o seu banco local atual em ../backups/local-antes-de-trazer_*.dump;
#   2. baixa a producao (pg_dump pelo ssh) para ../backups/producao_*.dump;
#   3. troca o banco local por ela.
#
# Copia exata: nomes, contatos e senhas de verdade — entra-se aqui com a mesma
# senha da producao. O que impede um teste daqui de mandar mensagem ou subir
# arquivo de verdade e o .env local nao ter credencial de WhatsApp nem de
# Drive; mantenha assim.
#
# Os arquivos (fotos de cartao, comprovantes) NAO vem: so o banco. As telas
# mostram "nao encontrado" para as imagens, que e o esperado.

set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$AQUI"
SERVIDOR="${SERVIDOR:-acesso.natallumen.com}"
QUANDO="$(date +%Y-%m-%d_%H%M)"
PASTA="$AQUI/../backups"
mkdir -p "$PASTA"

if grep -qE '^AMBIENTE=(producao|homologacao)' .env; then
  echo "Este .env nao e de desenvolvimento. Rode so no seu computador." >&2
  exit 1
fi

# As pecas da DATABASE_URL local, pelo mesmo caminho que o sistema le.
pecas() {
  ./.venv/bin/python - <<'PY'
import shlex
from sqlalchemy.engine import make_url
from app.config import config
u = make_url(config.database_url)
for k, v in {"PGHOST": u.host or "localhost", "PGPORT": u.port or 5432,
             "PGUSER": u.username, "PGPASSWORD": u.password or "",
             "PGDATABASE": u.database}.items():
    print(f"export {k}={shlex.quote(str(v))}")
PY
}

echo "==> 1. Guardando o seu banco local"
(eval "$(pecas)" && pg_dump --format=custom --file="$PASTA/local-antes-de-trazer_$QUANDO.dump")
echo "    $PASTA/local-antes-de-trazer_$QUANDO.dump"

echo "==> 2. Baixando a producao de $SERVIDOR"
# shellcheck disable=SC2029
ssh "$SERVIDOR" 'cd /var/www/natal-lumen/sistema/backend && eval "$(./.venv/bin/python - <<"PY"
import shlex
from sqlalchemy.engine import make_url
from app.config import config
u = make_url(config.database_url)
for k, v in {"PGHOST": u.host or "localhost", "PGPORT": u.port or 5432,
             "PGUSER": u.username, "PGPASSWORD": u.password or "",
             "PGDATABASE": u.database}.items():
    print(f"export {k}={shlex.quote(str(v))}")
PY
)" && pg_dump --format=custom' > "$PASTA/producao_$QUANDO.dump"
echo "    $PASTA/producao_$QUANDO.dump ($(du -h "$PASTA/producao_$QUANDO.dump" | cut -f1))"

echo "==> 3. Trocando o banco local pela copia"
(eval "$(pecas)" && pg_restore --clean --if-exists --no-owner -d "$PGDATABASE" "$PASTA/producao_$QUANDO.dump")
./.venv/bin/alembic upgrade head

echo
echo "Pronto. Entre com o mesmo email e senha da producao."
echo "Para voltar ao banco local de antes:"
echo "   pg_restore --clean --if-exists --no-owner -d <banco> $PASTA/local-antes-de-trazer_$QUANDO.dump"
