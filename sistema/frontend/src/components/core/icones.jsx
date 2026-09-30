// Icones do sistema, desenhados a mao em SVG.
//
// Nao ha fonte de icones nem biblioteca: sao doze linhas de path cada um, e
// uma dependencia a menos para carregar. Todos seguem a mesma grade de 24, com
// traco de 2 e `currentColor` — assim herdam a cor do botao e o hover funciona
// sem nenhuma regra extra.
//
// O tamanho vem de fora (`t`), porque o mesmo icone aparece em 15px na
// planilha e em 16px na ficha.

function Svg({ t = 15, children }) {
  return (
    <svg
      width={t}
      height={t}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

/** Ver como lista: linhas empilhadas. */
export function ListaIcone({ t }) {
  return (
    <Svg t={t}>
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" />
      <line x1="3" y1="12" x2="3.01" y2="12" />
      <line x1="3" y1="18" x2="3.01" y2="18" />
    </Svg>
  );
}

/** Ver como arquivo: quadradinhos lado a lado, como uma gaveta de fotos. */
export function ArquivoIcone({ t }) {
  return (
    <Svg t={t}>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </Svg>
  );
}

/** Trocar o arquivo por outro: duas setas em ciclo. */
export function Trocar({ t }) {
  return (
    <Svg t={t}>
      <path d="M21 8V3h-5" />
      <path d="M21 3l-6.5 6.5A7 7 0 0 0 5 12" />
      <path d="M3 16v5h5" />
      <path d="M3 21l6.5-6.5A7 7 0 0 0 19 12" />
    </Svg>
  );
}

/** Passar para o cartao seguinte na conferencia. */
export function ChevronDireita({ t }) {
  return (
    <Svg t={t}>
      <path d="M9 5l7 7-7 7" />
    </Svg>
  );
}

/** Voltar um cartao na conferencia. */
export function ChevronEsquerda({ t }) {
  return (
    <Svg t={t}>
      <path d="M15 5l-7 7 7 7" />
    </Svg>
  );
}

/** Conferido: o visto que a pessoa deu ao passar o cartao. */
export function Visto({ t }) {
  return (
    <Svg t={t}>
      <path d="M4 12.5l5 5L20 6.5" />
    </Svg>
  );
}

/** Ver a ficha. */
export function Olho({ t }) {
  return (
    <Svg t={t}>
      <path d="M1.5 12S5 5.5 12 5.5 22.5 12 22.5 12 19 18.5 12 18.5 1.5 12 1.5 12Z" />
      <circle cx="12" cy="12" r="3.2" />
    </Svg>
  );
}

/** Apadrinhar: ligar este padrinho a mais uma crianca. */
export function PessoaMais({ t }) {
  return (
    <Svg t={t}>
      <circle cx="9" cy="8" r="3.4" />
      <path d="M2.8 20c0-3.4 2.8-5.6 6.2-5.6 1.3 0 2.5.3 3.5.9" />
      <path d="M17.5 14.5v6M14.5 17.5h6" />
    </Svg>
  );
}

/** Baixar o cartao de agradecimento. */
export function Baixar({ t }) {
  return (
    <Svg t={t}>
      <path d="M12 3.5v10.5" />
      <path d="M8 10.5 12 14.5 16 10.5" />
      <path d="M4.5 17.5v1.5a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-1.5" />
    </Svg>
  );
}

/** Enviar pelo WhatsApp. */
export function Enviar({ t }) {
  return (
    <Svg t={t}>
      <path d="M21 3 10.5 13.5" />
      <path d="M21 3 14.5 21l-4-7.5L3 9.5 21 3Z" />
    </Svg>
  );
}

/** Desfazer o apadrinhamento. */
export function Desfazer({ t }) {
  return (
    <Svg t={t}>
      <path d="M3.5 8.5h11a5.5 5.5 0 0 1 0 11H8" />
      <path d="M7 4 3.5 8.5 7 13" />
    </Svg>
  );
}

/** Remover a linha. */
export function Xis({ t }) {
  return (
    <Svg t={t}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  );
}

/** Tres pontinhos: abre o menu de acoes da linha.
 *
 * Circulos preenchidos, e nao tracos: com `stroke` de 2 num raio pequeno o
 * ponto virava anel. Aqui o `fill` vem de `currentColor` para seguir a cor do
 * botao igual aos outros.
 */
export function TresPontos({ t }) {
  return (
    <Svg t={t}>
      <circle cx="12" cy="5" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="12" cy="19" r="1.6" fill="currentColor" stroke="none" />
    </Svg>
  );
}

/** Configuracoes: as telas que so a administracao geral abre.
 *
 * Reguladores, e nao engrenagem. A engrenagem classica tem oito dentes dentro
 * da grade de 24, e no tamanho em que este icone aparece — 18px, na base da
 * lateral — os dentes viram uma mancha. Duas reguas com o cursor no lugar
 * continuam legiveis ali.
 */
export function Configuracoes({ t }) {
  return (
    <Svg t={t}>
      <path d="M4 7h9.5M18.5 7H20M4 17h1.5M10.5 17H20" />
      <circle cx="16" cy="7" r="2.3" />
      <circle cx="8" cy="17" r="2.3" />
    </Svg>
  );
}
