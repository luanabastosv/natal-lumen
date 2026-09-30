#!/usr/bin/env bash
# Liga o backup diario com envio ao Drive. Roda UMA vez, e pede a senha do sudo.
#
#   ssh teste.natallumen.com
#   sudo /var/www/natal-lumen/sistema/publicacao/instalar-backup.sh
#
# Depois disso o backup roda sozinho todo dia as 03:10, como o usuario
# natal-lumen — o unico que alcanca a chave do Drive.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Rode com sudo: sudo $0" >&2
  exit 1
fi

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Pasta dos backups"
install -d -o natal-lumen -g natal-lumen -m 750 /var/lib/natal-lumen/backups

echo "==> Unidades do systemd"
install -m 644 "$AQUI/natal-lumen-backup.service" /etc/systemd/system/
install -m 644 "$AQUI/natal-lumen-backup.timer"   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now natal-lumen-backup.timer

echo "==> Testando agora (o primeiro backup ja vai para o Drive)"
systemctl start natal-lumen-backup.service
sleep 2
journalctl -u natal-lumen-backup.service -n 20 --no-pager

echo
echo "Proxima execucao:"
systemctl list-timers natal-lumen-backup.timer --no-pager | head -3
