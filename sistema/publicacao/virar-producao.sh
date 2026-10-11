#!/usr/bin/env bash
# Transforma o servidor que era de teste no servidor de producao. Roda UMA vez,
# com sudo, no servidor:
#
#   ssh teste.natallumen.com
#   sudo /var/www/natal-lumen/sistema/publicacao/virar-producao.sh
#
# Antes de rodar: no Cloudflare, um registro A `acesso` apontando para o IP
# deste servidor, em "DNS only" (nuvem cinza). O script confere isso e para se
# ainda nao estiver valendo.
#
# O que faz, em ordem — cada passo confere se ja foi feito, entao rodar de novo
# depois de uma falha continua de onde parou:
#
#   1. backup completo agora, antes de tudo, e depois apaga (perguntando) o
#      que foi lancado testando: padrinhos, pagamentos, cartoes, compras, kits;
#   2. nginx: acesso.natallumen.com passa a ser o nome do sistema, e os
#      limites por IP sobem para aguentar uma sala cheia no mesmo Wi-Fi;
#   3. certificado HTTPS cobrindo os dois nomes;
#   4. teste.natallumen.com redireciona para acesso.natallumen.com;
#   5. AMBIENTE=producao, 2 workers e, com PASTA_DRIVE=<id>, a pasta do
#      Drive de producao no lugar da de teste;
#   6. copia do banco de hora em hora;
#   7. confere tudo de fora.
#
# Ver sistema/docs/AMBIENTES.md.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Rode com sudo: sudo $0" >&2
  exit 1
fi

NOVO=acesso.natallumen.com
ANTIGO=teste.natallumen.com
NGINX=/etc/nginx/sites-available/natal-lumen
ENV=/var/www/natal-lumen/sistema/backend/.env
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> 0. O DNS de $NOVO ja aponta para ca?"
MEU_IP="$(hostname -I | awk '{print $1}')"
DNS_IP="$(getent ahostsv4 "$NOVO" | awk 'NR==1 {print $1}' || true)"
if [ -z "$DNS_IP" ] || ! hostname -I | tr ' ' '\n' | grep -qx "$DNS_IP"; then
  echo "    Ainda nao: $NOVO -> '${DNS_IP:-nada}', este servidor e $MEU_IP."
  echo "    Crie no Cloudflare o registro A 'acesso' -> $MEU_IP (DNS only) e"
  echo "    rode de novo daqui a alguns minutos."
  exit 1
fi
echo "    ok ($DNS_IP)"

echo "==> 1. Backup completo antes de mexer"
systemctl start natal-lumen-backup.service
journalctl -u natal-lumen-backup.service -n 6 --no-pager | sed 's/^/    /'

echo "==> 1b. Apagar o que foi lancado testando"
# Padrinhos, pagamentos, cartoes, compras e kits da edicao Fortaleza 2026. O
# cadastro (criancas, instituicoes, usuarios) fica. Roda como natal-lumen, o
# dono das imagens e comprovantes no disco. Mostra a contagem e pergunta.
cd /var/www/natal-lumen/sistema/backend
sudo -u natal-lumen ./.venv/bin/python -m app.seeds.limpar_operacao --edicao 1 | sed 's/^/    /'
read -r -p "    Apagar isso? Digite APAGAR para apagar, ou Enter para pular: " RESPOSTA
if [ "$RESPOSTA" = "APAGAR" ]; then
  sudo -u natal-lumen ./.venv/bin/python -m app.seeds.limpar_operacao --edicao 1 --sim "Fortaleza 2026" | sed 's/^/    /'
else
  echo "    pulado"
fi
cd - > /dev/null

echo "==> 2. nginx: nome novo e limites por IP"
[ -e "$NGINX.antes-da-producao" ] || cp "$NGINX" "$NGINX.antes-da-producao"
sed -i \
  -e "s/server_name $ANTIGO;/server_name $NOVO $ANTIGO;/" \
  -e 's/zone=login:10m rate=10r\/m/zone=login:10m rate=30r\/m/' \
  -e 's/zone=api:10m   rate=120r\/m/zone=api:10m   rate=600r\/m/' \
  -e 's/zone=login burst=5 /zone=login burst=20 /' \
  -e 's/zone=api burst=40 /zone=api burst=200 /' \
  "$NGINX"
