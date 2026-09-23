# Site Natal Lumen

Site em React (pasta `site/`) e backend em Python para a digitalização dos
cartões de monitoria (pasta `backend/`).

## O que o sistema de cartões faz

1. Você escolhe a instituição numa lista.
2. Envia a foto de um cartão.
3. O backend detecta as bordas do cartão e corrige a perspectiva (digitalização).
4. Lê o nome escrito no cartão com OCR e mostra o nome detectado.
5. Você confirma ou corrige o nome.
6. A imagem digitalizada é salva em `backend/cartoes_digitalizados/` como
   `INSTITUICAO_NOME.jpg` e o registro vai para a base de dados.

---

## Backend

Requisitos: Python 3.12 (instalado com `brew install python@3.12`).

### Instalação

```bash
cd backend
$(brew --prefix python@3.12)/bin/python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

O `requirements.txt` puxa o PyTorch (dependência do EasyOCR), por isso a
instalação baixa cerca de 2 GB e leva alguns minutos.

### Instituições de exemplo

```bash
cd backend
./.venv/bin/python seed.py
```

Cria a base `cartoes.db` (se ainda não existir) e insere 5 instituições.
Pode rodar mais de uma vez: nomes repetidos não são duplicados.
Para cadastrar as instituições reais, edite a lista `INSTITUICOES` em
[backend/seed.py](backend/seed.py).

### Rodar

```bash
cd backend
./.venv/bin/python -m uvicorn main:app --reload --port 8000
```

Na primeira execução o EasyOCR baixa os modelos de reconhecimento (~100 MB);
espere a mensagem `Pronto. API em http://localhost:8000`. Nas próximas vezes
o servidor sobe em poucos segundos.

Documentação interativa das rotas: <http://localhost:8000/docs>

### Rotas

| Método | Rota | O que faz |
| --- | --- | --- |
| `GET` | `/instituicoes` | Lista as instituições. |
| `POST` | `/cartoes/analisar` | Recebe `imagem` + `instituicao_id`. Digitaliza, roda o OCR e devolve um id temporário, o nome sugerido, todos os textos detectados com a confiança e a imagem em base64. Não grava nada na base. |
| `POST` | `/cartoes/confirmar` | Recebe `id`, `instituicao_id` e `nome`. Move a imagem para `cartoes_digitalizados/` com o nome final e grava o registro. |
| `GET` | `/cartoes` | Lista os cartões salvos. |

### Base de dados

SQLite por padrão, no arquivo `backend/cartoes.db`, criado automaticamente.
A conexão fica na variável `DATABASE_URL` do arquivo `backend/.env`:

```
DATABASE_URL=sqlite:///./cartoes.db
```

Para trocar por PostgreSQL depois, basta mudar essa linha (e instalar o driver
`psycopg2-binary`):

```
DATABASE_URL=postgresql+psycopg2://usuario:senha@localhost:5432/cartoes
```

Tabelas: `instituicoes` (id, nome único) e `cartoes` (id, nome,
instituicao_id, caminho_arquivo, criado_em).

### Arquivos

| Arquivo | Responsabilidade |
| --- | --- |
| [backend/main.py](backend/main.py) | Rotas, CORS e inicialização do EasyOCR. |
| [backend/database.py](backend/database.py) | Conexão e modelos SQLAlchemy. |
| [backend/scanner.py](backend/scanner.py) | Digitalização com OpenCV e leitura com OCR. |
| [backend/utils.py](backend/utils.py) | Montagem do nome do arquivo. |
| [backend/seed.py](backend/seed.py) | Instituições de exemplo. |

### Ajustar o OCR

A escolha do nome sugerido está isolada em `escolher_nome_sugerido()`, em
[backend/scanner.py](backend/scanner.py). As regras, por ordem:

1. Se o cartão tiver "Nome:", usa o texto que vem depois do rótulo (na mesma
   linha ou na linha de baixo).
2. Caso contrário, usa a linha com a maior altura de letra.

Textos curtos, com confiança baixa ou que são só números são descartados antes.
Os parâmetros ficam no topo dessa seção do arquivo e podem ser ajustados
conforme os cartões reais:

- `CONFIANCA_MINIMA` (0.30) — confiança mínima do OCR.
- `TAMANHO_MINIMO` (3) — número mínimo de letras.
- `TOLERANCIA_MESMA_LINHA` (0.6) — aumente se um nome sair partido ao meio.

Na digitalização, `AREA_MINIMA_DO_CARTAO` (0.20) define quanto da foto o cartão
precisa ocupar para as bordas serem aceitas. Se as bordas não forem
encontradas, a foto é usada como está e a resposta traz o aviso
`bordas não detectadas` — nunca dá erro.

---

## Frontend

```bash
cd site
npm install
npm run dev
```

A página dos cartões fica em <http://localhost:5173/cartoes-monitoria> e também
no link "Cartões Monitoria" do menu do site.

A URL do backend fica em `site/.env`:

```
VITE_API_URL=http://localhost:8000
```

### Arquivos

| Arquivo | Responsabilidade |
| --- | --- |
| [site/src/pages/CartoesMonitoria.jsx](site/src/pages/CartoesMonitoria.jsx) | A página. |
| [site/src/pages/CartoesMonitoria.css](site/src/pages/CartoesMonitoria.css) | Estilos da página (usa os tokens de `src/styles/tokens.css`). |
| [site/src/services/api.js](site/src/services/api.js) | Chamadas ao backend. |
| [site/src/App.jsx](site/src/App.jsx) | Rotas (`react-router-dom`). |

### Outros comandos

```bash
npm run lint     # oxlint
npm run build    # build de produção em dist/
npm run preview  # serve o build
```

Ao publicar o build, configure o servidor para devolver o `index.html` em
qualquer rota — sem isso, abrir `/cartoes-monitoria` direto no navegador dá 404.

---

## Rodando os dois juntos

Dois terminais:

```bash
# terminal 1
cd backend && ./.venv/bin/python -m uvicorn main:app --reload --port 8000

# terminal 2
cd site && npm run dev
```

O CORS do backend já libera as portas 5173 (Vite) e 3000.

## O que não é versionado

`backend/.gitignore` e `site/.gitignore` já excluem `.venv/`, `.env`,
`cartoes.db` e as pastas de imagens (`cartoes_temp/`, `cartoes_digitalizados/`).
Os arquivos `.env.example` das duas pastas servem de modelo.
