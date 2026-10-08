# Lembrete do evento

Na semana do evento, cada padrinho recebe uma mensagem lembrando o dia e
convidando para estar lá, com **os cartões que as crianças dele escreveram**.
Hoje isso é feito à mão: padrinho por padrinho, caçando o cartão de cada
criança. O sistema já sabe o caminho inteiro —
padrinho → apadrinhamento → criança → cartão do mesmo tipo — e monta a lista
sozinho.

Onde fica: **Padrinhos → "Ir para envio de cartões"**
(`/acesso/padrinhos/envio-de-cartoes`).

---

## Uma mensagem por dia do evento

**A regra que organiza tudo:** o lembrete é um convite para **um dia**. Cada
criança vai a um dia só (o da instituição dela), então:

- quem apadrinhou crianças de **um dia** recebe **uma** mensagem;
- quem apadrinhou crianças de **dois dias** recebe **duas** — uma para cada
  dia, cada uma levando **só os cartões das crianças daquele dia**.

Por isso a tela é separada por abas de dia, e o mesmo padrinho pode aparecer
nas duas. A etiqueta **"recebe 2 mensagens"** marca quem está nesse caso.

O texto da mensagem diz de que dia ela fala e explica por que pode chegar
outra — é o que faz o padrinho que recebe duas entender que os cartões de uma
são de um dia e os da outra, do outro.

## Quem fica pronto

Cada padrinho, em cada dia, cai numa de três situações:

| Situação | Quando | Sai? |
| --- | --- | --- |
| **Pronto** | Todos os cartões das crianças dele naquele dia já subiram, e o WhatsApp cadastrado tem cara de telefone | Sim |
| **Sem WhatsApp** | Os cartões estão todos aqui, mas falta o número (ou ele não serve) | Não — corrigir na ficha do padrinho |
| **Em progresso** | Ainda falta cartão subir. A tela mostra **"faltam X de Y"** e o cartão que falta aparece tracejado, com o código da criança | Não — espera os cartões |

**O lembrete só sai completo.** Mandar com dois cartões e depois o terceiro
sozinho seria pior que esperar.

Quem entra na conta:

- **só apadrinhamento pago.** Promessa não recebe cartão — a mesma regra do
  agradecimento (`servicos/apadrinhamento.py`);
- **só criança que não desistiu.** O convite é para vê-la no evento; o cartão
  de quem não vai não entra, e também não segura o envio dos outros;
- **cesta e festa da mesma criança são dois cartões.** A criança escreve um
  para cada padrinho; quem deu os dois recebe os dois.

A criança cuja instituição ainda **não tem dia** cai numa aba à parte,
"Sem dia definido". O lembrete dela não sai até o dia ser definido em
Instituições.

O filtro de instituição mostra o padrinho **inteiro** quando ele tem ao menos
uma criança daquela instituição: o lembrete dele é um só, e mostrar metade dos
cartões enganaria sobre o que vai sair.

## Quem acessa

A coordenação da cidade e a coordenação da captação — quem tem
`enviar_cartoes` **e enxerga a edição inteira**. O comissário tem
`enviar_cartoes`, mas não entra: ele só vê as próprias crianças, e um padrinho
recebe crianças de vários comissários. Visto por ele, o padrinho pareceria
pronto com metade dos cartões — e é justamente essa a pergunta que a tela
responde. A trava é do backend (`routers/lembretes.py`), não só do botão.

## A mensagem

Rascunho do modelo que vai para a aprovação da Meta. O mesmo texto para
todos; o que muda é o nome e o dia:

> Olá, **{{1}}**!
>
> O Natal Lumen está chegando, e queremos muito você com a gente no **{{2}}**.
>
> Os cartões abaixo foram escritos pelas crianças que você apadrinhou e que
> estarão no evento neste dia.
>
> Apadrinhou crianças que vão em outro dia do evento? Você vai receber outra
> mensagem, com os cartões delas.

- `{{1}}` — primeiro nome do padrinho;
- `{{2}}` — o dia por extenso: "sábado, 19 de dezembro".

A última frase vai para todo mundo de propósito: um modelo da Meta não tem
frase condicional, e para quem recebe uma mensagem só ela não atrapalha.

A tela mostra o texto pelos **três pontinhos na aba de cada dia → "Ver mensagem"**, numa janela, já com o dia daquela aba.

**Ainda em aberto:** horário e local do evento, se entram no texto.

## O que falta: o disparo

A tela já mostra quem está pronto, mas o botão **"Enviar aos N prontos"** está
desligado. Ele entra quando o sistema for ligado ao CRM, para a conversa com o
padrinho nascer lá. Decidido até agora:

- o WhatsApp da Lumen está na **API oficial da Meta**: mensagem que nós
  iniciamos só sai por **modelo aprovado**;
- o padrinho recebe **uma mensagem e todos os cartões** do dia. O formato mais
  próximo disso na API oficial é o **carrossel** (até 10 cartões por
  mensagem); a outra opção é um modelo por cartão. Fica decidido junto com o
  CRM, porque depende do que a API dele aceita.

Falta saber: qual é o CRM, se a API dele manda modelo com imagem (e
carrossel), e de quem é a conta do WhatsApp no Gerenciador de Negócios da Meta.