nginx -t
systemctl reload nginx

echo "==> 3. Certificado HTTPS para os dois nomes"
# Mesmo certificado, agora com os dois nomes. O nome da pasta continua sendo
# o antigo (/etc/letsencrypt/live/teste...): e so um rotulo, e a renovacao
# automatica segue valendo para os dois.
certbot --nginx --non-interactive --cert-name "$ANTIGO" -d "$NOVO" -d "$ANTIGO" --expand

echo "==> 4. $ANTIGO leva para $NOVO"
if ! grep -q "return 301 https://$NOVO" "$NGINX"; then
  # Logo depois do PRIMEIRO server_name: o bloco do HTTPS, onde o sistema mora.
  awk -v antigo="$ANTIGO" -v novo="$NOVO" '
    !feito && /server_name/ {
      print
      print ""
      print "    # O endereco antigo leva ao novo, com o mesmo caminho: quem salvou"
      print "    # o link de teste no celular nao fica perdido."
      print "    if ($host = " antigo ") {"
      print "        return 301 https://" novo "$request_uri;"
      print "    }"
      feito = 1
      next
    }
    { print }
  ' "$NGINX" > "$NGINX.novo"
  mv "$NGINX.novo" "$NGINX"
fi
nginx -t
systemctl reload nginx

echo "==> 5. AMBIENTE=producao, 2 workers, pasta do Drive"
sed -i \
  -e 's/^AMBIENTE=homologacao/AMBIENTE=producao/' \
  -e 's/^UVICORN_WORKERS=1$/UVICORN_WORKERS=2/' \
  "$ENV"
# A pasta do Drive: a de teste ("Comprovantes - Teste") ate aqui. Passe o id
# da pasta de producao, ja compartilhada com a conta de servico, em
#   sudo PASTA_DRIVE=<id> ./virar-producao.sh
# Sem PASTA_DRIVE, a pasta nao muda.
if [ -n "${PASTA_DRIVE:-}" ]; then
  sed -i "s/^DRIVE_PASTA_ID=.*/DRIVE_PASTA_ID=$PASTA_DRIVE/" "$ENV"
fi
grep -E '^(AMBIENTE|UVICORN_WORKERS|DRIVE_PASTA_ID)=' "$ENV" | sed 's/^/    /'
systemctl restart natal-lumen-api

echo "==> 6. Copia do banco de hora em hora"
install -d -o natal-lumen -g natal-lumen -m 750 /var/lib/natal-lumen/backups/hora
install -m 644 "$AQUI/natal-lumen-backup-hora.service" /etc/systemd/system/
install -m 644 "$AQUI/natal-lumen-backup-hora.timer"   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now natal-lumen-backup-hora.timer
systemctl start natal-lumen-backup-hora.service
ls -1 /var/lib/natal-lumen/backups/hora | tail -1 | sed 's/^/    primeira copia: /'

echo "==> 7. Conferindo de fora"
# Ate 60s: com 2 workers a API demora mais que 5s para voltar, e a primeira
# execucao deste script acusou 502 numa virada que tinha dado certo.
for _ in $(seq 1 60); do
  curl -fsS "https://$NOVO/acesso/api/saude" > /dev/null 2>&1 && break
  sleep 1
done
SAUDE="$(curl -fsS "https://$NOVO/acesso/api/saude" || true)"
echo "    $NOVO -> $SAUDE"
REDIR="$(curl -fsSI "https://$ANTIGO/acesso/" 2>/dev/null | awk 'tolower($1)=="location:" {print $2}' | tr -d '\r')"
echo "    $ANTIGO -> $REDIR"
DOCS="$(curl -s -o /dev/null -w '%{http_code}' "https://$NOVO/acesso/api/docs")"
echo "    /docs -> $DOCS (fechada em producao: 404)"

if [ "$SAUDE" = '{"ok":true,"ambiente":"producao"}' ] && [ "$REDIR" = "https://$NOVO/acesso/" ] && [ "$DOCS" = "404" ]; then
  echo
  echo "PRONTO: o sistema e https://$NOVO/acesso/"
else
  echo
  echo "ATENCAO: alguma conferencia nao bateu. Mande esta saida."
  exit 1
fi
