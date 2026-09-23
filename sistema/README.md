# Sistema Natal Lumen

Sistema interno de gestão do evento, publicado em `https://DOMINIO/acesso`.
O site público (pasta `site/` na raiz) é um projeto separado e não faz parte daqui.

- Especificação: [docs/ESPECIFICACAO.md](docs/ESPECIFICACAO.md)
- Identidade visual: [docs/IDENTIDADE_VISUAL.md](docs/IDENTIDADE_VISUAL.md)

## Estado

| Fase | O que é | Situação |
| --- | --- | --- |
| 1 | Fundação do backend: 19 tabelas, migrations, seed de perfis | **pronta** |
| 2 | Autenticação e autorização | **pronta** |
| 3 | Fundação do frontend | **pronta** |
| 4 | Cadastros base (cidades, edições, instituições, usuários) | a fazer |
| 5 | Crianças e importação de listas | a fazer |
| 6 | Padrinhos, apadrinhamentos e pagamentos | a fazer |
| 7 | Cartões: digitalização, OCR e envio | a fazer |
| 8 | Kits, compras e check-in | a fazer |
| 9 | Painel e relatórios | a fazer |
| 10 | Publicação em /acesso | a fazer |

---

## Backend

Requisitos: Python 3.12 e PostgreSQL 16.

```bash
brew install python@3.12 postgresql@16
brew services start postgresql@16
```

### Base de dados

```bash
psql -d postgres -c "CREATE ROLE natal_lumen LOGIN PASSWORD 'natal_lumen_dev';"
psql -d postgres -c "CREATE DATABASE natal_lumen OWNER natal_lumen;"
```

> Se o `psql` não estiver no PATH:
> `export PATH="$(brew --prefix postgresql@16)/bin:$PATH"`

### Instalação

```bash
cd backend
$(brew --prefix python@3.12)/bin/python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env     # e ajuste a senha da base
```

O `requirements.txt` inclui o EasyOCR, que puxa o PyTorch: a instalação baixa
cerca de 2 GB e leva alguns minutos. Só é usado na fase 7.

Gere um segredo de sessão próprio para o `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Migrations

Toda alteração de estrutura passa por migration — nunca `CREATE TABLE` a mão.

```bash
cd backend
./.venv/bin/alembic upgrade head              # aplica tudo
./.venv/bin/alembic revision --autogenerate -m "o que mudou"
./.venv/bin/alembic downgrade -1              # desfaz a última
./.venv/bin/alembic current                   # em que ponto a base está
```

A URL da base vem do `.env` (via `app/config.py`), não do `alembic.ini` — assim
o mesmo arquivo de migration serve para desenvolvimento e produção, e nenhuma
credencial fica versionada.

### Seed de perfis e permissões

```bash
cd backend
./.venv/bin/python -m app.seeds.perfis_permissoes
```

Cria as 13 permissões e os 4 perfis (Coordenação, Comissário, Monitor,
Estrutura). É idempotente: rodar de novo não duplica nada, e não desfaz ajustes
feitos direto na base — os perfis existem na base justamente para poderem ser
alterados sem mexer no código.

### Testes

```bash
cd backend
./.venv/bin/python -m tests.test_esquema        # 22 verificações
./.venv/bin/python -m tests.test_autenticacao   # 50 verificações
```

`test_esquema` valida as restrições do banco com dados reais (um padrinho em
várias crianças, apadrinhamento entre cidades, unicidade de cartões e kits).

`test_autenticacao` cobre login e bloqueio, os atributos dos cookies, o CSRF, os
tokens de uso único e o isolamento de dados por edição e por instituição.

Nenhum dos dois deixa nada gravado na base.

### Primeiro acesso ao sistema

O sistema não tem cadastro aberto: as contas dos voluntários são criadas pela
coordenação, já de dentro. Para criar a primeira conta de administração geral:

```bash
cd backend
./.venv/bin/python -m app.seeds.criar_admin "Seu Nome" "voce@exemplo.org"
```

A conta nasce **sem senha**. O comando imprime um link de uso único, válido por
72 horas, em que a pessoa define a própria senha — a senha nunca passa pelo
terminal nem fica em histórico. Rodar de novo para a mesma conta gera um link
novo (útil se o anterior expirou ou a conta ficou bloqueada).

### Rodar a API

```bash
cd backend
./.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Documentação interativa em <http://localhost:8000/docs> (desligada em produção).

