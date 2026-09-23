# Identidade visual — extraída de `site/`

Documento de referência para o sistema em `sistema/frontend`. Tudo aqui foi lido
do site público em `site/` (que está em produção e **não deve ser alterado**) e do
bundle do design system em `_ds/natal-lumen-design-system-*/`.

> Regra do projeto: **nunca importar arquivos de `site/`**. Os arquivos visuais
> necessários (fontes, SVGs, tokens) são **copiados** para `sistema/frontend`.

---

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

**Amber** (ação/destaque)
`--amber-900:#8f6301` · `--amber-800:#b17701` · `--amber-700:#cc8902`
`--amber-600:#e69c00` · `--amber-500:#ffb000` ← principal · `--amber-400:#ffc23d`
`--amber-300:#ffd166` · `--amber-200:#ffe3a3` · `--amber-100:#fff3d6`

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

### Regras de uso (do design system)

- **Branco é o fundo padrão da página.** Navy é para blocos institucionais/escuros.
- **Amber nunca é fundo de área grande** — só CTA, pílulas, detalhes e acentos.
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

```
primary   fundo amber-500,  texto navy-900   hover amber-600
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
