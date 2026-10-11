# Um servidor, e o teste no seu computador

Desde 11/10/2026 o sistema tem **um** servidor, o de produção. Não existe mais
servidor de teste: o que antes ia para homologação agora é testado no
computador de quem programa, com uma cópia dos dados de verdade.

```
acesso.natallumen.com   VPS (Vultr Miami)   AMBIENTE=producao   só o que tem tag
teste.natallumen.com    o mesmo servidor    redireciona para acesso.natallumen.com
seu computador          localhost:5173      AMBIENTE=desenvolvimento
```

O domínio raiz, `natallumen.com`, é o Shopify: a loja e o site público.

---

## 1. Por que um servidor só

Havia dois: homologação para poder quebrar, produção para valer. A decisão de
juntar foi tomada às vésperas do lançamento (13/10/2026), por três motivos:

- **Uma pessoa mexe no código.** Homologação serve para muita gente conferir o
  trabalho de muita gente. Aqui ela só repetia o que já tinha sido visto no
  computador.
- **O sistema é pequeno.** Cabe com folga numa máquina de 2 GB (cerca de 900 MB
  em uso, com 2 workers), e o banco tem dezenas de MB.
- **Dois servidores custam cuidado.** O de teste ficava desatualizado, cada
  publicação era feita duas vezes, e um servidor esquecido é um servidor sem
  atualização de segurança.

O que o servidor de teste pegava, e o computador sozinho não pega, agora é
coberto assim:

| O risco | Como fica coberto |
| --- | --- |
| Migration que estraga dado de verdade | testar antes com `trazer_producao.sh` (seção 3) **e** cópia automática do banco antes de cada publicação (seção 4) |
| Publicar algo que ninguém viu rodando | só sobe o que tem tag, e a tag aponta para um commit testado |
| Versão nova com defeito | `REF=<tag anterior>` volta em um comando |
| Build de produção diferente do `npm run dev` | `npm run build && npm run preview` no computador antes da tag |

O que **não** fica coberto, e foi aceito: não há onde testar com HTTPS e o
nginx de verdade antes de publicar. Mudança no `nginx.conf`, no `.service` ou
no cookie de sessão pede publicação fora do horário de uso, com alguém olhando.

---

## 2. Os três valores de `AMBIENTE`

`AMBIENTE` no `.env` continua aceitando três valores, embora só dois sejam
usados agora:

| | `desenvolvimento` | `homologacao` | `producao` |
| --- | --- | --- | --- |
| Onde | seu computador | (não usado) | o servidor |
| Cookie `Secure` | não | sim | sim |
| CORS para o Vite | sim | não | não |
| `/docs` | aberta | aberta | fechada |
| Link de definir senha na resposta | sim | não | não |
| `anonimizar` roda | sim | sim | **recusa** |
| `CHECKIN_SEMPRE_ABERTO` | vale | vale | **ignorado** |

Um valor escrito errado (`prod`, `produção`) faz a API recusar a subir.

---

## 3. Testar com os dados de verdade, no seu computador

```bash
cd sistema/backend
./trazer_producao.sh
```

O script guarda o seu banco local, baixa a produção pelo `ssh` e troca o banco
local por ela — uma cópia **exata**, com nomes, contatos e senhas de verdade.
Entra-se com o mesmo email e senha da produção.

O `.env` local **não tem** credencial de WhatsApp nem de Drive, e é isso que
impede um teste daqui de mandar mensagem a um padrinho ou subir arquivo na
pasta de verdade. Mantenha assim.

Use antes de publicar **qualquer migration**. As fotos e os comprovantes não
vêm junto (só o banco): as imagens aparecem como "não encontrado", e está certo.

---

## 4. Como o código chega ao servidor

```
seu computador  ──▶  main no GitHub  ──(tag)──▶  produção
```

1. Testes e build no computador (`/subir` faz isso).
2. Commit e push para o `main`.
3. Uma tag com a data: `v2026.10.12-1`, `v2026.10.12-2`...
4. Publicação daquela tag:

```bash
ssh acesso.natallumen.com "cd /var/www/natal-lumen && REF=v2026.10.12-1 DOMINIO=acesso.natallumen.com ./sistema/publicacao/publicar.sh"
```

O `publicar.sh` faz uma cópia do banco **antes** da migration (guarda as 10
últimas em `sistema/backups/antes-de-publicar/`). Se a cópia falhar, nada é
publicado.

**Voltar atrás:** publique a tag anterior com o mesmo comando. O código volta;
o banco, não — migration aplicada não se desfaz sozinha. Se a migration
estragou dado, restaure a cópia feita antes de publicar:

```bash
cd /var/www/natal-lumen/sistema/backend
sudo systemctl stop natal-lumen-api
# PGPASSWORD etc.: ver o backup.sh
pg_restore --clean --if-exists -d natal_lumen ../backups/antes-de-publicar/<o mais recente>.dump
sudo systemctl start natal-lumen-api
```

Publique fora do horário de uso: a API fica 3 a 5 segundos fora do ar no
reinício.

---

## 5. As cópias do banco

| Quando | Onde | Quantas | O que |
| --- | --- | --- | --- |
| Antes de cada publicação | `sistema/backups/antes-de-publicar/` | 10 | banco |
| De hora em hora (minuto 40) | `/var/lib/natal-lumen/backups/hora/` | 48 | banco |
| Toda madrugada (00h10 de Brasília) | `/var/lib/natal-lumen/backups/` **e Drive** | 14 | banco + arquivos + planilha |
| Automática | painel da Vultr (Automatic Backups) | a da Vultr | a máquina inteira |

As de hora em hora protegem do erro humano do meio do dia. A da madrugada é a
única que sai da máquina: se o disco morrer, é dela que se volta.

---

## 6. Como o servidor de teste virou o de produção

Feito uma vez, em outubro de 2026, pelo
[`publicacao/virar-producao.sh`](../publicacao/virar-producao.sh): backup,
nome novo no nginx, certificado para os dois nomes, redirecionamento do nome
antigo, `AMBIENTE=producao`, 2 workers e as cópias de hora em hora. O que tinha
sido lançado só para testar (padrinhos, pagamentos, cartões, compras, kits) saiu
pelo `app.seeds.limpar_operacao`.

A máquina continua em **Miami**. São Paulo responderia mais rápido para quem
usa do Nordeste, mas a diferença (cerca de 0,1 s por pedido) não justificava
mudar de servidor às vésperas do lançamento. Se um dia mudar, siga o
[HOSPEDAGEM.md](HOSPEDAGEM.md) e restaure o backup da madrugada na máquina nova.
