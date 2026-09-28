# Colocar o sistema no ar — passo a passo

Guia para quem nunca administrou um servidor. Cada passo diz **em que site
entrar**, **o que clicar** e **o que colar no terminal**.

Reserve umas 3 horas para a primeira vez. Não precisa ser tudo no mesmo dia:
dá para parar no fim de qualquer parte.

---

## O mapa: o que você vai ter no fim

```
natallumen.com          →  Shopify          loja e site  (já existe)
acesso.natallumen.com   →  servidor 2       PRODUÇÃO     o que vale
teste.natallumen.com    →  servidor 1       HOMOLOGAÇÃO  onde pode quebrar
```

**Vamos montar o de teste primeiro.** Ele é idêntico ao de produção, e é onde
você vai errar à vontade sem risco nenhum. Quando o de teste estiver
funcionando, repetir para produção é o mesmo caminho, já conhecido.

Cada servidor tem **o seu próprio banco de dados**. Nada do que você fizer em
`teste` toca em `acesso`. Essa é a garantia que você pediu.

---

## Antes de começar: três palavras

**VPS** é um computador alugado, ligado 24h num data center. Você não vê tela
nem teclado dele: conversa por texto, pelo terminal.

**Terminal** é o aplicativo do seu Mac onde você digita comandos. Abra com
`Cmd + Espaço`, digite `Terminal`, Enter.

**`sudo`** na frente de um comando significa "faça isso como administrador".
Ele pode pedir a sua senha. Quando pedir, **digite normalmente — não vai
aparecer nada na tela, nem bolinhas.** É assim mesmo. Digite e dê Enter.

> **Sobre copiar e colar:** os blocos cinza deste guia são para colar no
> terminal, uma linha de cada vez (ou o bloco inteiro, quando forem linhas
> seguidas). Onde aparecer algo em MAIÚSCULAS como `SUBDOMINIO` ou
> `SENHA_DO_BANCO`, **troque pelo valor real antes de dar Enter.**

### O que ter em mãos

- [ ] Cartão de crédito para a Hostinger
- [ ] Acesso ao painel do Cloudflare (`natallumen.com`)
- [ ] Acesso à conta do GitHub `luanabastosv`
- [ ] Um gerenciador de senhas (**Bitwarden** é grátis e serve). Você vai gerar
      umas 6 senhas e segredos neste guia. **Guarde cada um lá na hora.**

---

# PARTE 1 — Preparar o seu Mac (10 min)

Você precisa de uma **chave SSH**: um par de arquivos que funciona como uma
chave de casa. A parte pública você entrega ao servidor; a privada fica no seu
Mac e nunca sai dele. É mais seguro que senha, e evita digitar senha toda vez.

Abra o Terminal e cole:

```bash
ls ~/.ssh/id_ed25519.pub
```

- **Apareceu um caminho de arquivo?** Você já tem chave. Pule para a Parte 2.
- **Apareceu "No such file or directory"?** Crie agora:

```bash
ssh-keygen -t ed25519 -C "luana-natal-lumen"
```

Ele vai perguntar três coisas. **Dê Enter nas três** (aceita o local padrão e
deixa sem senha extra). No fim aparece um desenho esquisito de asteriscos —
é normal, é a "arte" da chave.

Agora mostre a sua chave pública e **copie o resultado inteiro**:

```bash
cat ~/.ssh/id_ed25519.pub
```

Vai sair uma linha só, começando com `ssh-ed25519 AAAA...`. Guarde num
rascunho — você vai colar isso na Hostinger daqui a pouco.

> Essa linha **pode** ser mostrada a qualquer um: é a fechadura, não a chave.
> O arquivo sem `.pub` (`id_ed25519`) é que é secreto e nunca se envia.

---

# PARTE 2 — Contratar o servidor de teste (20 min)

### 2.1 Comprar

