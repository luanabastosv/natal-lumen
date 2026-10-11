---
description: Testa, commita e publica o que está pendente na produção (acesso.natallumen.com)
---

Publique o trabalho pendente no servidor — **que é a produção**, com gente
usando. Não existe mais servidor de teste (ver `sistema/docs/AMBIENTES.md`).
**Nesta ordem**, sem pular etapas, e sem seguir adiante se alguma falhar.

## 1. Ver o que mudou

```bash
git status --short && git diff --stat
```

Se não houver nada pendente e o `main` local já estiver igual ao remoto e à
última tag publicada, diga isso e **pare**.

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
| `routers/monitoria.py`, `schemas/monitoria.py` | `test_monitoria` |
| `routers/criancas.py` | `test_criancas` |
| `routers/padrinhos.py` | `test_padrinhos` |
| `routers/cartoes.py` | `test_cartoes` |
| `routers/kits.py`, `compras.py`, `checkin.py`, `financeiro.py` | `test_logistica` |
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

**Migration nova?** Pergunte se ela já rodou o `./trazer_producao.sh` e testou
sobre a cópia da produção. Se não, ofereça rodar antes — é o único lugar onde a
migration encontra os dados de verdade antes de encontrá-los no servidor.

## 3. Commitar

Leia o diff de verdade antes de escrever a mensagem — ela deve dizer **por que**
mudou, não repetir o que o diff já mostra. Português, primeira linha curta e
concreta, corpo explicando a decisão. Separe em mais de um commit quando as
mudanças forem de assuntos diferentes.

Mostre a mensagem que pretende usar **antes** de commitar e espere o OK dela,
a menos que ela já tenha dito para seguir.

Termine cada mensagem com a linha `Co-Authored-By` da conversa.

## 4. Enviar e marcar

```bash
git push origin main
git tag -a vAAAA.MM.DD-N -m "<resumo de uma linha>"   # N = 1, 2... no mesmo dia
git push origin vAAAA.MM.DD-N
```

**Sem o push o servidor não vê nada**, e sem reclamar: ele lê do GitHub.
A tag é o que permite voltar atrás em um comando.

## 5. Publicar

Avise antes se for horário de uso: a API fica 3 a 5 segundos fora do ar.

```bash
ssh acesso.natallumen.com "cd /var/www/natal-lumen && REF=vAAAA.MM.DD-N DOMINIO=acesso.natallumen.com ./sistema/publicacao/publicar.sh"
```

O script faz uma cópia do banco antes da migration. Se ela falhar, nada sobe.

## 6. Conferir de fora — não confie só no script

```bash
ssh acesso.natallumen.com "cd /var/www/natal-lumen && git describe --tags"
curl -s https://acesso.natallumen.com/acesso/ | grep -oE 'index-[A-Za-z0-9]+\.(js|css)'
ssh acesso.natallumen.com "ls /var/www/natal-lumen/sistema/frontend/dist/assets/"
curl -s https://acesso.natallumen.com/acesso/api/saude
```

Só diga que subiu quando **as quatro** baterem: as duas linhas de `OK:` do
script, a tag certa no servidor, os nomes dos assets iguais nos dois lados, e
`{"ok":true,"ambiente":"producao"}`.

## Se falhar

A versão antiga continua no ar até a nova subir inteira. Para voltar à
anterior depois de publicada:

```bash
ssh acesso.natallumen.com "cd /var/www/natal-lumen && REF=<tag anterior> DOMINIO=acesso.natallumen.com ./sistema/publicacao/publicar.sh"
ssh acesso.natallumen.com "sudo journalctl -u natal-lumen-api -n 40 --no-pager"   # pede a senha dela
```

Se a migration estragou dado, a cópia de antes está em
`sistema/backups/antes-de-publicar/` — ver `sistema/docs/AMBIENTES.md`, seção 4.

## Ao terminar

Diga o que ela deveria olhar em `https://acesso.natallumen.com/acesso/` nesta
publicação especificamente — as telas que a mudança tocou.
