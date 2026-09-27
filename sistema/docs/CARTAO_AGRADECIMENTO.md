# Cartão de agradecimento

A arte que o padrinho recebe no WhatsApp: **um cartão por criança apadrinhada**,
com o nome dela, o código, a instituição e o dia em que ela estará no evento.

Onde fica: **Padrinhos → botão "Cartão"**, na linha de cada criança apadrinhada.
Baixa um PNG pronto para anexar na conversa.

O arquivo sai como **`{CÓDIGO}_{NOME_DA_CRIANÇA}.png`** — `001_ANA_CLARA_AVILA.png`.
Sem acento e sem espaço, como já são os cartões digitalizados: assim o arquivo
atravessa WhatsApp, Windows e Drive sem virar `001_Ana%20Clara%20A%CC%81vila`.

Nada é guardado em disco: a arte é montada na hora. Se o nome da criança ou o
dia do evento mudarem, é só baixar de novo.

---

## Enviar pelo WhatsApp

Ao lado de "Cartão" há o botão **"WhatsApp"** (desabilitado se o padrinho não
tem número cadastrado). Ele se comporta de dois jeitos:

| Onde | O que acontece |
| --- | --- |
| **Celular** | Abre a folha de compartilhar nativa **com o PNG dentro**. Escolha WhatsApp → escolha o contato → enviar. A imagem vai de verdade. |
| **Desktop** | Baixa o PNG e abre a conversa do padrinho já com a mensagem escrita. Quem envia arrasta a imagem para a janela. |

**Por que no desktop não vai sozinho.** O link do WhatsApp
(`wa.me` / `web.whatsapp.com/send`) carrega **só texto** — não existe parâmetro
para anexar arquivo, nem na web nem no aplicativo. Nenhum truque de front-end
contorna isso: é limite da plataforma. No celular o caminho é outro
(`navigator.share` com arquivo), e por isso lá funciona.

### Envio automático (WhatsApp Cloud API)

Está **implementado**. Com as credenciais no `.env`, o botão "WhatsApp" manda
o cartão sozinho: o servidor sobe o PNG para a Meta e dispara o template. Sem
credenciais, o mesmo botão cai no envio a mão descrito acima — ninguém fica
sem poder enviar.

Bibliotecas não oficiais que pilotam o WhatsApp Web por baixo dos panos
(whatsapp-web.js, Baileys e afins) fazem isso sem custo, mas **violam os termos
do WhatsApp e podem derrubar o número da organização** — justamente o número
que fala com os padrinhos. Não usamos.

---

## Ligar a Cloud API

Cinco passos. Os quatro primeiros são na Meta, e só você pode fazer.

### 1. Conta e número

1. Um **Meta Business Account** (business.facebook.com), com o CNPJ da
   organização verificado.
2. Em **WhatsApp → Introdução**, crie a **WhatsApp Business Account (WABA)**.
3. Cadastre um **número dedicado**. Ele **não pode** estar ativo no app do
   WhatsApp comum nem no Business — se estiver, apague a conta daquele número
   antes. Depois de virar Cloud API, o número só fala pela API.

### 2. Token que não expira

O token que a Meta mostra no painel dura 24h — serve para testar, não para
produção. Para o definitivo:

1. **Configurações do Business → Usuários → Usuários do sistema**
2. Crie um usuário de sistema com papel de administrador
3. **Gerar novo token** → escolha o app → permissões `whatsapp_business_messaging`
   e `whatsapp_business_management` → validade **Nunca**

Guarde: esse token dá acesso de envio. Ele vai no `.env`, nunca no Git.

### 3. Template aprovado

Mensagem que **a organização inicia** só sai em template aprovado — é a regra
da Meta, não escolha nossa. Em **WhatsApp Manager → Modelos de mensagem**:

| Campo | Valor |
| --- | --- |
| Nome | `cartao_agradecimento` (o mesmo do `WHATSAPP_TEMPLATE`) |
| Idioma | Português (BR) — `pt_BR` |
| Categoria | **Utilidade** (é confirmação de uma transação existente, o apadrinhamento) |
| Cabeçalho | **Mídia → Imagem** |
| Corpo | precisa ter exatamente dois parâmetros, nesta ordem |

Corpo sugerido:

```
Oi, {{1}}! 💛 Obrigado por apadrinhar a {{2}} no Natal Lumen.
Este é o cartão dela — guarde com carinho. Qualquer dúvida, é só responder aqui.
```

`{{1}}` = primeiro nome do padrinho · `{{2}}` = primeiro nome da criança.
**A ordem importa**: é a que o código manda em `whatsapp.py`.

A aprovação costuma sair em minutos, mas pode levar até 24h. Se a Meta
classificar como *Marketing* em vez de *Utilidade*, o custo por mensagem sobe —
vale ajustar o texto para soar como confirmação, não como divulgação.

### 4. Opt-in

A Meta exige que o padrinho tenha concordado em receber mensagens antes do
primeiro envio. Na prática: deixe explícito na ficha de apadrinhamento que o
WhatsApp informado será usado para enviar o cartão e avisos do evento.

### 5. `.env`

```bash
WHATSAPP_TOKEN=EAAG...                  # do passo 2
WHATSAPP_PHONE_NUMBER_ID=123456789012345  # WhatsApp Manager → API Setup
WHATSAPP_TEMPLATE=cartao_agradecimento
WHATSAPP_IDIOMA=pt_BR
WHATSAPP_VERSAO_API=v21.0
```

Reinicie a API. Pronto — o botão passa a enviar sozinho.

