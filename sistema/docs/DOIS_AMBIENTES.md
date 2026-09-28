# Homologação e produção

Duas máquinas, dois bancos, dois domínios. O que entra em produção passou antes
por homologação.

```
teste.natallumen.com    VPS   AMBIENTE=homologacao   segue o main
acesso.natallumen.com   VPS   AMBIENTE=producao      só o que tem tag
```

O domínio raiz, `natallumen.com`, não é de nenhum dos dois: é o Shopify, onde
fica a loja e o site público.

> **Para montar qualquer um dos dois servidores do zero**, siga o
> [HOSPEDAGEM.md](HOSPEDAGEM.md) — passo a passo, do contratar a VPS ao
> cadeado do HTTPS. Este documento aqui explica *por que* são dois e o que
> muda entre eles.

---

## 1. Por que duas máquinas, e não duas pastas na mesma

> **Esta seção mudou.** A justificativa original era memória: o EasyOCR comia
> ~1 GB de RAM por worker, produção ficava em ~2,5 GB, e um teste de leitura de
> cartão em homologação podia acionar o OOM killer do Linux — que escolhe a
> vítima pelo tamanho, e a maior seria a produção.
>
> **O EasyOCR saiu.** A identificação do cartão passou a ser pelo código no
> nome do arquivo, e a aplicação inteira cabe em **152 MB** (medido). O
> argumento de memória evaporou junto, e com ele a necessidade de 4 GB.

O que **continua** valendo é isolamento, que nunca foi sobre RAM: homologação
existe para você poder quebrar coisas. Se ela mora na mesma máquina que a
produção, um `systemctl` errado, um disco cheio ou uma migration travando o
Postgres derrubam as duas ao mesmo tempo.

Duas máquinas de 2 GB custam praticamente o mesmo que uma de 4 GB, e uma delas
pode cair sem levar a outra junto.

### As contas agora

```
aplicação, por worker .........   152 MB
produção, 2 workers ...........   ~300 MB
Postgres ......................   ~300 MB
nginx + sistema ...............   ~300 MB
                                 ────────
total em produção .............   ~900 MB   em 2 GB, com folga
```

---

## 2. Os três ambientes, e o que muda em cada um

`AMBIENTE` no `.env` aceita exatamente três valores:

| | `desenvolvimento` | `homologacao` | `producao` |
| --- | --- | --- | --- |
| Cookie `Secure` | não (HTTP local) | **sim** | **sim** |
| CORS para o Vite | sim | não | não |
| `/docs` | aberta | **aberta** | fechada |
| Link de definir senha na resposta | sim | **não** | não |

Duas escolhas que valem explicação:

**`/docs` fica aberta em homologação.** É um servidor de teste com dados
falsos; poder abrir a documentação da API e disparar uma chamada à mão economiza
tempo. Em produção some.

**O link de definir senha NÃO volta na resposta em homologação.** Em
desenvolvimento ele volta porque não há servidor de email e você está sozinho
no localhost. Homologação tem domínio público — quem soubesse um email entraria
na conta. Lá o acesso se cria pelo seed, que imprime o link no terminal.

> **Valor desconhecido derruba o arranque.** `AMBIENTE=prod` ou
> `AMBIENTE=produção` (com cedilha) fazem a aplicação **recusar a subir**. Antes
> isso passava em silêncio e caía no modo mais frouxo: cookie sem HTTPS e
> `/docs` aberta num servidor de produção, parecendo tudo bem.

---

## 3. Como o código anda

```
você trabalha  ──▶  main  ──▶  homologação  ──(tag)──▶  produção
```

**Homologação segue o `main`.** Todo commit que entra no main pode ir para lá:

```bash
ssh lumen@teste.natallumen.com
cd /var/www/natal-lumen
SERVICO=natal-lumen-api ./sistema/publicacao/publicar.sh
```

**Produção só recebe o que foi marcado.** Depois de ver funcionando em
homologação, você marca:

```bash
git tag -a v2026.1 -m "Ficha do padrinho com abas e pagamento"
git push origin v2026.1
```

E publica exatamente aquela marca:

```bash
ssh lumen@acesso.natallumen.com
cd /var/www/natal-lumen
REF=v2026.1 DOMINIO=acesso.natallumen.com ./sistema/publicacao/publicar.sh
```