### Rotas de autenticação

| Método | Rota | O que faz |
| --- | --- | --- |
| `POST` | `/auth/login` | Abre a sessão. Devolve o usuário, as permissões e os vínculos. |
| `POST` | `/auth/logout` | Encerra a sessão. |
| `GET` | `/auth/eu` | Quem está na sessão. O frontend chama ao abrir. |
| `POST` | `/auth/definir-senha` | Define a senha pelo link de uso único. |
| `POST` | `/auth/esqueci-senha` | Gera link de redefinição (2 h). |
| `GET` | `/saude` | Confere que a API está de pé. |

### Como funciona o acesso

**Sessão.** JWT de 8 horas num cookie `httpOnly`, `SameSite=Strict`, com
`path=/acesso` — e `Secure` quando `AMBIENTE=producao`. O token nunca vai para o
`localStorage`. Cinco tentativas falhas bloqueiam a conta por 15 minutos.

**CSRF.** O JWT carrega um valor aleatório que também é gravado num segundo
cookie, `nl_csrf`, esse legível pelo JavaScript. Em todo `POST`, `PUT`, `PATCH`
e `DELETE`, o frontend copia esse valor para o cabeçalho `X-CSRF-Token`, e o
backend confere se bate com o que está dentro do token. Um site de terceiros não
consegue ler o cookie, então não consegue forjar o cabeçalho.

**Autorização.** Toda decisão acontece no backend; o frontend só esconde menus.
Cada rota declara a permissão que exige:

```python
@router.post("/cartoes")
def subir(ctx: ContextoAcesso = Depends(exige_permissao("subir_cartoes"))):
    ...
```

**Isolamento de dados (LGPD).** A permissão é por edição — a mesma pessoa pode
ser coordenação numa cidade e comissária noutra. As consultas são filtradas
pelas edições em que ela tem *aquela* permissão, e não por todas as suas
edições. Comissários e monitores ainda são limitados às instituições atribuídas
em `usuario_instituicao`. Use sempre o filtro do contexto:

```python
criancas = db.scalars(select(Crianca).where(ctx.filtro_criancas())).all()
```

Um comissário ou monitor **sem instituição atribuída não vê nenhuma criança** —
de propósito: o vínculo existe, mas a coordenação ainda não definiu por quais
instituições ele responde.

`admin_geral` alcança tudo, em todas as cidades.

**Log.** Login, logout, tentativa falhada, bloqueio e definição de senha vão para
`log_atividades`. O registro entra na mesma transação da ação, para nunca existir
log de algo que acabou desfeito.

### Organização

| Pasta | Responsabilidade |
| --- | --- |
| `app/config.py` | configuração lida do `.env` |
| `app/database.py` | engine, sessão e a classe `Base` |
| `app/models/` | as 19 tabelas: `operacao` · `apadrinhamento` · `logistica` · `acesso` |
| `app/schemas/` | entrada e saída das rotas (Pydantic) |
| `app/routers/` | as rotas, cada uma declarando a permissão exigida |
| `app/seguranca/` | senhas, JWT, CSRF e as dependências de autorização |
| `app/servicos/` | regra de negócio sem HTTP (OCR, importação, arquivos, log) |
| `app/seeds/` | dados iniciais |
| `alembic/versions/` | histórico de migrations |

### Arquivos enviados

Ficam em `ARQUIVOS_DIR` (por padrão `sistema/arquivos/`), **fora** das pastas
públicas do frontend. Nunca são servidos diretamente: só por rota autenticada
que confere a permissão e a edição do usuário. A pasta está no `.gitignore` —
são dados sensíveis (LGPD).

---

## Frontend

React 19 + Vite, JavaScript (sem TypeScript), como o site.

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Abre em <http://localhost:5173/acesso/>. **O backend precisa estar rodando**: o
Vite encaminha `/acesso/api` para `http://localhost:8000`, removendo o prefixo —
igual ao que o nginx fará em produção.

