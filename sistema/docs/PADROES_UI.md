# Padrões de UI do sistema

Convenções de interface do `sistema/frontend`. A [identidade
visual](IDENTIDADE_VISUAL.md) diz **com que cor e tipografia** desenhar; este
documento diz **como montar a tela**.

---

## 1. Modal em vez de mexer no layout

**Sempre que possível, uma ação abre um modal — não um painel que empurra a
página.**

Quem usa o sistema está quase sempre lendo uma tabela: procurando um código,
conferindo uma linha, marcando várias crianças. Um painel que abre no meio da
página desloca tudo o que está abaixo dele; a linha que a pessoa estava olhando
some do lugar, e ela perde a referência. O modal abre por cima, resolve a
tarefa e devolve a tela exatamente como estava.

Vale para: criar e editar registros, confirmar uma ação destrutiva, ver a ficha
de alguém, mostrar um link gerado.

Use `components/feedback/Modal.jsx`, que já cuida de:

- foco no primeiro campo ao abrir (ou no botão de fechar, se for só leitura);
- `Esc` e clique no fundo para fechar;
- rolagem do fundo travada enquanto está aberto;
- `role="dialog"` e `aria-modal`.

```jsx
{formAberto && (
  <Modal titulo="Nova criança" aoFechar={() => !salvando && definirFormAberto(false)}>
    <form onSubmit={salvar}>
      <div className="linha-campos">{/* campos */}</div>
      <div className="barra-acoes barra-acoes--fim">
        <Button variant="secondary" type="submit" carregando={salvando}>Salvar</Button>
        <Button variant="ghost" onClick={fechar} disabled={salvando}>Cancelar</Button>
      </div>
    </form>
  </Modal>
)}
```

Enquanto salva, `aoFechar` não fecha: a pessoa não perde o que digitou por um
`Esc` sem querer.

### Dois tamanhos, e a escolha é sobre o conteúdo

**Um modal nunca muda de tamanho conforme o conteúdo cresce.** Se a altura
acompanha, a janela pula embaixo do ponteiro a cada ação, e o botão que a
pessoa ia clicar em seguida não está mais onde estava. Numa ficha com doze
crianças e três ações cada, isso acontece a cada clique.

| `tamanho` | Quando | Comportamento |
| --- | --- | --- |
| `padrao` (omitido) | **Formulário.** O conteúdo é fixo: N campos, sempre os mesmos. | 440px de largura, altura acompanha até 85vh. |
| `grande` | **Ficha.** O conteúdo varia e muda com a janela aberta — apadrinhar mais uma criança, desfazer outra, uma lista de 1 ou de 15. | 720px × `min(86vh, 820px)`, **fixo**. O corpo rola. |
| `largo` | **Visualizador.** Largo como a ficha, mas nada ali muda enquanto está aberto — o cartão digitalizado é o caso. | 720px de largura, altura do conteúdo até 85vh. |

```jsx
<Modal rotulo="Nome do padrinho:" titulo={padrinho.nome} tamanho="grande" aoFechar={fechar}>
```

