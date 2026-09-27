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
