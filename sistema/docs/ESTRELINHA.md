# Estrelinha ⭐ — perguntar ao Claude sobre os dados do Natal Lumen

A Estrelinha é um **conector do Claude** (um servidor MCP dentro da própria
API). Quem tem o link pergunta em português — "quantos apadrinhamentos a gente
teve ontem?", "quantos padrinhos apadrinharam crianças de 10 anos?" — e o
Claude escreve o SQL, consulta o banco **ao vivo** e responde.

Ela também lê a **lojinha no Shopify** (vendas, pedidos, produtos e
estoque), sem que a coordenação precise de conta no Shopify: as credenciais
ficam só no servidor.

```
Claude ──POST──▶ acesso.natallumen.com/acesso/api/estrelinha/mcp?key=TOKEN
                 └─ app/routers/estrelinha.py
                    ├─ usuária `estrelinha` do Postgres (só SELECT)
                    │  └─ views do schema `estrelinha` (migration e7a4c19b5d20)
                    └─ app/servicos/shopify.py  (ferramenta `consultar_loja`)
                       └─ Admin API do Shopify, app com escopos só de leitura
```

## O que ela vê, e o que não vê

Desde 15/11/2026 (migration `a3f9d27c6e18`), ela vê **todos os dados do
evento**: crianças com nome, padrinhos com contato, observações, pagamentos,
cartões, kits, usuários e o log. A decisão foi da coordenação, porque só
quem já vê tudo no sistema usa a Estrelinha.

Ficam de fora só as credenciais: `usuarios.senha_hash`, tentativas de login e
bloqueio, `tokens_acesso` e `sessoes_revogadas`.

As views usam `select *`, mas o Postgres congela as colunas na criação da
view. Coluna nova numa tabela só aparece para ela depois de uma migration que
recrie as views (copie a `a3f9d27c6e18` e rode `recriar()`).

## Segurança, em camadas

1. **Token:** sem `ESTRELINHA_TOKEN` no `.env`, a rota nem existe (404). Com
   ele, quem não manda o token certo leva 401. Para cortar o acesso de todo
   mundo, troque o token e reinicie a API.
2. **Usuária própria:** `estrelinha` só tem `SELECT` nas views. Escrever, ou
   ler a tabela real (onde está a senha), dá `permission denied` no Postgres.
3. **Transação só de leitura**, 15 s no máximo por consulta e 500 linhas por
   resposta.

`python -m tests.test_estrelinha` tenta ler o hash da senha e os tokens,
inserir, apagar por `WITH`, mandar duas consultas e travar o banco —
tudo tem de ser barrado.

---

## Ligar no servidor (uma vez)

### 1. Criar a usuária `estrelinha`

```bash
ssh acesso.natallumen.com
sudo -u postgres psql -d natal_lumen
```

```sql
create role estrelinha with login password 'SENHA_FORTE_AQUI';
alter role estrelinha set default_transaction_read_only = on;
alter role estrelinha set statement_timeout = '15s';
grant connect on database natal_lumen to estrelinha;
create schema if not exists estrelinha authorization natal_lumen;
grant usage on schema estrelinha to estrelinha;
grant select on all tables in schema estrelinha to estrelinha;
alter default privileges for role natal_lumen in schema estrelinha
  grant select on tables to estrelinha;
```

Gere a senha com `openssl rand -hex 24` (o servidor não tem `python3`).

### 2. Colocar no `.env` do servidor

Em `/var/www/natal-lumen/sistema/backend/.env`:

```
ESTRELINHA_DATABASE_URL=postgresql+psycopg://estrelinha:SENHA_FORTE_AQUI@localhost:5432/natal_lumen
ESTRELINHA_TOKEN=<openssl rand -hex 32>
```

### 3. Publicar

Pelo `/subir` de sempre. A migration cria as views, e o reinício da API lê o
`.env` novo. Para conferir de fora:

