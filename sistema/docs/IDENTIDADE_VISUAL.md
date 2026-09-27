# Identidade visual — extraída de `site/`

Documento de referência para o sistema em `sistema/frontend`. Tudo aqui foi lido
do site público em `site/` (que está em produção e **não deve ser alterado**) e do
bundle do design system em `_ds/natal-lumen-design-system-*/`.

> Regra do projeto: **nunca importar arquivos de `site/`**. Os arquivos visuais
> necessários (fontes, SVGs, tokens) são **copiados** para `sistema/frontend`.

---

> Este documento é sobre **cor, tipografia e tokens**. Como montar a tela
> (modal x painel, onde vai o CTA, barra de ações) está em
> [PADROES_UI.md](PADROES_UI.md).

## 1. Tecnologia de estilização

**CSS puro com variáveis CSS (custom properties). Não há Tailwind, CSS Modules,
styled-components nem biblioteca de UI.** O `package.json` do site tem apenas
`react` e `react-dom` como dependências.

Existem duas convenções, e ambas devem ser mantidas no sistema:

| Onde | Convenção | Exemplo |
| --- | --- | --- |
| Páginas | CSS global com nomes **BEM**, num arquivo ao lado da página | `src/pages/Home.jsx` + `src/pages/Home.css`, classes `.hero__title`, `.split-section--bordered` |
| Componentes reutilizáveis | **Estilos inline** lendo as variáveis CSS | `Button.jsx`, `SiteFooter.jsx` — `style={{ background: "var(--color-cta)" }}` |

Os tokens ficam em `src/styles/tokens.css`, importado por `src/index.css`:

```css
@import "./styles/tokens.css";
```

Nenhuma cor, tamanho ou fonte é escrita "crua" fora do `tokens.css` — tudo vem de
`var(--...)`. **O sistema deve seguir a mesma disciplina.**

---

## 2. Cores

Paleta completa em `site/src/styles/tokens.css`. Escalas base:

**Navy** (cor dominante da marca)
`--navy-900:#0d2352` · `--navy-800:#122c67` · `--navy-700:#153377` ← principal
`--navy-600:#204490` · `--navy-500:#3a61a5` · `--navy-400:#6688bd`
`--navy-300:#9db2d6` · `--navy-200:#c7d3e9` · `--navy-100:#e6ecf6`

**Amber** (ação/destaque) — **no site**
`--amber-900:#8f6301` · `--amber-800:#b17701` · `--amber-700:#cc8902`
`--amber-600:#e69c00` · `--amber-500:#ffb000` ← principal · `--amber-400:#ffc23d`
`--amber-300:#ffd166` · `--amber-200:#ffe3a3` · `--amber-100:#fff3d6`

> ⚠️ **O sistema divergiu aqui.** O amber do site está em matiz **40–41°**: é
> laranja-âmbar, não o amarelo da logo. (O filtro que o site aplica ao mascote,
> `invert(69%) sepia(84%) saturate(1000%)`, renderiza `#ffa800` — matiz 40°,
> ainda mais laranja.) No `sistema/` a escala foi refeita em matiz **46°**, que
> lê como amarelo de verdade sem perder o calor, e renomeada para `--amarelo-*`
> para que ninguém use as duas por engano:
>
> `--amarelo-900:#7a5c00` · `--amarelo-800:#9c7500` · `--amarelo-700:#c29200`
> `--amarelo-600:#e0aa00` · `--amarelo-500:#ffc300` ← principal · `--amarelo-400:#ffd23d`
> `--amarelo-300:#ffdf6b` · `--amarelo-200:#ffecab` · `--amarelo-100:#fff8d9`
>
> **O site público não mudou.**

**Cream / neutros**
`--cream-500:#f2e7d1` · `--cream-300:#f7f0e3` · `--cream-100:#fbf7ee`
`--white:#ffffff` · `--black:#000000`

### Papéis semânticos (usar estes, não as escalas base)