1. Entre em **[hostinger.com.br](https://www.hostinger.com.br)**
2. No menu, vá em **VPS** (não é "Hospedagem de Sites" — é outro produto)
3. Escolha o plano **KVM 1**, o mais simples. Ele tem RAM de sobra: o sistema
   inteiro ocupa cerca de 150 MB.
4. No período, quanto mais longo mais barato. Para o servidor **de teste**,
   pegue o prazo mais curto que compensar — se um dia você desligar a
   homologação, não fica dinheiro preso.
5. Finalize a compra.

### 2.2 Configurar

Depois da compra a Hostinger abre um assistente de configuração. Se ele não
abrir, entre em **[hpanel.hostinger.com](https://hpanel.hostinger.com)** →
**VPS** → clique no seu servidor.

Responda assim:

| Pergunta | Resposta |
| --- | --- |
| Sistema operacional | **Ubuntu 24.04 LTS** (só o sistema limpo, sem painel) |
| Localização | **São Paulo, Brasil** |
| Senha de root | gere uma longa no Bitwarden e **guarde lá** |
| Chave SSH | **adicione a sua** — cole a linha `ssh-ed25519 AAAA...` da Parte 1 |
| Nome do servidor | `natal-lumen-teste` |

> Se ele oferecer templates com "CyberPanel", "Plesk", "cPanel", **recuse**.
> Você quer o Ubuntu puro; esses painéis instalam um monte de coisa que vai
> conflitar com o nginx que o sistema usa.

Espere uns 5 minutos até o status virar **Running / Em execução**.

### 2.3 Anotar o IP

Na página do servidor, aparece o **IP** — quatro números separados por ponto,
tipo `191.101.23.45`. **Anote.** É o endereço do seu servidor na internet.

---

# PARTE 3 — Apontar o domínio (Cloudflare, 10 min)

Entre em **[dash.cloudflare.com](https://dash.cloudflare.com)** → clique em
**natallumen.com** → menu lateral **DNS** → **Records**.

Clique em **Add record** e preencha:

| Campo | Valor |
| --- | --- |
| Type | **A** |
| Name | `teste` |
| IPv4 address | o IP que você anotou |
| Proxy status | **DNS only** (a nuvem tem que ficar **CINZA**, não laranja) |
| TTL | Auto |

Salve.

### Por que a nuvem tem que ficar cinza

Dois motivos concretos, e o segundo é sério:

1. O certificado de segurança (o cadeado do HTTPS) é emitido por um programa
   que precisa alcançar o **seu** servidor. Com o proxy ligado, ele não passa.
2. O sistema tem uma trava contra ataque de senha: 10 tentativas de login por
   minuto **por IP**. Com o proxy da Cloudflare ligado, todos os pedidos chegam
   com o IP da Cloudflare — e a trava, em vez de limitar cada atacante,
   viraria um limite único para o mundo inteiro. O primeiro robô consumiria a
   cota de todo mundo e **derrubaria o login da equipe**.

Se um dia você quiser ligar o proxy (ele esconde o IP e filtra ataque), dá —
mas antes é preciso ensinar o nginx a ler o IP verdadeiro. Está anotado no topo
do arquivo [`publicacao/nginx.conf`](../publicacao/nginx.conf).

### Confira que o domínio já responde

No terminal do seu Mac:

```bash
dig +short teste.natallumen.com
```

Tem que devolver o IP do servidor. Se vier vazio, espere 5 minutos e tente de
novo (o DNS demora a se espalhar).

---

# PARTE 4 — Primeiro acesso e segurança básica (20 min)

### 4.1 Entrar no servidor

No terminal do Mac:

```bash
ssh root@teste.natallumen.com
```

Na primeira vez ele pergunta *"Are you sure you want to continue connecting?"*
— digite `yes` e Enter.

Se aparecer algo como `root@srv123:~#`, **você está dentro do servidor**. Daqui
em diante, tudo que você colar acontece lá, não no seu Mac.

> **Como saber onde você está:** o início da linha muda. No Mac aparece o nome
> do seu computador; no servidor aparece `root@...` ou `lumen@...`. Para sair e
> voltar ao Mac, digite `exit`.

### 4.2 Atualizar o sistema

```bash
apt update && apt upgrade -y
```

Demora uns minutos. Se abrir uma tela roxa perguntando sobre reiniciar
serviços, aperte **Tab** até destacar `<Ok>` e Enter. Se perguntar sobre manter
um arquivo de configuração, escolha **manter a versão instalada**.

### 4.3 Criar o seu usuário

Trabalhar como `root` é perigoso: qualquer erro de digitação pode apagar o
servidor inteiro, sem confirmação e sem volta. Vamos criar um usuário normal
que pede `sudo` para tarefas administrativas.

```bash
adduser lumen
```

Ele pede uma senha (**gere e guarde no Bitwarden**) e depois nome completo,
telefone etc. — **dê Enter em todos esses**, são opcionais. No fim confirme
com `Y`.

Dê poder administrativo a ele e copie a sua chave SSH:

```bash
usermod -aG sudo lumen

mkdir -p /home/lumen/.ssh
cp ~/.ssh/authorized_keys /home/lumen/.ssh/
chown -R lumen:lumen /home/lumen/.ssh
chmod 700 /home/lumen/.ssh
chmod 600 /home/lumen/.ssh/authorized_keys
```

A primeira linha dá poder administrativo ao `lumen`. As outras copiam para ele
a sua chave SSH, que a Hostinger instalou na conta `root` — sem isso você
criaria o usuário e não conseguiria entrar com ele.

### 4.4 Fechar a porta do root

Ainda como root:

```bash
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

Isso faz duas coisas: ninguém mais entra como `root` pela internet, e ninguém
entra por senha — só com chave. É o que elimina 99% das tentativas de invasão,
que são robôs testando `root` + senha comum o dia inteiro.

> ⚠️ **NÃO FECHE ESTA JANELA DO TERMINAL AINDA.** Se algo deu errado, ela é a
> sua única porta de entrada. Abra uma **segunda** janela de terminal
> (`Cmd + N`) e teste:
>
> ```bash
> ssh lumen@teste.natallumen.com
> ```
>
> Entrou? Ótimo. Agora pode fechar a primeira. **Não entrou?** Volte para a
> primeira janela (que ainda é root) e me chame antes de sair de lá.

### 4.5 Firewall

Já como `lumen`:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
sudo ufw status
```

Isso fecha todas as portas menos três: a do SSH (22), a do site (80) e a do
site seguro (443). O banco de dados fica acessível só de dentro da máquina.

### 4.6 Atualizações de segurança automáticas

```bash
sudo apt install -y unattended-upgrades fail2ban
sudo systemctl enable --now fail2ban
```

`unattended-upgrades` instala correções de segurança sozinho. `fail2ban` bane
temporariamente quem erra a entrada muitas vezes seguidas.

---

# PARTE 5 — Instalar os programas (15 min)

Tudo como `lumen`, dentro do servidor:

```bash
sudo apt install -y python3.12 python3.12-venv python3-pip \
    postgresql nginx git curl rsync
```

**Node.js** — o que vem no Ubuntu é velho demais para o frontend (o Vite 8 exige
Node 20+; o Ubuntu 24.04 traz o 18). Instale a versão certa:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version
```

Tem que mostrar `v22.` alguma coisa.

**Bibliotecas de imagem** — o sistema usa OpenCV para endireitar a foto do
cartão, e ele exige duas bibliotecas gráficas que não vêm num servidor sem
tela. Sem elas, **a API não sobe** (erro `libGL.so.1: cannot open shared
object file`):

```bash
sudo apt install -y libgl1 libglib2.0-0
```

E o certbot, que emite o certificado do cadeado:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

---

# PARTE 6 — Trazer o código (20 min)

### 6.1 Criar o usuário do serviço e a pasta

O sistema roda como um usuário **sem senha e sem poder nenhum**, chamado
`natal-lumen`. Se um dia alguém achar uma falha na aplicação, o estrago fica
limitado ao que esse usuário pode fazer — que é quase nada.

```bash
sudo adduser --system --group natal-lumen
sudo mkdir -p /var/www/natal-lumen
sudo chown lumen:lumen /var/www/natal-lumen
```

### 6.2 Dar ao servidor acesso de leitura ao GitHub

O repositório é privado, então o servidor precisa da própria chave. Crie uma:

```bash
ssh-keygen -t ed25519 -C "servidor-teste-natal-lumen" -f ~/.ssh/github -N ""
cat ~/.ssh/github.pub
```

Copie a linha inteira que apareceu. Agora, **no navegador do seu Mac**:

1. Entre em **[github.com/luanabastosv/natal-lumen](https://github.com/luanabastosv/natal-lumen)**
2. **Settings** (aba no topo do repositório, não a do seu perfil)
3. Menu lateral → **Deploy keys** → **Add deploy key**
4. Title: `servidor teste`
5. Key: cole a linha
6. **NÃO marque** "Allow write access" — o servidor só precisa ler
7. **Add key**

De volta ao servidor, ensine o git a usar essa chave:

```bash
cat >> ~/.ssh/config <<'FIM'
Host github.com
  IdentityFile ~/.ssh/github
  IdentitiesOnly yes
FIM
chmod 600 ~/.ssh/config
ssh -T git@github.com
```

A última linha deve responder algo como *"Hi luanabastosv/natal-lumen! You've
successfully authenticated, but GitHub does not provide shell access."* —
**isso é sucesso**, apesar do "but".

### 6.3 Baixar o código

```bash
git clone git@github.com:luanabastosv/natal-lumen.git /var/www/natal-lumen
cd /var/www/natal-lumen
ls
```

Tem que aparecer a pasta `sistema` entre outras.

---

# PARTE 7 — Banco de dados (10 min)

Gere uma senha forte para o banco e **guarde no Bitwarden**:

```bash
openssl rand -base64 24
```

Copie o resultado. Agora crie o usuário e o banco, **trocando `SENHA_DO_BANCO`
pelo que você acabou de copiar**:

```bash
sudo -u postgres psql -c "CREATE ROLE natal_lumen LOGIN PASSWORD 'SENHA_DO_BANCO';"
sudo -u postgres psql -c "CREATE DATABASE natal_lumen OWNER natal_lumen;"
```

> Se a senha gerada tiver aspas simples `'`, gere outra — ela quebraria o
> comando.

---

# PARTE 8 — A configuração (`.env`) (15 min)

Este é o arquivo mais importante e o único que não está no git: ele guarda
senhas e segredos.

```bash
cd /var/www/natal-lumen/sistema/backend
cp .env.example .env
```

Gere o segredo da sessão (é o que assina o "crachá" de quem está logado):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copie o resultado. Abra o arquivo para editar:

```bash
nano .env
```

> **Como usar o `nano`:** as setas movem o cursor, você digita normalmente. Para
> salvar: `Ctrl+O`, Enter. Para sair: `Ctrl+X`. Não existe mouse aqui.

Deixe estas cinco linhas assim (**apague o que estava e escreva o valor real**):

```bash
DATABASE_URL=postgresql+psycopg://natal_lumen:SENHA_DO_BANCO@localhost:5432/natal_lumen
JWT_SECRET=o-segredo-gerado-acima
AMBIENTE=homologacao
ARQUIVOS_DIR=/var/www/natal-lumen/sistema/arquivos
UVICORN_PORTA=8000
UVICORN_WORKERS=1
```

**E confirme que WhatsApp e Drive continuam comentados (com `#` na frente).**
Isso é proposital e importante: com as credenciais preenchidas, um teste de
"reenviar cartão" mandaria mensagem de verdade no WhatsApp de um padrinho real.

Salve (`Ctrl+O`, Enter, `Ctrl+X`) e tranque o arquivo:

```bash
sudo chown natal-lumen:natal-lumen .env
sudo chmod 600 .env
```

> Agora só o usuário do serviço (e o administrador via `sudo`) consegue ler o
> arquivo. É por isso que, mais adiante, o backup é rodado com `sudo`.

---

# PARTE 9 — Montar o backend (15 min)

```bash
cd /var/www/natal-lumen/sistema/backend
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

A instalação demora — são várias bibliotecas grandes (pandas, OpenCV). Pode
levar 5 minutos. Avisos em amarelo são normais; o que importa é não terminar
com `ERROR`.

Crie as tabelas e os dados iniciais:

```bash
sudo -u natal-lumen ./.venv/bin/alembic upgrade head
sudo -u natal-lumen ./.venv/bin/python -m app.seeds.perfis_permissoes
```

Crie a pasta dos arquivos enviados e dê a posse ao serviço:

```bash
sudo mkdir -p /var/www/natal-lumen/sistema/arquivos
sudo chown -R natal-lumen:natal-lumen /var/www/natal-lumen/sistema/arquivos
```

Crie a sua conta de administrador — **troque o nome e o email**:

```bash
sudo -u natal-lumen ./.venv/bin/python -m app.seeds.criar_admin "Luana Bastos" "luana@natallumen.com"
```

**Ele imprime um link na tela. COPIE E GUARDE** — é por ele que você define a
sua senha, e ele vale 72 horas. Se perder, dá para gerar outro rodando o mesmo
comando depois.

---

# PARTE 10 — Montar o frontend (10 min)

```bash
cd /var/www/natal-lumen/sistema/frontend
npm ci
npm run build
```

No fim tem que aparecer uma lista de arquivos e a palavra `built`. Confirme:

```bash
ls dist
```

Tem que ter `index.html` e uma pasta `assets`.

---

# PARTE 11 — Fazer a API subir sozinha (10 min)

O `systemd` é quem liga a API quando o servidor liga, e religa se ela cair.

```bash
cd /var/www/natal-lumen/sistema/publicacao
sudo cp natal-lumen-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now natal-lumen-api
sudo systemctl status natal-lumen-api
```

Procure por **`active (running)`** em verde. Aperte `q` para sair da tela de
status.

Teste se a API responde:

```bash
curl http://127.0.0.1:8000/saude
```

Resposta esperada: `{"ok":true,"ambiente":"homologacao"}`

> **Deu erro?** Veja o que ela reclamou:
> ```bash
> sudo journalctl -u natal-lumen-api -n 40 --no-pager
> ```
> Os dois erros mais comuns estão no **Socorro**, no fim deste guia.

---

# PARTE 12 — Abrir para a internet, com cadeado (15 min)

### 12.1 nginx

```bash
cd /var/www/natal-lumen/sistema/publicacao
sudo cp nginx.conf /etc/nginx/sites-available/natal-lumen
sudo sed -i 's/SUBDOMINIO/teste.natallumen.com/g' /etc/nginx/sites-available/natal-lumen
sudo ln -sf /etc/nginx/sites-available/natal-lumen /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default /var/www/html/index.nginx-debian.html
sudo nginx -t
```

A última linha tem que dizer `syntax is ok` e `test is successful`. Aí recarregue:

```bash
sudo systemctl reload nginx
```

### 12.2 O certificado (o cadeado)

```bash
sudo certbot --nginx -d teste.natallumen.com
```

Ele pergunta:

| Pergunta | O que responder |
| --- | --- |
| Email | o seu — é para avisar se o certificado for expirar |
| Termos de serviço | `Y` |
| Receber emails da EFF | `N` (tanto faz) |

No fim: *"Successfully received certificate"*. O certbot reescreve o nginx
sozinho, ligando o HTTPS e redirecionando quem chegar por HTTP. **A renovação
é automática**, a cada 90 dias — não precisa fazer nada.

### 12.3 O teste de verdade

No navegador do seu **Mac**, abra:

```
https://teste.natallumen.com
```

Você deve ver o **cadeado** na barra de endereço e cair na tela de entrada do
sistema. 🎉

Agora cole aquele **link de primeiro acesso** que você guardou na Parte 9,
defina a sua senha e entre.

---

# PARTE 13 — Backup para fora da máquina (20 min)

**Esta é a parte que você não pode pular.** O [`backup.sh`](../backend/backup.sh)
grava em `sistema/backups/`, que fica **no mesmo disco do servidor**. Se a
máquina morrer, o backup morre junto.

Duas coisas não dão para refazer: o banco de dados e a pasta `arquivos/`
(fotos dos cartões e comprovantes de pagamento — registro financeiro). O resto
está no git.

### 13.1 Teste o backup manualmente

```bash
cd /var/www/natal-lumen/sistema/backend
sudo ./backup.sh
ls -lh ../backups/
```

Devem aparecer dois arquivos: um `.dump` (o banco) e um `.tar.gz` (os
arquivos).

### 13.2 Mandar para fora

Você **já tem** uma conta de serviço do Google Drive configurada para os
comprovantes — dá para usar o mesmo Drive como destino do backup, com o
`rclone`:

```bash
sudo apt install -y rclone
rclone config
```

O `rclone config` é um assistente interativo e longo demais para transcrever
aqui, e as telas mudam de versão para versão. O caminho é: `n` (new remote) →
nome `drive` → tipo `drive` → e então **autenticação com a conta de serviço**,
apontando o mesmo JSON que o sistema usa.

> **Este passo é o único do guia que eu recomendo fazer junto comigo**, porque
> o `rclone config` tem muitas ramificações e errar ali significa achar que
> tem backup sem ter. Me chame quando chegar aqui.

Com o remote configurado, o envio é:

```bash
rclone copy /var/www/natal-lumen/sistema/backups drive:backups-natal-lumen
```

**Alternativa mais simples**, se preferir resolver hoje: o backup também pode
ser puxado para o seu Mac, com um comando que você roda de vez em quando:

```bash
# rode NO SEU MAC, não no servidor
rsync -avz lumen@acesso.natallumen.com:/var/www/natal-lumen/sistema/backups/ ~/Backups-NatalLumen/
```

Não é automático, mas é infinitamente melhor que nada — e o Mac já tem Time
Machine / iCloud atrás.

### 13.3 Automatizar

```bash
sudo crontab -e
```

Na primeira vez ele pergunta o editor — escolha `1` (nano). Vá até o fim do
arquivo e acrescente:

```
0 3 * * * /var/www/natal-lumen/sistema/backend/backup.sh >> /var/log/natal-lumen-backup.log 2>&1
```

Isso roda o backup **todo dia às 3h da manhã**. Salve com `Ctrl+O`, Enter,
`Ctrl+X`.

> **E o mais importante:** backup que nunca foi restaurado não é backup, é
> esperança. Uma vez por mês, restaure o backup da produção **no servidor de
> teste** — está descrito no [DOIS_AMBIENTES.md](DOIS_AMBIENTES.md), seção 4.
> Você testa o backup e atualiza os dados de teste no mesmo gesto.

---

# PARTE 14 — Repetir para produção

Refaça as Partes 2 a 13, com **cinco diferenças**:

| | teste | produção |
| --- | --- | --- |
| Nome do servidor | `natal-lumen-teste` | `natal-lumen` |
| Subdomínio (Cloudflare) | `teste` | `acesso` |
| `AMBIENTE` no `.env` | `homologacao` | `producao` |
| `UVICORN_WORKERS` | `1` | `2` |
| Deploy key no GitHub | `servidor teste` | `servidor producao` |
| WhatsApp e Drive | **vazios** | preenchidos |
| `JWT_SECRET` | um | **outro, gerado de novo** |
| `sed` do nginx | `teste.natallumen.com` | `acesso.natallumen.com` |

> **Não repita o `JWT_SECRET` entre os dois.** Se forem iguais, um crachá
> emitido no servidor de teste vale como entrada na produção.

`AMBIENTE=producao` muda três coisas sozinho: o cookie passa a exigir HTTPS, o
CORS é desligado e a página `/docs` some. E um valor escrito errado
(`prod`, `produção` com cedilha) **faz a API recusar a subir** — de propósito,
para não cair no modo mais frouxo em silêncio.

---

# PARTE 15 — O dia a dia, depois de tudo no ar

### Publicar uma mudança

O fluxo é: você trabalha → `main` → teste → (tag) → produção.

**No teste** (pega o que estiver no `main`):

```bash
ssh lumen@teste.natallumen.com
cd /var/www/natal-lumen
./sistema/publicacao/publicar.sh
```

**Na produção** (só o que foi marcado com uma tag, depois de você ver
funcionando no teste):

```bash
# no seu Mac
git tag -a v2026.1 -m "Descrição do que mudou"
git push origin v2026.1

# no servidor de produção
ssh lumen@acesso.natallumen.com
cd /var/www/natal-lumen
REF=v2026.1 ./sistema/publicacao/publicar.sh
```

A tag é o portão. Sem ela, "publicar em produção" seria pegar o que estivesse
no `main` naquele segundo — inclusive um commit de dez minutos atrás que
ninguém viu rodando.

**E é ela que desfaz um erro:** se a `v2026.1` deu problema,
`REF=v2026.0 ./sistema/publicacao/publicar.sh` devolve a versão anterior em um
comando.

### Comandos que você vai usar

```bash
sudo systemctl status natal-lumen-api        # a API está de pé?
sudo systemctl restart natal-lumen-api       # religar a API
sudo journalctl -u natal-lumen-api -n 50     # últimas 50 linhas do log
sudo journalctl -u natal-lumen-api -f        # log ao vivo (Ctrl+C para sair)
df -h                                        # o disco está enchendo?
free -h                                      # a memória está apertada?
```

### Monitoramento (5 min, grátis)

Entre em **[uptimerobot.com](https://uptimerobot.com)**, crie conta grátis e
adicione um monitor:

- Type: **HTTP(s)**
- URL: `https://acesso.natallumen.com/acesso/api/saude`
- Intervalo: 5 minutos
- Alerta: o seu email (e WhatsApp, se quiser)

Se o sistema cair de madrugada, você fica sabendo antes da equipe.

---

# Socorro

### A API não sobe

```bash
sudo journalctl -u natal-lumen-api -n 40 --no-pager
```

| O que diz o erro | O que é | Conserto |
| --- | --- | --- |
| `libGL.so.1: cannot open shared object file` | falta biblioteca gráfica do OpenCV | `sudo apt install -y libgl1 libglib2.0-0` |
| `AMBIENTE=... nao existe` | valor errado no `.env` | só vale `desenvolvimento`, `homologacao` ou `producao` |
| `password authentication failed` | senha do banco errada no `.env` | confira a `DATABASE_URL` |
| `Permission denied: '.env'` | o serviço não consegue ler o arquivo | `sudo chown natal-lumen:natal-lumen .env` |
| `ModuleNotFoundError` | faltou instalar dependência | rode o `pip install -r requirements.txt` de novo |

### O site abre mas dá "502 Bad Gateway"

O nginx está de pé, a API não. Veja o log da API acima.

### O site abre mas dá "404" nas telas internas

Falta o `try_files` do nginx, ou o `npm run build` não rodou. Confira que
`sistema/frontend/dist/index.html` existe.

### Não consigo mais entrar por SSH

Entre pelo **console de emergência da Hostinger**: hPanel → VPS → seu servidor
→ **Browser terminal** (ou "Console"). Ele funciona mesmo com o SSH quebrado,
e entra como `root` com a senha que você guardou no Bitwarden.

### Perdi o link de primeiro acesso

```bash
cd /var/www/natal-lumen/sistema/backend
sudo -u natal-lumen ./.venv/bin/python -m app.seeds.criar_admin "Luana Bastos" "luana@natallumen.com"
```

Ou, se você já consegue entrar com outra conta de gestor, dá para gerar um link
novo pela própria tela de **Usuários**.

---

## Um buraco conhecido, para você saber que existe

**"Esqueci minha senha" não envia email.** O sistema gera o link de
redefinição, mas não há servidor de email configurado — então ninguém recebe.
Em desenvolvimento o link volta na tela; em homologação e produção, não (seria
uma porta aberta: quem soubesse um email entraria na conta).

**Isso não impede a estreia.** Quando alguém da equipe esquecer a senha, um
gestor entra em **Usuários**, gera um link de acesso novo e manda por WhatsApp.

Se quiser autoatendimento de verdade depois, é preciso: contratar um serviço de
envio (Resend e Brevo têm plano grátis suficiente para o volume de vocês),
configurar SPF e DKIM no Cloudflare, e escrever o envio no
[`auth.py`](../backend/app/routers/auth.py). É uma tarde de trabalho, e pode
esperar o pós-evento.
