// Botao do sistema. A anatomia segue o DS: pilula, peso 800, afunda no
// :active e ganha anel de foco no :focus-visible.
//
// O estilo vive em CSS (.botao, em base.css) e nao mais em style inline: com
// inline nao existe :active nem :focus-visible, e o hover precisava de dois
// handlers de JS que o teclado nunca disparava.

import Estrelinhas from "../feedback/Estrelinhas.jsx";

const TAMANHOS = { sm: "botao--sm", md: "", lg: "botao--lg" };

export default function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  carregando = false,
  larguraTotal = false,
  type = "button",
  iconLeft,
  // Botao so de icone, redondo. O `titulo` passa a ser obrigatorio: vira a
  // dica do mouse e o que o leitor de tela anuncia, ja que nao ha texto.
  soIcone = false,
  titulo,
  children,
  onClick,
  as = "button",
  href,
}) {
  const inativo = disabled || carregando;
  const Tag = as === "a" ? "a" : "button";

  const classe = [
    "botao",
    `botao--${variant}`,
    TAMANHOS[size] ?? "",
    larguraTotal ? "botao--largo" : "",
    soIcone ? "botao--so-icone" : "",
    inativo ? "botao--inativo" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <Tag
      className={classe}
      href={as === "a" ? href : undefined}
      type={as === "button" ? type : undefined}
      disabled={as === "button" ? inativo : undefined}
      aria-disabled={as === "a" && inativo ? true : undefined}
      title={titulo}
      aria-label={soIcone ? titulo : undefined}
      aria-busy={carregando || undefined}
      onClick={inativo ? undefined : onClick}
    >
      {/* Enquanto salva, as estrelinhas ocupam o lugar do icone: o botao nao
          muda de largura no meio do clique, e quem clicou ve que a coisa esta
          andando sem precisar ler o texto de novo. */}
      {carregando ? <Estrelinhas tamanho={13} /> : iconLeft}
      {children}
    </Tag>
  );
}