> **Custo.** A Meta cobra por mensagem de template, com preço por país e por
> categoria (Utilidade é mais barata que Marketing), e há uma franquia mensal
> de conversas de serviço. Os valores mudam: confira a tabela de preços do
> Brasil no painel da Meta antes de estimar o orçamento da edição.

---

## O que o sistema registra

Toda tentativa vira uma linha em `envios_cartao` — **inclusive as que falham**.
Sem isso ninguém descobre que o número de um padrinho está errado, nem dá para
saber quem ficou sem receber.

Na tela, cada criança apadrinhada mostra `cartão enviado` ou `envio falhou`, e
o botão vira **"Reenviar"** depois do primeiro envio. Reenviar acrescenta uma
linha nova; não apaga a anterior.

Erros da Meta chegam traduzidos, não como código: token recusado, template não
aprovado, número sem WhatsApp e fora da janela de 24h têm mensagem própria.

---

## Como colocar a arte definitiva

O sistema **não desenha a arte** — ele só escreve os quatro campos por cima do
template que você fizer. Trocar a arte do ano que vem é trocar um PNG, não
mexer em código.

### 1. Exporte o template

Um **PNG** sem os textos variáveis — só a arte: fundo, mascote, moldura,
"obrigado por apadrinhar", o que for. Deixe vazio o espaço onde entram o nome,
o código, a instituição e a data.

Tamanho sugerido: **1080 × 1350** (o formato que o WhatsApp entrega sem
recomprimir demais). Qualquer tamanho serve, desde que o `layout.json` use as
coordenadas desse tamanho.

### 2. Coloque o arquivo no servidor

Em `ARQUIVOS_DIR` (fora das pastas públicas — nada aqui é servido direto):

```
arquivos/agradecimento/SERRA/2026/template.png   ← só para essa edição
arquivos/agradecimento/template.png              ← para todas as edições
```

Vale o primeiro que existir, nessa ordem. Sem nenhum dos dois, o sistema
desenha um cartão simples com as cores da marca — ele existe só para a
funcionalidade rodar antes de o design ficar pronto.

### 3. Diga onde cada texto entra

Um `layout.json` **ao lado do template**:

```json
{
  "campos": {
    "nome":        { "x": 540, "y": 560,  "tamanho": 76, "fonte": "extrabold",
                     "cor": "#153377", "ancora": "ma", "largura_max": 900 },
    "codigo":      { "x": 540, "y": 670,  "tamanho": 34, "fonte": "extrabold",
                     "cor": "#ffb000", "ancora": "ma", "maiusculas": true },
    "instituicao": { "x": 540, "y": 860,  "tamanho": 40, "fonte": "bold",
                     "cor": "#153377", "ancora": "ma", "largura_max": 880 },
    "dia":         { "x": 540, "y": 1030, "tamanho": 48, "fonte": "extrabold",
                     "cor": "#153377", "ancora": "ma", "largura_max": 880 }
  }
}
```

| Chave | O que é |
| --- | --- |
| `x`, `y` | Pixels **do template**, a partir do canto superior esquerdo. |
| `ancora` | `"ma"` = x é o **meio** do texto (centralizado). `"la"` = x é a borda esquerda. |
| `tamanho` | Corpo da fonte em px. |
| `fonte` | `regular`, `bold` ou `extrabold` — Typold, a fonte da marca. |
| `cor` | Hex. |
| `maiusculas` | `true` põe o texto em CAIXA ALTA. |
| `largura_max` | O texto **encolhe** até caber nessa largura. |
| `prefixo` | Texto fixo antes do valor, ex.: `"Código "`. |

Campo que você não listar simplesmente não é escrito — útil se a arte já
trouxer, por exemplo, a instituição impressa.

**`largura_max` importa.** "Escola Municipal Professora Maria das Dores" é o
tipo de nome que as instituições têm de verdade; sem o limite ele atravessa a
arte inteira. A fonte encolhe até 60% do tamanho pedido e para por aí — abaixo
disso fica ilegível, e é melhor transbordar de leve do que entregar algo que
ninguém lê.

---

## Quem pode baixar

Exige **duas** permissões: `ver_padrinhos` (para alcançar o apadrinhamento) e
`ver_criancas` **na edição da criança**.

A segunda não é burocracia: a tela de Padrinhos mostra de propósito só o
primeiro nome e a idade da criança, e o cartão leva nome completo, código e
instituição. Quem só cuida de padrinhos não passa a ler a ficha da criança por
este caminho.

---

## Onde está no código

| Arquivo | O que faz |
| --- | --- |
| `backend/app/servicos/agradecimento.py` | Monta o PNG: acha o template, lê o layout, escreve os campos. |
| `backend/app/routers/padrinhos.py` | `GET /apadrinhamentos/{id}/agradecimento` |
| `backend/app/recursos/fontes/` | Typold Regular/Bold/ExtraBold, para o PNG sair na fonte da marca. |
| `frontend/src/pages/Padrinhos.jsx` | O botão "Cartão" em cada criança apadrinhada. |
| `frontend/src/services/api.js` | `api.baixar()` — baixa e dispara o "salvar como". |
| `backend/app/servicos/whatsapp.py` | Cloud API: sobe a mídia, manda o template, traduz o erro da Meta. |
| `backend/app/models/apadrinhamento.py` | `EnvioCartao` — uma linha por tentativa de envio. |
| `frontend/src/utils/whatsapp.js` | Link `wa.me` e compartilhamento nativo, para o envio a mão. |
