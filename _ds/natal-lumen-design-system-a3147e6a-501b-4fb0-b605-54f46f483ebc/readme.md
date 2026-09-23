# Natal Lumen — Design System

## What is Natal Lumen
Natal Lumen is a Christmas-season social project run for 30+ years, linked to Obra Lumen Ser Feliz. It brings a day of play, food and celebration to thousands of vulnerable children in Fortaleza and other Brazilian cities (and Guiné-Bissau), plus year-round donation and sponsorship ("apadrinhamento") campaigns. This design system is for the **institutional website** — a permanent site whose visual identity is refreshed each edition/year, run by a Catholic evangelization ministry, balancing warmth for children/families with credibility for donors, volunteers and corporate partners.

**Source material**: brand assets supplied directly by the user (logos, mascot/seal artwork, illustrated children, sparkle texture, Checkin script font, full Typold family). No Figma file, codebase or existing site was attached — this system was authored from those assets and the brief alone. See `uploads/` in this project for the original files.

## Index
- `styles.css` — root stylesheet, imports everything under `tokens/`
- `tokens/` — colors, fonts, typography scale, spacing/radius/shadow
- `assets/logos/` — primary lockup + sticker badges (PNG, as supplied — see Iconography)
- `assets/illustrations/` — duotone children, star mascot, sparkle texture, seal artwork (recolored SVGs, see Iconography)
- `assets/fonts/` — Checkin (display) + Typold family (body/condensed/extended), as OTF
- `components/` — 11 React components across `core/`, `cards/`, `navigation/`, `marketing/`, `media/`, `backgrounds/`, `feedback/`
- `guidelines/` — foundation specimen cards (colors, type, spacing) shown in the Design System tab

### Components
- **core/Button** — primary (amber), secondary (navy), ghost
- **core/Badge** — circular campaign seal with curved lettering, mascot centered
- **core/CampaignPill** — tilted sticker pill for short campaign phrases
- **cards/BrowserCard** — browser-chrome card (dotted top bar) for editions/testimonials/news
- **navigation/SiteHeader**, **navigation/SiteFooter** — institutional header/footer
- **marketing/CTASection** — donate / sponsor / volunteer block
- **marketing/StoreBanner** — "Loja aberta" banner for the seasonal Shopify store
- **media/DuotonePhoto** — navy/amber duotone photo filter
- **backgrounds/DecorativeBackground** — sparkle texture or organic blob wrapper
- **feedback/EmptyState** — mascot or kids illustration + message, for empty/thank-you states

**Intentional additions**: none of the above were invented beyond the brief's explicit component list — `core/CampaignPill` and `backgrounds/DecorativeBackground` are direct implementations of "faixa/pílula de texto curvo" and "blob orgânico / padrão de estrelinhas" from the brief.

## Content fundamentals
- **Language**: Brazilian Portuguese, direct address using "você" implicitly (imperative verbs: "Apadrinhe", "Doe", "Participe") rather than "eu/nós" framing.
- **Tone**: warm and inviting, but not childish — sentences are short, concrete, and centered on the child ("Cada real ajuda a levar brincadeiras, alimentação e presentes"). Avoid corporate-NGO jargon; avoid religious language beyond a light institutional mention (the ministry link is stated plainly, not preached).
- **Casing**: sentence case for body copy and headings; ALL CAPS reserved for eyebrows/labels (Typold Condensed) and badge/seal lettering — never for full paragraphs.
- **CTAs**: verb-first, 2-4 words — "Apadrinhar agora", "Quero doar", "Ser voluntário", "Visitar loja".
- **Numbers**: used sparingly and only when concrete/sourced (e.g. "3.200 crianças") — never invented statistics.
- **Emoji**: not used anywhere in the supplied assets or reference copy — do not introduce them.