**Ficha leva `rotulo`.** O título de uma ficha é um nome próprio solto, e nome
próprio sozinho não diz de que ele é nome — "Fernanda Studart Girão" pode ser a
madrinha ou a criança. O `rotulo` é um eyebrow acima do título ("Nome do
padrinho:", "Nome da criança:").

**Os dados da ficha vão em duas colunas** (`ficha--duas`): cinco campos
empilhados custavam cinco faixas de altura antes da lista começar; em duas
colunas custam três. Texto corrido (observações) usa `ficha__dt-largo` /
`ficha__dd-largo` e ocupa a faixa inteira.

**Uma ficha com mais de um modo usa abas, não painéis que abrem.** Ver § 5.

A moldura fixa é deliberada mesmo quando sobra espaço: um padrinho sem nenhuma
criança abre a mesma janela de um com quinze. Ficha é lugar de voltar, e voltar
ao mesmo lugar vale mais que economizar pixel.

**`largo` existe porque a regra é sobre conteúdo que MUDA, não sobre tamanho.**
Uma imagem parada não cresce debaixo do ponteiro, então travar a altura dela só
deixaria vão embaixo. E a imagem leva `max-height: calc(85vh - 265px)` — os
265px são o topo da janela, o respiro do corpo e a lista de dados abaixo. É o
que faz um cartão fotografado **em pé** caber inteiro sem rolagem; deitado,
quem limita é a largura.

Mecanicamente: `.modal__corpo` é `flex: 1` com **`min-height: 0`** — sem isso o
item flex não encolhe abaixo do conteúdo e quem rolaria seria a página atrás,
não o corpo da janela. `.modal__rodape` é `flex: none` e fica ancorado embaixo.

**As exceções** — quando o painel na página é melhor que o modal:

- **Um fluxo de página inteira**, com etapas e conferência longa: a importação
  de listas troca a página toda (`ImportarLista`), porque a prévia tem dezenas
  de linhas e não cabe numa janela.
- **Um painel que é o resultado de uma seleção na própria tabela**, e que
  precisa continuar visível enquanto se marca mais linhas: a barra de "N
  criança(s) marcada(s)" em Kits.
- **Um bloco de conferência antes de gravar**, ligado ao que está na tela: a
  leitura do cartão em Cartões.

Na dúvida, modal.

---

## 2. Um botão sólido por escopo

**Nenhum botão é amarelo.** O botão cheio é navy (`--color-cta`, que aponta para
`--color-primary`) com texto branco — 11,9:1. O amarelo saiu dos botões: amarelo
de fundo obriga texto escuro por cima, e texto azul sobre amarelo são duas cores
saturadas brigando na mesma pílula. O amarelo vale mais marcando estado na
planilha do que pintando botão.

A hierarquia agora é **cheio vs. contorno**, e a regra é de escopo: um botão
cheio por escopo. A página tem o seu; o modal que ela abre tem o dele.

| Papel | Variante | Quando |
| --- | --- | --- |
| CTA da página | `primary` (padrão) | A ação principal. **Um por tela.** Navy cheio. |
| Confirmar dentro de painel/modal | `secondary` | `Salvar`, `Criar`, `Confirmar…` Navy cheio, mas dentro da janela. |
| Tudo o mais | `ghost` | Filtrar, paginar, cancelar, editar, ativar/desativar. Contorno navy. |

`primary` e `secondary` têm hoje o **mesmo visual**. Isso é intencional e não é
duplicação a limpar: os nomes marcam escopos que nunca aparecem juntos (o modal
cobre a página), e manter os dois deixa a intenção legível no JSX e permite
separá-los depois sem varrer 58 chamadas.

O CTA é normalmente o botão que **abre** o fluxo principal (`Nova criança`,
`Novo padrinho`, `Registrar pagamento`). O `Salvar` do modal que ele abre é
`secondary`: é o botão dominante da janela, e o CTA que ficou atrás está coberto
pelo overlay.

Páginas com dois `primary` no código são aceitáveis **só** quando os dois estão
em estados mutuamente exclusivos e nunca aparecem juntos — as etapas de
`ImportarLista`, o antes/depois da leitura em `Cartões`, o formulário e a tela
de sucesso em `DefinirSenha`.

Telas sem CTA (Painel, Check-in de uma ação só) simplesmente não têm botão
cheio — isso é normal, e melhor do que promover algo que não é o principal.

### Ação repetida por linha vira ícone

Botão com texto é para ação que aparece **uma vez** na tela. Assim que a mesma
ação se repete por linha — o olho de cada criança, as três ações de cada
apadrinhamento — a palavra custa mais do que informa: são quinze vezes
"Cartão", "WhatsApp" e "Desfazer" numa ficha, e o texto empurra tudo para
baixo sem dizer nada novo a partir da segunda vez.

Use `components/core/BotaoIcone.jsx` com um ícone de `components/core/icones.jsx`:

```jsx
<span className="acoes-icone">
  <BotaoIcone tamanho="sm" titulo={`Ver ficha de ${c.nome}`} onClick={abrir}>
    <Olho />
  </BotaoIcone>
  <BotaoIcone tamanho="sm" perigo titulo={`Remover ${c.nome}`} onClick={remover}>
    <Xis />
  </BotaoIcone>
</span>
```

Regras:

- **`titulo` é obrigatório** e leva o nome do registro junto (`Ver ficha de
  Ana`, não `Ver`). Ele vira o `title` (dica do mouse) e o `aria-label` — o
  rótulo não sumiu, mudou de lugar.
- `tamanho="sm"` (24px) na planilha, o padrão (28px) na ficha.
- `perigo` só para desfazer e remover: apenas o hover muda, para vermelho.
- `carregando` troca o ícone por uma roda **do mesmo tamanho**, para a fila de
  ações não mudar de largura no meio do clique.
- Os ícones são SVG escritos à mão, na grade de 24 com traço de 2 e
  `currentColor` — não há fonte de ícones nem biblioteca, e a cor vem do botão.

Os tamanhos de `Button` seguem a mesma lógica de densidade: `sm` é **32px**, o
botão de dentro (rodapé de modal, bloco de ficha, paginação). Dentro de
`.barra-acoes` ele volta aos 40px, porque ali divide a linha com campos de
40px e precisa alinhar com eles.

### Onde o amarelo vive agora

Só em **elemento**, nunca em tipo:

| Token | Uso |
| --- | --- |
| `--color-destaque` (`amarelo-500`) | ponto de alerta na aba, barra de progresso, roda do spinner |
| `--surface-destaque` (`amarelo-100`) | fundo de aviso, etiqueta de espera, painel em destaque |
| `--border-destaque` (`amarelo-300`) | borda desses mesmos blocos |
| `--focus-ring-dark` | anel de foco **sobre a lateral navy** |
| `star-mascot-amarelo.svg` | o mascote na lateral e na barra mobile |

Não existe token de texto amarelo. O acento de texto é `--text-accent`
(`navy-500`, 6,1:1): é ele que pinta o eyebrow, o primeiro nome da abertura e os
rótulos de seção da ficha.

---

## 3. Barra de ações

`.barra-acoes` é a linha de ferramentas da página: campos e botões lado a lado,
quebrando em várias linhas no celular.

- Campos e botões dentro dela têm **40px de altura** (`--control-h-sm`) e
  ficam alinhados pelas bordas. O `.campo` perde a margem de baixo que carrega
  quando está empilhado num formulário — sem isso, os campos flutuam acima dos
  botões.
- Para jogar algo na **ponta direita** da barra, envolva em
  `.barra-acoes__ponta`. É assim que o CTA fica na mesma linha dos filtros, na
  ponta oposta.
- `.barra-acoes--fim` é a barra de botões no rodapé de um painel ou modal.

```jsx
<form className="barra-acoes" onSubmit={buscar}>
  <Entrada value={busca} onChange={...} placeholder="Buscar por nome" />
  <Button type="submit" size="sm" variant="ghost">Buscar</Button>
  <span className="campo__dica">{total} nesta aba</span>

  <div className="barra-acoes__ponta">
    <Button size="sm" onClick={abrirNova}>Nova criança</Button>
  </div>
</form>
```

---

## 4. Lista de um-para-muitos: corta em uma linha, age na ficha

Quando uma linha da planilha tem uma coleção do outro lado — um padrinho com
dez, quinze crianças — a tentação é listar tudo na célula com os botões de cada
item. Não funciona: quinze crianças × três ações davam **quarenta e cinco
botões numa linha só**, e a altura da linha passava a depender do dado.

A regra é separar o que a célula faz do que a ficha faz:

| | Célula da planilha | Ficha (o olho) |
| --- | --- | --- |
| Mostra | primeiro nome + um marcador | nome, etiquetas e ações |
| Quantos | o que couber em **1 linha**, resto vira `…` | todos, em lista rolável |
| Ações | **nenhuma** | três ícones, na mesma linha do nome |

Na prática:

- `.vinculos` é a célula: `-webkit-line-clamp: 1` com `line-height` **fixo** e
  maior que a altura do marcador. Se um chip esticar a linha real além do
  `line-height`, o corte erra a conta e vaza uma fatia da linha seguinte.
- **Uma linha por registro, não duas.** A planilha é para varrer de cima a
  baixo comparando padrinhos, e linha de altura variável quebra essa leitura:
  o olho perde a régua. Quem precisa da lista toda abre a ficha.
- Uma coluna estreita ao lado carrega a **contagem** (`Nº`), porque uma linha
  cortada não distingue 12 de 25.
- A coluna solta do `<colgroup>` é a da lista, não a do nome: cada nome a mais
  que couber é uma ida a menos à ficha.
- O `title` da célula traz a lista inteira, para quem quer só espiar.
- **Dentro da ficha, criança é sempre `código + nome completo`** — nas três
  abas. É pelo código que se casa a linha da ficha com a linha da planilha, e
  primeiro nome sozinho não distingue duas Anas. O código vai na frente, em
  tinta discreta (`.ficha__linha-codigo`): identifica sem competir com o nome.

  O `crianca_primeiro_nome` continua existindo no schema e continua sendo o
  que vai para o **padrinho** — é o que o cartão de agradecimento usa. Os
  campos novos (`crianca_codigo`, `crianca_nome`) são para quem opera o
  sistema, e não alargam acesso: todo perfil que tem `ver_padrinhos` também
  tem `ver_criancas`, e essa saída só existe atrás dessas rotas.
### Na ficha, a coleção é lista — não são caixas

Vinte e cinco crianças em caixas com borda, raio e respiro viram rolagem sem
fim. Há duas formas, e a escolha é pela **quantidade**:

| Classe | Quando | Forma |
| --- | --- | --- |
| `.ficha__vinculo` | Poucos itens **com detalhe** — os ≤ 2 padrinhos na ficha da criança, com contato embaixo. | Caixa com borda. |
| `.ficha__lista` + `.ficha__linha` | Coleção que pode ser grande — as crianças na ficha do padrinho. | Uma faixa de 56px+, separada por filete. Sem caixa, sem raio. |

Uma `.ficha__linha` tem duas colunas: `-corpo` (`flex: 1`) à esquerda e
`-acoes` (`flex: none`) à direita. Dentro do corpo, **as etiquetas empilham
ACIMA do nome** — não ao lado das ações.

Por que não ao lado das ações: encostada nos ícones, a etiqueta lê como
legenda dos botões. "CESTA" colado num ícone de download parece o rótulo
daquele ícone, não o estado da criança.

Por que acima e não abaixo: o estado é o **filtro** com que se varre a lista
("o que falta pagar?"), e o nome é a confirmação de *qual* é. Quem varre lê a
primeira linha de cada bloco; quem procura um nome lê a segunda.

Os valores por item saíram da linha: com vinte crianças, vinte vezes
`R$ 120,00` é ruído — o total combinado e o pago já estão no `<dl>` acima.

Este é o lugar onde a densidade **não** vale a pena. Na planilha cada linha é
um registro que se compara com o de cima; aqui cada linha é uma criança sobre
a qual se vai agir, e três alvos de clique de 28px precisam de espaço em volta
para não virar erro. Daí os 56px de mínimo e o respiro de `--space-3`.

### Formulário dentro da ficha é barra, não painel

Com título, parágrafo de dica e campos rotulados, o formulário de apadrinhar
ocupava metade da janela **antes de alguém digitar qualquer coisa**, e empurrava
a lista de crianças para fora da tela.

`.ficha__acao` é uma barra de uma linha: os rótulos viram `placeholder` (com
`aria-label`, porque `placeholder` não nomeia campo para leitor de tela),
controles de 34px, e os botões na mesma faixa. Ela quebra sozinha se faltar
largura. Só o campo marcado com `campo--cresce` estica — os outros são
`flex: none`, senão o select encolhe até sumir atrás da própria seta.

**O olho não depende de permissão de escrita.** Em `Crianças` ele abre um
detalhe que a linha já resume, então segue o `podeEditar`. Em `Padrinhos` ele é
o único caminho para a lista completa — quem só tem `ver_padrinhos` precisa
dele igual.

A ficha guarda o **id**, não o objeto: ela lê sempre a linha que está na lista,
e devolve o registro atualizado pelo `aoMudar`. Assim a janela e a planilha
atrás nunca divergem, e nenhuma mudança recarrega a tabela inteira — quem
estava no meio da planilha não perde o lugar.

---

## 5. Nada aparece do nada: aba em vez de painel que abre

**Apertar um botão não pode mudar de lugar o que a pessoa está lendo.**

A ficha do padrinho tem três modos — ver as crianças, apadrinhar mais uma,
registrar um pagamento. A primeira versão resolvia isso com botões que
inseriam um painel entre o título e a lista. Cada clique empurrava a lista para
baixo, e o painel de pagamento (total, campos, comprovante e vinte caixas de
marcar) empurrava muito. Era o mesmo defeito do modal que cresce com o
conteúdo, dentro do modal que não cresce.

A forma certa é a **faixa de abas** (`.abas` + `.abas--ficha`), o mesmo
componente das instituições em Crianças:

- **Aba é aba, não pílula clicável.** As três dividem a largura do container,
  sem caixa nem raio, e a escolhida é marcada por um traço de 3px embaixo. A
  pílula lia como botão — e botão promete que algo vai *acontecer*, enquanto
  aba promete que algo vai *trocar*. (Na página de Crianças as instituições
  seguem em pílula: lá são vinte e poucas, roláveis na horizontal, e nenhuma
  divide largura com as outras.)
- O traço nasce **transparente** na aba inativa, não ausente: assim escolher
  uma aba não muda a altura da faixa.
- A faixa fica **sempre no mesmo ponto**. Só o que está abaixo dela troca.
- A faixa **gruda no topo** da área que rola (`position: sticky`): a lista pode
  ter vinte e cinco linhas, e ter de rolar de volta até em cima só para trocar
  de aba seria o mesmo defeito por outro caminho.
- A **contagem vive no rótulo** (`aba__contagem`): "12 apadrinhada(s)", "7 a
  pagar", "tudo quitado". É o que diz se vale a pena entrar na aba.
- Aba que a permissão não alcança **não existe** — `Apadrinhar` pede
  `editar_padrinhos`, `Pagamento` pede `registrar_pagamentos`. Com uma aba só,
  a faixa não aparece.
- Terminada a ação, volta-se para a **lista**: é de lá que se olha o resultado.
- Um estado vazio ("tudo quitado") é **conteúdo da aba**, não motivo para
  sumir com ela: sumir mudaria o tamanho da faixa, que é o que as abas vieram
  resolver.

### A mesma faixa serve à página com dois livros

`Financeiro` tem duas abas — **Saídas** e **Recebimentos** — e usa a faixa em
pílula da página (`.abas`), a mesma das instituições em Crianças, e não a faixa
sublinhada da ficha: aqui não há janela com rolagem própria para grudar em cima,
e a faixa é do conteúdo da página, não de um modal.

Três coisas que essa tela resolve com a mesma regra de sempre:

- **A conta fica ACIMA da faixa.** Recebido, Saídas e Saldo são a resposta que a
  coordenação vem buscar, e não mudam quando se troca de aba — se estivessem
  dentro de uma delas, trocar de aba pareceria trocar de número.
- **A contagem de cada aba é o total em dinheiro**, não a quantidade de linhas:
  é o que diz se vale a pena entrar. Dez lançamentos de R$ 20 e um de R$ 8.000
  são a mesma contagem e nada parecidos.
- **Aba que a permissão não alcança não existe** — e com uma só, a faixa não
  aparece (§ 5). Quem cuida da estrutura lança o que gastou sem descobrir que
  existe uma metade do caixa que ele não vê. O CTA acompanha a aba aberta
  (`Nova saída` / `Novo recebimento`): dois `primary` no código, nunca os dois
  na tela.

### Uma lista de duas origens continua sendo uma lista

A aba Recebimentos mostra numa tabela só o que vem de duas tabelas: os
pagamentos dos padrinhos e os recebimentos soltos. Quem fecha o caixa quer ver
todo o dinheiro que entrou de uma vez — duas tabelas empilhadas na mesma tela
seriam o mesmo trabalho de antes, com mais rolagem.

O que isso exige da tela:

- **Cada linha diz de onde veio** (`fonte`), e é isso que decide em qual rota a
  ação dela bate. Conferir, subir comprovante e remover são a mesma ação para
  quem olha, e endereços diferentes por baixo — um mapa de rotas por origem
  (`rotas(linha)`) resolve isso num lugar, em vez de um `if` dentro de cada
  handler.
- **A chave do React é `fonte + id`**, nunca o id sozinho: os ids vêm de tabelas
  diferentes e colidem. Com a chave errada, subir o comprovante de uma linha
  pisca o estado de outra.
- **As colunas são o denominador comum.** O que só existe numa das origens (os
  apadrinhamentos que o pagamento quita, as observações da doação) vira texto na
  coluna que ambas têm — a descrição — ou a dica do mouse. Coluna que só
  preenche em metade das linhas é coluna que mente na outra metade.
- **Filtro corta a lista; total, nunca.** Os números do alto respondem "qual é o
  caixa da edição", e um caixa que muda quando se filtra a tela não é caixa
  nenhum. Quando o filtro (ou o teto de linhas) deixou coisa de fora, a barra
  diz quantas existem e quantas estão à vista.

### Botão não muda de função debaixo do ponteiro

Irmão da mesma regra. Na primeira versão do apadrinhar, achada a criança o
botão **"Procurar" virava "Confirmar"** — mesmo lugar, mesma cor, outra
consequência. Quem clicasse duas vezes seguidas confirmava um vínculo sem ter
lido o nome.

Agora "Procurar" fica onde está, sempre, e **o "Confirmar" nasce ao lado do
nome da criança** — que é justamente o que se precisa ler antes de confirmar.
Um botão por linha de resultado, e um "Confirmar todas (N)" no cabeçalho
quando há mais de um pendente.

A busca aceita **vários códigos de uma vez** (`SL03, SL04, SL06`), separados
por vírgula, espaço ou ponto-e-vírgula — é assim que a lista chega, colada de
uma planilha. Cada código vira uma consulta própria, em paralelo, porque a
busca por código é o *escape* que alcança qualquer instituição das edições do
usuário e **cada uma tem de ficar registrada em log**: uma busca, uma linha.
Daí também o teto de 20 por vez — colar duzentos códigos não pode virar
duzentas consultas de uma tacada.

Já a confirmação em lote roda **em série**, não em paralelo: cada `POST
/apadrinhamentos` devolve o padrinho inteiro, e dispará-los juntos faria
respostas fora de ordem sobrescreverem umas às outras — a última a chegar
apagaria as anteriores da tela.

Código não encontrado não some nem vira erro de tela inteira: fica na lista,
em itálico, com a etiqueta `não encontrada`. Quem colou cinco códigos precisa
ver **qual** dos cinco falhou.

### O amarelo saiu junto

Aqueles painéis tinham fundo `--surface-destaque` para marcar *"isto apareceu
agora"*. Com abas, nada aparece do nada — e o fundo perdeu a função. Some
também um problema que ele já tinha: amarelo em área grande contraria a regra
do próprio DS (§ 2), e um bloco de vinte linhas é área grande.

O que sobrou de tinta é o cabeçalho do pagamento, em `--surface-card-alt`
(creme neutro), agrupando o total que se confere contra o comprovante. A aba
ativa, em navy, já diz onde se está.

---

## 6. Valor derivado, nunca digitado duas vezes

O painel de **registrar pagamento** na ficha do padrinho não tem campo de
valor. A soma vem do que foi marcado: cada apadrinhamento já carrega o próprio
`valor` (cesta e festa custam diferente, e o preço vem da edição da criança).

Pedir o valor de novo criaria duas verdades sobre o mesmo dinheiro — o que a
base diz que foi quitado e o que o pagamento diz que custou — e nada garantiria
que batem. O total cresce conforme se marca, e o resumo é escrito como o
comissário fala: **"5 cestas + 2 festas"**.

Pagamento de valor diferente da soma (desconto, arredondamento) tem campo de
valor no formulário do **Financeiro** (aba Recebimentos), que o aceita solto. A
ficha cobre o caso normal.

### A aba lê na ordem da tarefa, e a confirmação gruda no pé

A primeira versão desta aba punha **total, data, forma e os dois botões numa
linha só, no alto**. A ideia era boa — com vinte crianças para marcar, um botão
no pé da lista fica longe de onde a pessoa está olhando — mas o resultado juntava
cinco coisas sem relação entre si, sem rótulo visível (data e forma tinham só
`aria-label`), e abria a aba com um **total grande antes de existir qualquer
marcação**: um número morto, que só dizia `R$ 0,00`. E os botões apareciam
*acima* dos campos que eles gravam.

A forma atual é uma coluna só, na ordem em que a tarefa acontece:

| | Bloco | Por quê nessa posição |
| --- | --- | --- |
| 1 | **O que este pagamento quita** — a lista de marcar | é a decisão, e é dela que o valor sai. Perguntar data e forma antes é pedir o detalhe de um pagamento que ainda não existe |
| 2 | **Como o dinheiro chegou** — data, forma, comprovante, observação | campos com rótulo de verdade, um assunto por bloco |
| 3 | **Pagamentos deste padrinho** — o histórico | conferir o passado é outra coisa; vem depois, atrás de um filete |
| — | **Barra de confirmação** | `position: sticky; bottom: 0` |

A barra grudada no pé resolve o motivo original (o botão longe do olho) **sem
inverter a leitura**: o total e o `Registrar` seguem a rolagem e estão sempre à
vista, e o número — que é o que se confere contra o comprovante na mão — continua
sendo o maior texto dali.

Dois cuidados que ela exige:

- **A barra diz o que falta.** `Marque o que este dinheiro quita.` →
  `Escolha o comprovante para poder registrar.` O texto e o `disabled` saem da
  mesma variável, então não há como um dizer uma coisa e o outro dizer outra.
  Botão inativo sem explicação faz a pessoa procurar o defeito na tela.
- **Nada de margem negativa para sangrar a largura.** O corpo do modal é
  `overflow-y: auto`, e o CSS força o outro eixo a `auto` junto: um filho mais
  largo que o conteúdo viraria barra de rolagem horizontal (é a mesma armadilha
  documentada em `.abas--ficha`).

Um detalhe que custou um bug: **`.ficha__secao` carrega margem vertical, e
margem vertical não se aplica a `span`.** O rótulo de seção é `div` — como em
`FichaCrianca` — senão o respiro que a classe promete simplesmente não acontece,
sem erro nenhum para avisar.

### Escolher arquivo é um controle, não um `input` solto

Um `input[type=file]` cru não diz de que ele é: o navegador escreve "Choose
file" e o resto da linha fica vazio. `.arquivo` embrulha o input num bloco que é
todo o alvo do clique, com rótulo próprio, e que **muda de estado quando o
arquivo entra** — borda tracejada e a etiqueta `obrigatório` no vazio; borda
inteira, visto e o nome do arquivo no cheio.

A diferença de *traço* (tracejado → inteiro) é o que se vê de canto de olho, sem
depender da cor. A palavra "obrigatório" está escrita em vez de um asterisco:
asterisco é convenção que exige legenda, e aqui há uma única exigência na tela.
O input fica escondido em posição absoluta, mas alcançável pelo teclado — quem
clica abre pelo `label`, quem chega pelo Tab foca o input e abre com Enter.

### Mais três detalhes que a forma resolve

- **A lista rola junto com a janela**, não por dentro. Rolagem dentro de
  rolagem é armadilha de ponteiro — e é também por isso que a barra de
  confirmação é `sticky` em vez de a lista ter rolagem própria.
- **O comprovante sobe numa requisição separada** (`POST
  /pagamentos/{id}/comprovante`, ou `/recebimentos/{id}/comprovante` para uma
  doação), depois do lançamento do dinheiro. A quitação é a parte que não pode
  falhar: misturar o upload nela faria um arquivo grande demais derrubar o
  vínculo junto. Se o upload falha, a tela diz que o dinheiro foi gravado e que
  só o arquivo faltou — e a linha fica com a etiqueta `falta` até ele vir.
- **A observação é uma caixa de texto, não um campo de uma linha.** O que se
  escreve ali é frase ("pagou 200 e pediu para descontar da festa da irmã"), e
  num `input` a pessoa perde de vista o começo do que escreveu. `AreaTexto` tem
  altura fixa em linhas, e não crescendo com o texto: um campo que estica
  empurra o botão de salvar para baixo enquanto se digita.

O arquivo é aceito só como JPG, PNG ou PDF, fica fora das pastas do frontend e
só sai por rota autenticada. Trocar o comprovante apaga o anterior do disco, e
apagar o pagamento apaga o arquivo — senão sobra arquivo que ninguém mais
alcança.

### O botão de registrar espera o comprovante

**Pagamento de padrinho não se registra sem arquivo.** O botão fica inativo até
escolherem um, nos dois lugares onde se registra: a aba Pagamento da ficha e o
formulário do Financeiro. Sem comprovante, ninguém confere depois se aquele
valor chegou de verdade — a linha seria uma promessa, e quem for conferir não
tem contra o que comparar.

Isso **não** vale para doação e "outros": dinheiro que alguém deixa na caixinha
às vezes não tem recibo nenhum, e recusar o lançamento faria a edição perder o
registro do dinheiro em vez de ganhar a prova dele.

A exigência é **da tela, não do servidor**, e isso é deliberado. O arquivo sobe
na segunda requisição, e se ela falhar o dinheiro já está gravado — recusar o
pagamento nesse ponto perderia a quitação por causa do arquivo, que é
exatamente o que a separação em duas requisições existe para evitar. Além disso
pagamentos antigos existem sem comprovante, e uma regra retroativa no servidor
os tornaria impossíveis de editar. Quem ficou sem arquivo aparece com a etiqueta
`falta`, na ficha e no Financeiro, e o arquivo entra depois.

### Conferir o passado é outro bloco, não outra tela

O histórico (bloco 3 da tabela acima) fica na mesma aba porque a pergunta "ele
já pagou isso?" nasce no mesmo lugar em que se registra o pagamento: mandar a
pessoa a outra tela para responder significaria fechar a ficha, perder o lugar
na planilha e voltar.

O filete e o respiro generoso entre os dois existem para não parecerem a mesma
lista — em cima se marca o que **vai** ser pago, embaixo se confere o que **já**
foi. Cada linha do histórico traz valor, data, forma, a observação e o
comprovante para baixar ou trocar, mais as etiquetas de conferido e de
`falta o comprovante`.

---

## 7. Riscado em vez de apagado

Quando alguém **sai** de uma lista mas o histórico dela continua importando,
a linha fica **riscada na planilha, não sumida**. É o caso da criança que
desistiu de ir ao evento: o kit, os cartões e o padrinho dela já existem, e
alguém ainda vai ter de decidir o que fazer com cada um — se o nome some da
tela, essa decisão some junto.

No banco, isso é um par `*_em` / `*_por` anulável (como `checkin_em` /
`checkin_por`), nunca um `DELETE`. Desmarcar é limpar os dois campos: a pessoa
pode mudar de ideia até a véspera.

Na tela: `.planilha__linha--desistiu` risca a linha inteira **menos a coluna de
ações** — senão o botão de desfazer some junto com o resto. A ação de marcar e
desmarcar fica no rodapé do modal da ficha, não como mais um ícone na linha:
tem consequência demais para um clique solto numa tabela densa.

`DELETE` continua existindo, para o caso diferente — a linha que entrou errada
e nunca deveria ter existido.

---

## 8. Duas vozes tipográficas

**Typold é a voz da interface. Aleo é a voz da leitura.** Os papéis não se
misturam — é a regra 1 do DS que serve de base para este sistema.

| Onde | Família | Como |
| --- | --- | --- |
| Títulos, botões, labels, números, células de tabela | `--font-body` (Typold) | peso 800 em UI, `letter-spacing: var(--tracking-titulo)` nos títulos |
| Lede, mensagens, enunciados, parágrafo longo | `--font-serif` (Aleo) | peso 400, `line-height` 1.6–1.65, `text-wrap: pretty` |

Aleo **nunca** recebe tracking negativo, e título **nunca** é serifado. O
negrito dentro de um parágrafo Aleo para em 700, que é o topo da família.

Aleo é variável: um arquivo de 36 KB cobre 300–700, auto-hospedado em
`public/fonts/` e importado em `tokens.css` antes de qualquer outro CSS.

---

## 9. Alturas de controle

O DS de origem usa 56px como altura base de botão. Aqui o padrão é **48px**, e
a barra de ações usa **40px**: este é um sistema de planilha, e 56px em cada
linha de filtro comeria a altura útil da tela. O 56 (`--control-h-lg`) fica
para o CTA grande, onde o DS quer presença.

| Token | Valor | Onde |
| --- | --- | --- |
| `--control-h-sm` | 40px | barra de ações, `Button size="sm"` |
| `--control-h` | 48px | campos de formulário, `Button` padrão |
| `--control-h-lg` | 56px | CTA grande (`Button size="lg"`) |

Todo botão afunda para `scale(0.97)` no `:active` e ganha `--shadow-focus` no
`:focus-visible`. Por isso o `Button` usa classe CSS e não `style` inline:
com inline não existe `:active` nem `:focus-visible`.

---

## 10. Contraste é parte do token

Duas cores foram escurecidas porque reprovavam no WCAG AA, e o motivo fica
registrado no próprio `tokens.css`:

- `--color-accent` era amarelo (`amber-700`, 2,9:1 sobre branco; depois
  `amber-900`, 5,3:1). O token **deixou de existir**: amarelo não pinta texto,
  nem escurecido. O acento de texto é `--text-accent` = `navy-500`, **6,1:1**.
- `--text-on-light-muted` era `#7c86a0` — **3,6:1**, reprovado nos 12px da dica
  e do rodapé. Passou para `#697188`, **4,9:1**.
- O anel de foco global era `amber-500` sobre branco: **1,6:1**, contra os 3:1
  que o WCAG 2.2 exige de indicador de foco — na prática, invisível. Passou a
  navy (`--focus-ring`, 11,9:1). Sobre a lateral navy o amarelo volta
  (`--focus-ring-dark`), e ali ele dá **7,4:1**.

---

## 11. Shell: layout Sidebar

Com 11 destinos, este sistema usa o layout de **Sidebar**: navegação vertical
fixa de 256px em `--navy-700`, marca no topo, usuário na base, e **nenhum
cabeçalho** no topo da página.

- Item ativo em **branco a 16%** — navy sobre navy sumiria.
- `Sair` é um ícone discreto na base — o peso visual da lateral é do item ativo.
- O usuário aparece como bolinha com as iniciais + nome e sobrenome.
- A home abre com o **card de abertura** (`.abertura`): saudação pelo primeiro
  nome, contexto em chips. Só na home; as telas internas abrem com título e
  ações em linha.
- Abaixo de 960px a lateral vira gaveta e uma barra fina de 56px aparece só
  para dar de onde abri-la.

**Desvio consciente do DS de origem:** ele recolhe a sidebar para um trilho de
80px só com ícones entre 960 e 1279px. Aqui ela segue inteira até 960px — os
11 destinos são só texto, e o trilho exigiria um jogo de ícones que este
sistema ainda não tem. Quando existirem os ícones, o trilho entra.