```
--color-primary        navy-700     --surface-page         white
--color-primary-hover  navy-800     --surface-card         white
--color-primary-active navy-900     --surface-card-alt     cream-100
--color-cta            amber-500    --surface-dark         navy-700
--color-cta-hover      amber-600    --surface-dark-alt     navy-800
--color-cta-active     amber-700    --surface-tint-warm    cream-100
--color-accent         amber-700
--color-support        navy-500     --border-light         navy-100
                                    --border-default       navy-200
--text-on-light-primary    navy-700 --border-dark          rgba(255,255,255,.24)
--text-on-light-secondary  #4a5872
--text-on-light-muted      #7c86a0  --color-disabled-bg    navy-100
--text-on-dark-primary     white    --color-disabled-text  navy-300
--text-on-dark-secondary   cream-500
--text-on-dark-muted       navy-300
--text-link            navy-600
--text-link-hover      navy-800
```

### Papéis semânticos **no sistema** (o que mudou)

O sistema não usa `--color-accent` nem amarelo em botão. A tabela acima é a do
site; no `sistema/frontend/src/styles/tokens.css` valem estes:

```
--color-cta            = --color-primary  (navy-700)   botão cheio
--color-cta-hover      = --color-primary-hover
--color-cta-active     = --color-primary-active
--color-cta-text       = white

--color-destaque       amarelo-500   preenchimento de elemento
--color-destaque-forte amarelo-600   borda/hover de elemento
--surface-destaque     amarelo-100   tinta de fundo (aviso, etiqueta, painel)
--border-destaque      amarelo-300   borda desses blocos

--text-accent          navy-500      acento de TEXTO (eyebrow, nome, rótulo)
--focus-ring           navy-700      anel de foco em fundo claro
--focus-ring-dark      amarelo-500   anel de foco sobre a lateral navy

--color-accent         REMOVIDO      era amarelo em texto
```

**Duas regras novas, e elas não são negociáveis:**

1. **Amarelo é elemento, nunca tipo.** Preenchimento, borda, ponto, barra, anel
   de foco sobre navy — sim. Cor de letra — não, nem o `amarelo-900`, que só
   parecia seguro por ser escuro. Acento de texto é `--text-accent` (navy-500).
2. **Nenhum botão é amarelo.** O botão cheio é navy com texto branco. Amarelo de
   fundo obriga texto escuro por cima, e azul sobre amarelo são duas cores
   saturadas brigando na mesma pílula.

### Regras de uso (do design system)

- **Branco é o fundo padrão da página.** Navy é para blocos institucionais/escuros.
- **Amber nunca é fundo de área grande** — só pílulas, detalhes e acentos.
- **Cream é tinta sutil**, para diferenciar um bloco do branco — não é fundo de página.
- No máximo **duas cores de fundo por tela**.
- Sem gradientes. Sem foto como fundo de página inteira.

> ⚠️ O `readme.md` do `_ds` diz que "cream é o fundo em light mode", mas o
> `tokens/colors.css` do mesmo bundle e o site implementado dizem **branco**.
> Vale o branco (é o que está em produção).

---

## 3. Tipografia

Três famílias, todas OTF locais em `site/public/fonts/` (11 arquivos, ~1,2 MB).

| Variável | Família | Uso |
| --- | --- | --- |
| `--font-display` | **Checkin** (script/bubble) | Só títulos hero e campanhas. Grande, em navy ou amber. Usar com parcimônia. |
| `--font-body` | **Typold** | Todo o resto. Corpo em 450/400, títulos em 700/800. |
| `--font-condensed` | **Typold Condensed** | Só rótulos institucionais em CAIXA ALTA, pequenos, com tracking largo. |
| `--font-extended` | **Typold Extended** | Disponível, sem uso no site atual. |

> **No `sistema/` são quatro.** Entrou `--font-serif` (**Aleo**, variável, 36 KB
> auto-hospedada) como voz da leitura: lede, mensagens e parágrafo longo. Typold
> segue sendo a voz da interface. Os papéis não se misturam — ver
> [PADROES_UI.md § 8](PADROES_UI.md). O site público não mudou.
>
> A escala do sistema também divergiu da do site: ela segue o DS de referência
> (display 36 / h1 28 / h2 22 / h3 18), mais compacta que a do site, porque
> tela de trabalho não é página de campanha.

Pesos disponíveis do Typold: 400 Regular, 450 Book, 500 Medium, 700 Bold,
800 ExtraBold, 900 Black. Condensed: 700/800/900. Extended: 700.

