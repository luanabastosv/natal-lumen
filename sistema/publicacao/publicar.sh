#!/usr/bin/env bash
# Atualiza o sistema ja publicado.
#
#   ssh servidor
#   cd /var/www/natal-lumen && ./sistema/publicacao/publicar.sh
#
# Nao cria nada do zero: para a primeira instalacao, siga o README.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$RAIZ"

echo "==> Buscando a versao nova"
git pull --ff-only

echo "==> Backend: dependencias"
./sistema/backend/.venv/bin/python -m pip install -q -r sistema/backend/requirements.txt

echo "==> Backend: migrations"
# Rodadas ANTES de reiniciar: o codigo novo costuma esperar o esquema novo.
(cd sistema/backend && ./.venv/bin/alembic upgrade head)

echo "==> Frontend: build"
(cd sistema/frontend && npm ci && npm run build)

echo "==> Reiniciando a API"
sudo systemctl restart natal-lumen-api

echo "==> Conferindo"
sleep 3
if curl -fsS https://"${DOMINIO:-localhost}"/acesso/api/saude > /dev/null; then
  echo "OK: a API respondeu."
else
  echo "ATENCAO: a API nao respondeu. Veja: sudo journalctl -u natal-lumen-api -n 50"
  exit 1
fi
