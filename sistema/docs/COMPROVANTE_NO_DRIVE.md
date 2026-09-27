# Comprovante de pagamento no Google Drive

O comprovante que a coordenação sobe na ficha do padrinho pode ir, além do
disco do servidor, para uma pasta do Drive do evento.

**Está desligado por padrão.** Sem credencial o sistema funciona exatamente
como antes: grava em disco e pronto. Nada quebra.

---

## 1. A regra que manda em tudo: o Drive é espelho

O comprovante é gravado **em disco primeiro** e só depois copiado para o
Drive. Se a cópia falhar, a requisição **não** falha: o pagamento está
registrado, o arquivo está salvo, e o link do Drive volta vazio.

Isso é deliberado. O comprovante é o registro de que alguém pagou — ele não
pode depender de o Google estar de pé naquele minuto. Para refazer a tentativa,
basta subir o comprovante de novo pela mesma tela.

A falha fica em `log_atividade` como `comprovante_drive_falhou`, com a
mensagem já traduzida.

---

## 2. Por que conta de serviço, e não "entrar com o Google"

Isto roda num servidor, sem navegador para a tela de consentimento. Um
*refresh token* de conta pessoal expira em 7 dias enquanto o app estiver em
"Testing" no console do Google — o upload pararia sozinho, sem aviso, dias
depois de alguém achar que estava tudo certo.

A conta de serviço não expira e não depende de ninguém estar logado.

---

## 3. Por que **Drive Compartilhado**, e não uma pasta do "Meu Drive"

Esta é a pegadinha que faz a maioria das integrações falhar na primeira vez.

Numa pasta comum do Meu Drive — mesmo compartilhada com a conta de serviço,
mesmo com permissão de Editor — o arquivo criado fica sendo **propriedade da
conta de serviço**. E conta de serviço **não tem cota de armazenamento
nenhuma**. O upload morre com `storageQuotaExceeded`, e a mensagem do Google
não explica nada disso.

Num **Drive Compartilhado** quem possui o arquivo é o próprio Drive, que tem a
cota da organização. O problema desaparece.

Por isso toda chamada leva `supportsAllDrives=true` — sem esse parâmetro a API
finge que Drives Compartilhados não existem.

> Drive Compartilhado exige **Google Workspace**. Numa conta `@gmail.com`
> comum ele não existe, e aí o caminho seria OAuth com refresh token de uma
> pessoa — com a ressalva dos 7 dias acima.

---

## 4. Como ligar

Uma vez só, no console do Google:

1. Criar (ou escolher) um projeto no **Google Cloud Console**.
2. Ativar a **Google Drive API** nesse projeto.
3. Criar uma **conta de serviço** e gerar uma chave **JSON**. Guardar o arquivo.
4. Criar o **Drive Compartilhado** do evento (menu "Drives compartilhados" →
   Novo), e dentro dele a pasta dos comprovantes.
5. Na pasta: **Compartilhar** → colar o `client_email` que está no JSON →
   permissão **Gerente de conteúdo**.
6. Abrir a pasta e copiar o id da URL:
   `https://drive.google.com/drive/folders/`**`ESTE_PEDACO_AQUI`**

No `.env` do backend:

```bash
# Caminho do JSON, ou o JSON inteiro colado numa linha só.
DRIVE_CREDENCIAIS=/etc/natal-lumen/conta-de-servico.json
DRIVE_PASTA_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz
```

Só isso. `config.drive_ligado` exige **os dois** preenchidos; faltando um, o
envio nem é tentado.

---

## 5. O que fica no Drive

Um arquivo por comprovante, na pasta configurada:

```
{CIDADE}_{ANO}_{NOME_DO_PADRINHO}_{AAAA_MM_DD}.jpg
FORTALEZA_2026_MARIANA_ALBUQUERQUE_2026_11_10.jpg
```

No disco, cidade e ano são pastas (`comprovantes/{cidade}/{ano}/`). No Drive a
pasta é uma só — a do evento — então eles entram no nome, senão dois
comprovantes de edições diferentes do mesmo padrinho colidiriam.

O `id` e o `webViewLink` voltam gravados em `pagamentos.comprovante_drive_id`
e `.comprovante_drive_link`, e o link sai no `PagamentoOut`.

---

## 6. Limites, e o que ainda não existe

- **Uma pasta para todas as edições.** Se cada evento precisar mesmo da sua
  própria pasta, o caminho é uma coluna `drive_pasta_id` em `edicoes` com
  queda para a configuração global. É uma coluna anulável e um campo na tela
  de Cidades e Edições — não foi feito.
- **A tela não mostra o link do Drive.** Ele volta na resposta da API, mas
  como a integração nasce desligada não havia o que mostrar. Quando ligar,
  vale um ícone de "abrir no Drive" ao lado do comprovante.
- **Trocar o comprovante não apaga o arquivo antigo do Drive.** No disco
  apaga (e apagar o pagamento também apaga). No Drive fica a versão anterior,
  de propósito: a lixeira do Drive é revisável por gente, e apagar
  automaticamente registro financeiro de dentro de um Drive compartilhado é
  mais arriscado do que deixar sobrando.
- Só JPG, PNG e PDF entram — a validação é a mesma do upload local.

---

## 7. Onde está o código

| Arquivo | O quê |
| --- | --- |
| `app/servicos/drive.py` | JWT RS256 → access_token → upload multipart. Espelha a forma de `whatsapp.py`. |
| `app/config.py` | `drive_credenciais`, `drive_pasta_id`, `drive_timeout_s`, `drive_ligado` |
| `app/routers/padrinhos.py` | `POST /pagamentos/{id}/comprovante` — grava local, depois espelha |
| `app/servicos/arquivos.py` | `nome_do_comprovante_drive()` |
| `alembic/versions/a7e2b91c4f08_*.py` | as duas colunas |
| `tests/test_padrinhos.py` | 13 verificações, com chave RSA de verdade e o Google simulado |

Os testes cobrem: desligado, ligado com sucesso, `supportsAllDrives`, a pasta
de destino, o nome com cidade e ano, e o caminho de falha — inclusive que o
comprovante continua salvo e que a explicação do Drive Compartilhado chega ao
log.