Fallback definido: `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.

### Escala (tokens)

```
display-xl 96px/0.95   h1 40px/1.12 w800   body-lg 19px/1.6 w450
display-lg 64px/0.98   h2 32px/1.16 w800   body-md 16px/1.6 w450
display-md 44px/1.02   h3 26px/1.20 w700   body-sm 14px/1.55 w450
                       h4 22px/1.28 w700   small   13px/1.5
                       h5 18px/1.32 w700   caption 12px/1.4
                       h6 16px/1.40 w700
botão   16px w700 tracking .01em
rótulo  13px w700 tracking .06em
eyebrow 13px w800 tracking .12em  (Condensed, CAIXA ALTA)
```

**Caixa alta é reservada** a eyebrows, rótulos e selos — nunca em parágrafos.

---

## 4. Logo e imagens

**Não existe arquivo de logo no projeto.** O `_ds/readme.md` explica: os SVGs de
logo vieram com `<style>` vazio e texto curvo em fonte não embutida, então foram
descartados; o bundle recomenda PNGs que **não estão** na pasta `assets/`.

O que o site usa como marca, no header:

```jsx
<img src="/images/star-mascot-outline.svg" alt="" className="site-header__mascot" />
Natal Lumen   {/* texto, Typold 800, 18px */}
```

Ou seja: **mascote em SVG + a palavra "Natal Lumen" em texto**. O mesmo SVG é o
favicon (`index.html`). O sistema deve fazer igual.

Arquivos em `site/public/images/` (copiar os necessários):

| Arquivo | O que é | Uso |
| --- | --- | --- |
| `star-mascot-outline.svg` (1,4 KB) | estrela mascote, contorno | marca do header, favicon, empty states |
| `sparkle-pattern.svg` (92 KB) | textura de estrelinhas | fundo decorativo, opacidade 0.18 |
| `two-stars-scene.svg` (28 KB) | cena com duas estrelas | ilustração |
| `about-photo.jpg`, `city-photo.jpg` | fotos do evento | só com filtro duotone |

O mascote no header recebe um filtro que o deixa amber:

```css
filter: invert(69%) sepia(84%) saturate(1000%) hue-rotate(360deg);
```

> **No sistema esse filtro saiu.** A cadeia só por acaso caía num amarelo
> (`#ffa800`) e não havia como mirá-la no tom novo. Em vez disso existe um
> segundo arquivo, `public/images/star-mascot-amarelo.svg`, que é o mesmo SVG
> com `fill="#ffc300"` — usado na barra lateral e na barra mobile. O
> `star-mascot-outline.svg` navy continua sendo o favicon, o `EmptyState` e a
> marca das telas de acesso.

**Fotografia é sempre duotone** (navy ou amber), nunca colorida — o componente
`DuotonePhoto` aplica isso com um filtro SVG (`feColorMatrix` + `feComponentTransfer`).
Para o sistema isso é pouco relevante (há fotos de cartões, que são documentos,
não imagens de marca) — **as fotos de cartões não devem receber duotone**.

---

## 5. Espaçamento, raios e sombras

```
--space-1  4px    --space-6  32px    --radius-sm   8px    (chips)
--space-2  8px    --space-7  48px    --radius-md   14px   (cards, inputs)
--space-3  12px   --space-8  64px    --radius-lg   22px   (seções, blocos)
--space-4  16px   --space-9  96px    --radius-pill 999px  (botões, selos)
--space-5  24px   --space-10 128px

--shadow-sm 0 2px 6px  rgba(21,51,119,.08)
--shadow-md 0 8px 24px rgba(21,51,119,.14)
--shadow-lg 0 16px 48px rgba(21,51,119,.20)

--container-max     1200px
--stroke-thick      3px
--stroke-hairline   1.5px
--stroke-hairline-color  var(--border-default)
```

Sombras são **sempre tingidas de navy**, nunca pretas. Bordas finas (1,5–2px) e
de baixo contraste.

**Linguagem de forma: cápsula/pílula.** Botões, selos e pílulas são totalmente
arredondados — é assinatura do logo em bubble-lettering. Cards usam cantos
generosos (14–22px).

---

## 6. Layout e responsividade

- **Um único breakpoint em todo o site: `@media (max-width: 860px)`.**
- Padding lateral: **64px no desktop, 24px no mobile** (o header usa 32px/16px).
- Padding vertical de seção: 112px (96px nas seções com borda) → 48px no mobile.
- Grids de duas colunas viram bloco único no mobile (`display: block`).
- O menu do header **desaparece** abaixo de 860px (`display: none`) — não há menu
  hambúrguer implementado.