## Visual foundations
- **Colors**: navy (#153377) is the dominant brand color and default page/section background for institutional moments; amber (#ffb000) is reserved for CTAs, the store banner and accents — never used as a large background. Cream (#f2e7d1) is the light-mode page background, not white. Max two background colors per screen (navy or cream), per brand guidance.
- **Type**: Checkin (script, bubble-lettering) is the display face for hero moments and campaign headlines — used sparingly, large, in navy or amber. Typold carries everything else: body copy at Book/Regular weight, headings at Bold/ExtraBold. Typold Condensed is reserved for uppercase institutional labels and eyebrows (small size, wide tracking).
- **Imagery**: all photography is duotone (navy or amber tint) — never full color. Illustrated children are line-art with navy fills, used as decorative/institutional elements (empty states, section accents), never as literal content photography substitutes.
- **Backgrounds**: mostly flat navy or cream; two decorative motifs layer on top — a repeating low-opacity sparkle-star texture, and soft irregular "blob" shapes in amber tones behind headlines. No gradients, no photography as full-bleed backgrounds observed in source material.
- **Shape language**: pill/capsule shapes throughout (buttons, badges, campaign pills) — a signature of the bubble-lettering logo. Cards use generous rounded corners (14–22px) styled like a browser window (dotted top bar) rather than plain rectangles.
- **Shadows**: soft, navy-tinted, low-opacity — used for elevation on cards and CTA blocks, never harsh/black.
- **Animation/hover/press**: no motion specified in source material; components use simple, quick (150ms) color transitions on hover (darken/amber-shift) as a sensible default — treat as a starting point, not a documented brand rule.
- **Borders**: thin (1.5–2px), low-contrast navy — used to separate card chrome, rarely as a primary visual device.
- **Corner radii**: sm 8px (chips), md 14px (cards/banners), lg 22px (feature sections), pill 999px (buttons/badges).
- **Transparency/blur**: not used in source material; decorative textures use opacity (not blur) to recede.

## Iconography
- No system icon font or SVG icon set was supplied — the brand does not appear to use a conventional UI icon system. Its "iconography" is illustrative: the star mascot, the circular seal, and the sparkle motif stand in for icons across empty states, badges and section markers.
- Several supplied illustration SVGs (`crianca-1`, `criancas-2`, `estrelachocada`, `Asset 63`, `Asset 54`, `2estrelas`, `2estrelas2`) shipped with empty `<style>` blocks (undefined CSS classes, no fill colors) — they would have rendered solid black. These were recolored (fills applied directly per path/class) to match the brand's navy/amber duotone treatment and saved under `assets/illustrations/`. Originals are untouched in `uploads/`.
- Logo variants supplied as SVG (`nl-correct`, `nl-sticker`, `nl-sticker-horizontal`, `nl-amarelo`, `logo-withouttext`, `tag`) had the same missing-style issue plus embedded curved `<text>`/`<tspan>` lettering that depends on the Checkin font rendering inside the SVG — these were not reliably fixable and are **not** included in `assets/`. Use the supplied PNG lockups instead (`assets/logos/`), which render correctly. Flagging this for the user — see Caveats.
- Emoji are not used anywhere in the source material.

## Caveats — please help me iterate
1. **Vector logo files are unusable as shipped.** `nl-correct`, `nl-sticker`, `nl-sticker-horizontal`, `nl-amarelo`, `logo-withouttext` and `tag` (all SVG) have empty style definitions and, in several cases, curved text set in a font that isn't embedded — they render as solid black shapes or blank text. I used the PNG lockups (`logo1@3x.png`, `Asset 50/51@1x.png`) instead, which look correct. **Could you re-export clean SVGs** (with fills baked in, and any curved text converted to outlines) for the vertical/horizontal lockups and the monogram? That would let the logo scale losslessly.
2. **No horizontal lockup or favicon-ready monogram** currently renders correctly — same root cause as above.
3. **Font substitution**: none needed — Checkin and the full Typold family were supplied and are embedded as-is.
4. **No codebase or Figma file was attached**, so components/pages here are built directly from the brief and brand assets, not from an existing site — please flag anything that should match a specific existing screen.
5. The circular **Badge** seal recreates the official stamp's curved lettering with SVG `textPath` rather than the original artwork (which has the same missing-font-in-SVG issue) — check it against the real seal for exact letterform match.