A tag é o portão. Sem ela, "publicar em produção" seria pegar o que estivesse
no main naquele segundo — inclusive um commit de dez minutos atrás que ninguém
viu rodando.

`REF` também serve para **voltar atrás**: se a v2026.1 deu problema,
`REF=v2026.0 ./publicar.sh` devolve a versão anterior em um comando. Migration
já aplicada não volta sozinha — por isso migration que apaga coluna merece uma
janela de duas versões.

---

## 4. Os dados de homologação

Homologação precisa do **volume e dos formatos** da produção — o padrinho com
vinte crianças, a planilha de cem linhas, a paginação de verdade. Não precisa
dos nomes das crianças.

```bash
# na produção
pg_dump -Fc natal_lumen > producao.dump

# leve para o servidor de teste, e lá:
pg_restore -c -d natal_lumen producao.dump
python -m app.seeds.anonimizar --sim
python -m app.seeds.criar_admin "Seu Nome" "voce@exemplo.org"
```

| Muda | Fica |
| --- | --- |
| nomes de crianças, padrinhos e usuários | códigos, idades, sexo |
| WhatsApp e email | valores, datas, formas de pagamento |
| observações | todas as ligações entre as tabelas |
| senhas (zeradas) e tokens (apagados) | caminhos dos arquivos em disco |
| links do Drive | |

O nome falso é **estável**: a mesma linha dá sempre o mesmo nome, porque vem de
um hash do id e não de sorteio. Sem isso, comparar um print de ontem com a tela
de hoje viraria adivinhação.

**Duas travas no comando:**

1. Recusa rodar com `AMBIENTE=producao`. Ele apaga dado pessoal sem volta.
2. Sem `--sim`, só explica o que faria e sai.

As imagens dos cartões e os comprovantes **não são copiados** — só as linhas do
banco. As rotas de download respondem 404 para arquivo que não existe, que é o
comportamento certo. Os links do Drive são zerados para homologação não apontar
para o arquivo real na pasta da produção.

---

## 5. O que muda em cada `.env`

Igual nos dois: `DATABASE_URL` (bancos diferentes), `ARQUIVOS_DIR`,
`JWT_SECRET` (**gere um para cada** — não repita).

Diferente:

```bash
# homologação
AMBIENTE=homologacao
UVICORN_PORTA=8000
UVICORN_WORKERS=1
# WhatsApp e Drive vazios: teste não manda mensagem para padrinho de verdade
```

```bash
# produção
AMBIENTE=producao
UVICORN_PORTA=8000
UVICORN_WORKERS=2
```

> **Deixe WhatsApp e Drive desligados em homologação.** Com as credenciais de
> produção preenchidas, um teste de "reenviar cartão" mandaria mensagem de
> verdade para o WhatsApp de um padrinho — e os nomes já estariam anonimizados,
> então a mensagem sairia errada além de indesejada.

---

## 6. O que homologação pega, e o que não pega

**Pega** — e é por isso que ela existe: migration rodando sobre dados que já
existem; caminho do nginx (`/acesso`, `/acesso/api`); cookie `Secure` +
`SameSite` sob HTTPS de verdade; o build de produção do frontend (que não é o
mesmo do `npm run dev`); o systemd subindo; variável de ambiente faltando.

**Não pega:** envio real de WhatsApp e upload real para o Drive — os dois ficam
desligados lá de propósito. Continuam sendo verificados no seu computador e
pelos testes automatizados.

---

## 7. Instalar o servidor de homologação

Igual ao de produção, no [README § Publicação](../README.md) — com quatro
diferenças:

1. `AMBIENTE=homologacao` e `UVICORN_WORKERS=1`.
2. O `server_name` do nginx é `teste.natallumen.com`, e o certbot roda para ele.
3. Depois de instalar, restaure o dump e rode o `anonimizar`.
4. **Não coloque credencial de WhatsApp nem de Drive.**

E um pedido: ponha `noindex` no servidor de teste, para ele não aparecer em
busca. Uma linha no bloco do nginx:

```nginx
add_header X-Robots-Tag "noindex, nofollow" always;
```