```bash
npm run lint     # oxlint
npm run build    # build de produção em dist/
npm run preview  # serve o build
```

### Telas

| Rota | O que é |
| --- | --- |
| `/acesso/entrar` | Login |
| `/acesso/definir-senha?token=...` | Primeiro acesso e redefinição de senha |
| `/acesso/esqueci-senha` | Pede o link de redefinição |
| `/acesso/painel` | Painel inicial, com atalhos do que o perfil alcança |
| `/acesso/criancas` e demais | Espaços reservados das próximas fases |

`/acesso` sem sessão cai no login; com sessão, vai para o painel.

### Organização

| Pasta | Responsabilidade |
| --- | --- |
| `src/services/` | `api.js` (fetch com cookie e CSRF) e `auth.js` |
| `src/contexts/` | sessão: usuário, permissões e edição ativa |
| `src/routes/` | `RotaProtegida` — exige sessão e, se pedido, permissão |
| `src/components/core/` | `Button` (portado do site), `Campo` |
| `src/components/layout/` | cabeçalho, menu, rodapé e a casca |
| `src/components/feedback/` | `EmptyState` (portado), `Carregando`, `Mensagem` |
| `src/styles/` | `tokens.css` (cópia do site), `base.css`, `layout.css` |
| `src/pages/` | as telas |

### Identidade visual

Os arquivos visuais foram **copiados** de `site/`, nunca importados — 11 fontes,
o mascote, a textura de estrelinhas e o `tokens.css` inteiro, sem alterar um
valor. O que o site não tinha (campos, tabelas, mensagens, carregamento,
navegação de aplicação) foi criado aqui sobre os mesmos tokens. Ver
[docs/IDENTIDADE_VISUAL.md](docs/IDENTIDADE_VISUAL.md).

**Celular.** O site público esconde o menu abaixo de 860px. Aqui não dá: muitos
voluntários usam o sistema pelo telefone. No mesmo ponto de quebra, o menu vira
uma gaveta de verdade — com botão, fundo escurecido, fecho por Esc e ao navegar.

### Como o frontend conversa com a API

O cookie de sessão é `httpOnly`: o JavaScript não consegue lê-lo, só perguntar
ao backend quem está na sessão (`GET /auth/eu`, feito uma vez ao abrir a
página). Todo pedido vai com `credentials: "include"`, e nos métodos que alteram
dados o `api.js` copia sozinho o cookie `nl_csrf` para o cabeçalho
`X-CSRF-Token` — nenhuma tela precisa se lembrar disso.

O `pode(permissao)` do contexto **apenas esconde menus**. Quem decide o acesso é
o backend, em cada rota.

---

## Rodando tudo junto

Dois terminais:

```bash
# terminal 1 — API
cd backend && ./.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# terminal 2 — telas
cd frontend && npm run dev
```

Depois abra <http://localhost:5173/acesso/>.

Na primeira vez, crie sua conta e abra o link que o comando imprime:

```bash
cd backend
./.venv/bin/python -m app.seeds.criar_admin "Seu Nome" "voce@exemplo.org"
```

> Se a porta 5173 estiver ocupada, o Vite sobe noutra e avisa no terminal — mas
> aí o endereço muda. Confira a linha `Local:` antes de abrir o navegador.

## Publicação em /acesso

A fazer na fase 10. O desenho previsto:

- `https://DOMINIO/` → site público (`site/dist`)
- `https://DOMINIO/acesso` → `sistema/frontend/dist`, com o servidor devolvendo
  `index.html` em qualquer subrota
- `https://DOMINIO/acesso/api` → uvicorn, com o FastAPI usando
  `root_path="/acesso/api"`. O servidor web precisa **remover** o prefixo antes
  de encaminhar (no nginx, `proxy_pass http://127.0.0.1:8000/;` — com a barra
  no fim): a aplicação atende em `/auth/login`, e o `root_path` serve só para
  ela montar os links e a documentação com o prefixo correto.

Frontend e API no mesmo domínio é o que permite o cookie de sessão `httpOnly`
com `SameSite=Strict` e `path=/acesso`, sem CORS em produção.
