import Estrelinhas from "../feedback/Estrelinhas.jsx";

/** Botao que e so um icone.
 *
 * Existe porque acao repetida por linha nao cabe escrita: um padrinho com
 * quinze criancas tem quinze vezes "Cartao", "WhatsApp" e "Desfazer" na
 * ficha, e a palavra ali nao informa mais do que o icone — informa menos,
 * porque empurra tudo para baixo.
 *
 * O rotulo nao some, muda de lugar: `titulo` vira `title` (a dica do mouse) e
 * `aria-label` (o que o leitor de tela anuncia). Nunca chame sem ele.
 */
export default function BotaoIcone({
  titulo,
  children,
  onClick,
  tamanho = "md",
  perigo = false,
  disabled = false,
  carregando = false,
}) {
  const inativo = disabled || carregando;

  const classe = [
    "botao-icone",
    tamanho === "sm" ? "botao-icone--sm" : "",
    perigo ? "botao-icone--perigo" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={classe}
      title={titulo}
      aria-label={titulo}
      aria-busy={carregando || undefined}
      disabled={inativo}
      onClick={inativo ? undefined : onClick}
    >
      {carregando ? <Estrelinhas tamanho={7} /> : children}
    </button>
  );
}
