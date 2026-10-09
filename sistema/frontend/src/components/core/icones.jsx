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

/** Baixar o agradecimento. */
export function Baixar({ t }) {
  return (
    <Svg t={t}>
      <path d="M12 3.5v10.5" />
      <path d="M8 10.5 12 14.5 16 10.5" />
      <path d="M4.5 17.5v1.5a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-1.5" />
    </Svg>
  );
}

/** Importar uma planilha: a seta sobe para dentro da bandeja, o avesso do
 *  Baixar. Mesmo desenho de bandeja, para os dois lerem como par. */
export function Importar({ t }) {
  return (
    <Svg t={t}>
      <path d="M12 14.5V4" />
      <path d="M8 8 12 4 16 8" />
      <path d="M4.5 17.5v1.5a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-1.5" />
    </Svg>
  );
}

/** Imprimir: a impressora com a folha saindo embaixo. */
export function Imprimir({ t }) {
  return (
    <Svg t={t}>
      <path d="M7 8V3.5h10V8" />
      <path d="M7 17H5a1.5 1.5 0 0 1-1.5-1.5v-5A1.5 1.5 0 0 1 5 9h14a1.5 1.5 0 0 1 1.5 1.5v5A1.5 1.5 0 0 1 19 17h-2" />
      <rect x="7" y="13.5" width="10" height="7" rx="0.5" />
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

/* ---------- Icones do menu lateral ----------
   Um por destino. Existem para a lateral recolhida, onde so o icone aparece;
   na aberta eles vao ao lado do nome, para a pessoa aprender o par. */

/** Painel: a casa, a porta de entrada. */
export function MenuPainel({ t }) {
  return (
    <Svg t={t}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9v11h14V9" />
      <path d="M10 20v-6h4v6" />
    </Svg>
  );
}

/** Criancas: duas cabecinhas, uma maior e uma menor. */
export function MenuCriancas({ t }) {
  return (
    <Svg t={t}>
      <circle cx="9" cy="7" r="3" />
      <path d="M3 20v-1a6 6 0 0 1 12 0v1" />
      <circle cx="17.5" cy="9.5" r="2.2" />
      <path d="M16 20v-1.5a4.5 4.5 0 0 1 5-4.4" />
    </Svg>
  );
}

/** Padrinhos: o coracao de quem doa. */
export function MenuPadrinhos({ t }) {
  return (
    <Svg t={t}>
      <path d="M12 20s-7-4.4-9-9a4.6 4.6 0 0 1 8.2-4.1L12 8l.8-1.1A4.6 4.6 0 0 1 21 11c-2 4.6-9 9-9 9z" />
    </Svg>
  );
}

/** Cartoes e autorizacao: o envelope. */
export function MenuCartoes({ t }) {
  return (
    <Svg t={t}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </Svg>
  );
}

/** Kits: a caixa de presente. */
export function MenuKits({ t }) {
  return (
    <Svg t={t}>
      <rect x="3" y="8" width="18" height="4" rx="1" />
      <path d="M5 12v8h14v-8" />
      <path d="M12 8v12" />
      <path d="M12 8S10.5 3.5 8 4.5 9 8 12 8zM12 8s1.5-4.5 4-3.5S15 8 12 8z" />
    </Svg>
  );
}

/** Financeiro: a moeda. */
export function MenuFinanceiro({ t }) {
  return (
    <Svg t={t}>
      <circle cx="12" cy="12" r="9" />
      <path d="M15 9.5c-.5-1-1.6-1.5-3-1.5-1.7 0-3 .9-3 2s1.3 1.7 3 2 3 .9 3 2-1.3 2-3 2c-1.4 0-2.5-.5-3-1.5" />
      <path d="M12 6.5v11" />
    </Svg>
  );
}

/** Check-in: a prancheta com o visto. */
export function MenuCheckin({ t }) {
  return (
    <Svg t={t}>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4V3h6v1" />
      <path d="m9 13 2 2 4-4" />
    </Svg>
  );
}

/** Usuarios: o cracha de quem trabalha no sistema. */
export function MenuUsuarios({ t }) {
  return (
    <Svg t={t}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <circle cx="9" cy="11" r="2" />
      <path d="M6 16a3 3 0 0 1 6 0" />
      <path d="M15 10h3M15 14h3" />
    </Svg>
  );
}

/** Instituicoes: o predio da escola. */
export function MenuInstituicoes({ t }) {
  return (
    <Svg t={t}>
      <path d="M3 21h18" />
      <path d="M5 21V10l7-5 7 5v11" />
      <path d="M10 21v-5h4v5" />
      <path d="M9 11h.01M15 11h.01" />
    </Svg>
  );
}

/** Recolher/abrir a lateral: a barra com a seta. */
export function MenuRecolher({ t, aberto = true }) {
  return (
    <Svg t={t}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" />
      {aberto ? <path d="m16 10-2 2 2 2" /> : <path d="m14 10 2 2-2 2" />}
    </Svg>
  );
}
