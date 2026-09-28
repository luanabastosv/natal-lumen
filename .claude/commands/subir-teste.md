---
description: Testa, commita e publica o que está pendente no ambiente de homologação (teste.natallumen.com)
---

Publique o trabalho pendente no servidor de homologação, **nesta ordem**.
Não pule etapas e não siga adiante se alguma falhar.

## 1. Ver o que mudou

```bash
git status --short && git diff --stat
```

Se não houver nada pendente e o `main` local já estiver igual ao remoto,
diga isso e **pare** — não há o que publicar.

## 2. Rodar os testes que a mudança pede

⚠️ **Este projeto NÃO usa pytest.** `pytest` responde `collected 0 items` e
parece sucesso. Os testes são scripts, rodados um a um:

```bash
cd sistema/backend && ./.venv/bin/python -m tests.NOME
```

Escolha pelas pastas tocadas, e rode **sempre** `test_seguranca`:

| Mudou em | Rode |
| --- | --- |
| `routers/painel.py`, `schemas/painel.py` | `test_painel` |
| `routers/criancas.py` | `test_criancas` |
| `routers/padrinhos.py` | `test_padrinhos` |
| `routers/cartoes.py` | `test_cartoes` |
| `routers/kits.py`, `compras.py`, `checkin.py` | `test_logistica` |
| `routers/usuarios.py`, `edicoes.py`, `cadastros` | `test_cadastros` |
| `routers/auth.py`, sessões, permissões | `test_autenticacao` |
| `models/`, migration nova | `test_esquema` |
| **qualquer coisa no backend** | `test_seguranca` (sempre) |

Cada um termina com `N verificacoes ok, 0 falha(s)`. **Qualquer falha: pare,
mostre a saída e não publique.**

Se mexeu no frontend:

```bash
cd sistema/frontend && npx oxlint && npm run build
```

## 3. Commitar

Leia o diff de verdade antes de escrever a mensagem — ela deve dizer **por que**
mudou, não repetir o que o diff já mostra. Siga o estilo do repositório:
português, primeira linha curta e concreta, corpo explicando a decisão.

Separe em mais de um commit quando as mudanças forem de assuntos diferentes
(documentação e código, por exemplo).

Mostre a mensagem que pretende usar **antes** de commitar e espere o OK dela.

Termine cada mensagem com:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

## 4. Enviar para o GitHub

```bash
git push origin main
```

**Sem isto o passo seguinte não publica nada**, e sem reclamar: o servidor lê
do GitHub, não da máquina dela.

## 5. Publicar

```bash
ssh teste.natallumen.com "cd /var/www/natal-lumen && DOMINIO=teste.natallumen.com ./sistema/publicacao/publicar.sh"
```

## 6. Conferir de fora — não confie só no script

```bash
# o servidor está no commit que acabou de subir?
ssh teste.natallumen.com "cd /var/www/natal-lumen && git log --oneline -1"

# o navegador recebe os arquivos recém-compilados?
curl -s https://teste.natallumen.com/acesso/ | grep -oE 'index-[A-Za-z0-9]+\.(js|css)'
ssh teste.natallumen.com "ls /var/www/natal-lumen/sistema/frontend/dist/assets/"

# a API responde no ambiente certo?
curl -s https://teste.natallumen.com/acesso/api/saude
```

Só diga que subiu quando **as quatro** baterem: as duas linhas de `OK:` do
script, o hash do commit igual ao que você acabou de enviar, os nomes dos
assets iguais nos dois lados, e `{"ok":true,"ambiente":"homologacao"}`.

## Se falhar

Nada se perde: a versão antiga continua no ar até a nova subir inteira.

```bash
ssh teste.natallumen.com "sudo journalctl -u natal-lumen-api -n 40 --no-pager"
```

## Ao terminar

Diga o endereço (`https://teste.natallumen.com/acesso/`) e **o que ela deveria
olhar** nesta publicação especificamente — as telas que a mudança tocou, não
uma lista genérica.

---

**Isto é só homologação.** Produção (`acesso.natallumen.com`) nunca recebe o
`main`: só o que tiver tag, com `REF=vX.Y`, e depois de visto funcionando
aqui. Ver `sistema/docs/DOIS_AMBIENTES.md`.
