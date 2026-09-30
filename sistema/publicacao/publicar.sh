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

# Qual versao publicar.
#
#   homologacao:  ./publicar.sh              segue o main, sempre o mais novo
#   producao:     REF=v2026.1 ./publicar.sh  so o que foi marcado com tag
#
# A diferenca e o portao: homologacao recebe tudo o que entra no main, e so
# vira producao o que alguem marcou de proposito depois de ver funcionando.
REF="${REF:-}"

echo "==> Buscando a versao nova"
git fetch --all --tags --prune
if [ -n "$REF" ]; then
  echo "    publicando a referencia fixa: $REF"
  git checkout --quiet --detach "$REF"
else
  echo "    seguindo o main"
  git checkout --quiet main
  git pull --ff-only
fi
echo "    versao: $(git describe --tags --always) ($(git rev-parse --short HEAD))"

echo "==> Backend: dependencias"
./sistema/backend/.venv/bin/python -m pip install -q -r sistema/backend/requirements.txt

echo "==> Frontend: build"
(cd sistema/frontend && npm ci && npm run build)

# O nome da unidade muda por servidor; o padrao serve para producao.
SERVICO="${SERVICO:-natal-lumen-api}"

# A migracao vem AQUI, colada no restart — e nao antes do build do frontend,
# onde ficava. Entre uma coisa e outra ha um `npm ci` que leva um ou dois
# minutos, e nesse intervalo o codigo VELHO conversava com o banco NOVO: depois
# de uma migracao que renomeia coluna, era erro em toda consulta daquela tabela.
# Ninguem notava em homologacao; no dia do evento, notaria.
echo "==> Backend: migrations"
(cd sistema/backend && ./.venv/bin/alembic upgrade head)

echo "==> Reiniciando a API ($SERVICO)"
sudo systemctl restart "$SERVICO"

echo "==> Conferindo"

# Espera ATE 30s, tentando a cada segundo, em vez de dormir 3 e chutar uma vez.
# A API demora mais que 3s para ligar na porta, e o script dizia "FALHOU" em
# publicacao que tinha dado certo — em cinco de sete tentativas numa mesma
# tarde. O problema nao e so o susto: um alarme que quase sempre mente ensina a
# ignorar o alarme, e ai a falha de verdade passa batido.
espera_api() {
  local tentativas=30
  while [ $tentativas -gt 0 ]; do
    if curl -fsS http://127.0.0.1:8000/saude > /dev/null 2>&1; then
      return 0
    fi
    tentativas=$((tentativas - 1))
    sleep 1
  done
  return 1
}

# Primeiro direto no uvicorn: isola "a API subiu?" de "o nginx esta certo?".
# Antes daqui so havia a checagem por HTTPS usando ${DOMINIO}, que nunca era
# definido em lugar nenhum — caia em https://localhost, falhava sempre, e o
# script terminava com erro mesmo quando a publicacao tinha dado certo.
if ! espera_api; then
  echo "FALHOU: a API nao respondeu em 30 segundos."
  echo "  Veja: sudo journalctl -u $SERVICO -n 50"
  exit 1
fi
echo "OK: a API respondeu."

# E, se o dominio for informado, a volta inteira pelo nginx e pelo HTTPS.
#   DOMINIO=natallumen.org ./sistema/publicacao/publicar.sh
if [ -n "${DOMINIO:-}" ]; then
  # Tres tentativas: o nginx pode pegar o primeiro pedido com o upstream ainda
  # trocando de processo.
  publico_ok=""
  for _ in 1 2 3; do
    if curl -fsS "https://$DOMINIO/acesso/api/saude" > /dev/null 2>&1; then
      publico_ok="sim"
      break
    fi
    sleep 2
  done

  if [ -n "$publico_ok" ]; then
    echo "OK: o caminho publico tambem respondeu."
  else
    echo "ATENCAO: a API subiu, mas https://$DOMINIO/acesso/api/saude nao respondeu."
    echo "  Olhe o nginx: sudo nginx -t && sudo tail -n 30 /var/log/nginx/error.log"
    exit 1
  fi
else
  echo "(defina DOMINIO=seu.dominio para conferir tambem pelo HTTPS)"
fi