> ⚠️ Para o sistema isto **precisa mudar**: a especificação exige uso por celular
> ("vários voluntários usarão pelo celular"). O sistema precisa de navegação
> mobile de verdade (menu lateral ou inferior), não pode simplesmente esconder o
> menu. Os tokens e cores continuam valendo; o padrão de navegação, não.

---

## 7. Componentes existentes (11) e o que aproveitar

Em `site/src/components/`, organizados por domínio:
`core/` · `cards/` · `navigation/` · `marketing/` · `media/` · `backgrounds/` · `feedback/`

Todos são `export default function`, sem TypeScript, com imports usando extensão
explícita (`./Home.jsx`).

| Componente | Aproveitar no sistema? |
| --- | --- |
| `core/Button` (primary amber / secondary navy / ghost; sm-md-lg) | **Sim, portar.** Base dos botões do sistema. |
| `feedback/EmptyState` (mascote + título + corpo + ação) | **Sim, portar.** Listas vazias. |
| `cards/BrowserCard` (card com barra de "janela" pontilhada) | Talvez — visual muito institucional para telas densas de dados. |
| `navigation/SiteHeader` / `SiteFooter` | **Não portar como estão.** O sistema precisa de header com usuário/edição/logout e menu mobile. Servem de referência de cor e altura. |
| `core/Badge`, `core/CampaignPill`, `marketing/CTASection`, `marketing/StoreBanner`, `media/DuotonePhoto`, `backgrounds/DecorativeBackground` | Não — são de marketing institucional. |

### Anatomia do `Button` (referência a manter)

> **O sistema mudou o `primary`.** Abaixo está o site; no sistema `primary` e
> `secondary` são ambos navy cheio com texto branco (escopos diferentes: CTA da
> página vs. confirmar do modal), e `ghost` é o contorno. Ver
> [PADROES_UI.md § 2](PADROES_UI.md).

```
primary   fundo amber-500,  texto navy-900   hover amber-600   ← só no site
secondary fundo navy-700,   texto branco     hover navy-800
ghost     transparente, borda 2px navy-700   hover navy-100
desabilitado  fundo navy-100, texto navy-300, cursor not-allowed
comum     border-radius pill · border 2px · font-weight 700
          transition 150ms (background, color, border-color, transform)
          tamanhos sm 10/18px·14 · md 14/28px·16 · lg 18/36px·18
```

---

## 8. O que **não** existe no site e terá de ser criado

O site é institucional: não tem formulários nem telas de dados. Portanto **não há
padrão pronto** para nada abaixo — criar no sistema, respeitando os tokens:

- `input` de texto, `select`, `textarea`, checkbox, radio, input de arquivo
- estados de foco, erro e validação de campo
- tabelas e listas densas de dados, paginação, filtros e busca
- modais/diálogos, abas, tooltips
- mensagens de erro/sucesso/aviso (toasts ou banners)
- indicadores de carregamento (spinner, skeleton)
- navegação de aplicação: menu lateral, breadcrumb, menu do usuário
- badges de status (ex.: pendente/montado/entregue, digitalizado/enviado)

**Sugestão de base para campos** (coerente com os botões e com os tokens):
fundo branco, borda `2px solid var(--border-default)`, raio `var(--radius-md)`,
padding `12px 14px`, fonte `var(--font-body)` 16px, e no foco
`border-color: var(--color-primary)` sem `outline`.

---

## 9. Checklist para `sistema/frontend`

- [ ] Copiar `site/public/fonts/*.otf` → `sistema/frontend/public/fonts/` (11 arquivos)
- [ ] Copiar `star-mascot-outline.svg` e `sparkle-pattern.svg` → `public/images/`
- [ ] Copiar `site/src/styles/tokens.css` → `src/styles/tokens.css` (sem alterar os valores)
- [ ] Recriar `index.css` com `@import "./styles/tokens.css"` + reset
- [ ] Portar `Button` e `EmptyState`
- [ ] Criar a camada de formulários/tabelas que o site não tem
- [ ] Navegação mobile de verdade (o site apenas esconde o menu)
- [ ] Favicon = `star-mascot-outline.svg`, como no site