```bash
curl -s -X POST "https://acesso.natallumen.com/acesso/api/estrelinha/mcp?key=TOKEN" \
  -H "content-type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Tem de voltar a lista com `ver_estrutura` e `consultar`.

---

## Ligar a lojinha do Shopify (uma vez)

Sem as três linhas `SHOPIFY_*` no `.env`, a Estrelinha continua igual e
nem oferece a ferramenta da loja.

Desde 1º/01/2026 o Shopify não deixa mais criar app em *Configurações →
Apps → Desenvolver apps*. O app agora nasce no **Dev Dashboard**, e o sistema
troca o id e o segredo dele por um token de 24 h sozinho, sempre que precisa.

### 1. Criar o app no Dev Dashboard

1. No admin da loja, clique no nome da loja (canto de cima) → **Dev
   Dashboard**. Ou abra https://dev.shopify.com/dashboard com a mesma conta
   dona da loja. O app e a loja têm de estar na **mesma organização**.
2. **Create app** → nome `Estrelinha`.
3. Na versão do app, em **Access → Scopes**, marque só leitura:
   `read_orders`, `read_products`, `read_reports` (e `read_inventory`, se
   quiser estoque). Nada de `write_`.
4. **Release** a versão.
5. Em **Home** do app → **Install app** → escolha a loja do Natal Lumen →
   **Install**.
6. Em **Settings** do app, copie o **Client ID** e o **Client secret**.

### 2. Colocar no `.env` do servidor

Em `/var/www/natal-lumen/sistema/backend/.env`:

```
SHOPIFY_LOJA=SUBDOMINIO           # o xxx de xxx.myshopify.com
SHOPIFY_CLIENT_ID=...
SHOPIFY_CLIENT_SECRET=...
```

O subdomínio aparece em *Configurações → Domínios* (o endereço
`.myshopify.com`), mesmo que a loja use domínio próprio.

### 3. Reiniciar e conferir

```bash
sudo systemctl restart natal-lumen-api
```

O `tools/list` do curl da seção anterior passa a trazer também
`consultar_loja`. No Claude, desconecte e conecte a Estrelinha de novo (ou
abra uma conversa nova) para ela aparecer, e pergunte: "Estrelinha, quanto a
lojinha vendeu nos últimos 7 dias?"

### O que ela consegue, e os limites

- **Totais e rankings** (faturamento, unidades por produto, vendas por dia)
  vêm do **ShopifyQL**, que cobre todo o histórico.
- **Pedidos um a um** só alcançam os **últimos 60 dias**: é o limite do
  Shopify para apps sem `read_all_orders`, e o Dev Dashboard ainda não deixa
  pedir esse escopo.
- **Se aparecer `ACCESS_DENIED`** em pedidos ou no ShopifyQL, o Shopify está
  segurando os *dados protegidos de clientes*. Em app da própria loja isso
  costuma vir liberado, mas o Shopify bloqueia nos planos **Basic/Starter**.
  Nesse caso, os produtos e o estoque continuam funcionando; para as vendas,
  só subindo o plano.
- **Só leitura, em duas camadas:** o app só tem escopos `read_`, e o
  `shopify.consultar` recusa `mutation`/`subscription` antes de sair do
  servidor. `python -m tests.test_estrelinha_loja` tenta mandar mutations
  disfarçadas; tudo tem de ser barrado. Ele não fala com o Shopify de
  verdade nem precisa do banco.
- **Cortar o acesso à loja:** apague as linhas `SHOPIFY_*` e reinicie, ou
  desinstale o app *Estrelinha* na loja.

---

## Usar no Claude

1. No Claude, abra **Configurações → Conectores → Adicionar conector
   personalizado**.
2. Em nome, coloque `Estrelinha`. Em URL, coloque
   `https://acesso.natallumen.com/acesso/api/estrelinha/mcp?key=TOKEN`.
3. Numa conversa, pergunte: "Estrelinha, quantos apadrinhamentos a gente teve
   ontem?"

As instruções de como ler os dados (o que é edição, fuso de Fortaleza, cesta
e festa) vão junto com o conector, e o Claude as recebe ao conectar.

**Para a coordenação:** cada pessoa adiciona o conector com o mesmo link. O
link **é** a senha. Mande só por mensagem privada, e troque o token quando
alguém sair da coordenação.
