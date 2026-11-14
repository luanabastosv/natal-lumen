# Estrelinha ⭐ — perguntar ao Claude sobre os dados do Natal Lumen

A Estrelinha é um **conector do Claude** (um servidor MCP dentro da própria
API). Quem tem o link pergunta em português — "quantos apadrinhamentos a gente
teve ontem?", "quantos padrinhos apadrinharam crianças de 10 anos?" — e o
Claude escreve o SQL, consulta o banco **ao vivo** e responde.

```
Claude ──POST──▶ acesso.natallumen.com/acesso/api/estrelinha/mcp?key=TOKEN
                 └─ app/routers/estrelinha.py
                    └─ usuária `estrelinha` do Postgres (só SELECT)
                       └─ views do schema `estrelinha` (migration e7a4c19b5d20)
```

## O que ela vê, e o que não vê

Ela só enxerga as views do schema `estrelinha`, nunca as tabelas reais:

| Vê | Não vê |
| --- | --- |
| edições, dias, instituições, grupos, ônibus e núcleo | usuários, senhas, sessões, log |
| crianças: código, idade, sexo, dia, check-in, falta, desistência | **nome da criança**, observações |
| padrinhos: nome, membro Ser Feliz, interesse mensal | **WhatsApp e e-mail**, observações |
| apadrinhamentos, pagamentos (valor, data, forma, conferido) | comprovantes, id do Mercado Pago |
| cobranças, envios e status dos cartões, kits | arquivos dos cartões, texto do OCR |
| autorizações: só sim/não de necessidade e restrição | **qual** necessidade ou restrição |
| compras e recebimentos | nome do doador |

Para mostrar mais uma coluna, crie uma migration nova que recria a view.

## Segurança, em camadas

1. **Token:** sem `ESTRELINHA_TOKEN` no `.env`, a rota nem existe (404). Com
   ele, quem não manda o token certo leva 401. Para cortar o acesso de todo
   mundo, troque o token e reinicie a API.
2. **Usuária própria:** `estrelinha` só tem `SELECT` nas views. Escrever ou ler
   a tabela real dá `permission denied` no próprio Postgres.
3. **Transação só de leitura**, 15 s no máximo por consulta e 500 linhas por
   resposta.

`python -m tests.test_estrelinha` tenta ler `usuarios`, ler o nome da
criança, inserir, apagar por `WITH`, mandar duas consultas e travar o banco —
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

Gere a senha com `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`.

### 2. Colocar no `.env` do servidor

Em `/var/www/natal-lumen/sistema/backend/.env`:

```
ESTRELINHA_DATABASE_URL=postgresql+psycopg://estrelinha:SENHA_FORTE_AQUI@localhost:5432/natal_lumen
ESTRELINHA_TOKEN=<python3 -c "import secrets; print(secrets.token_urlsafe(32))">
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
