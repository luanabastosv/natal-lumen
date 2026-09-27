import { useSessao } from "../../contexts/useSessao.js";

/** Barra fina que so existe no celular, onde a lateral vira gaveta: sem ela
 *  nao haveria de onde abrir a gaveta. No desktop ela nao e renderizada — a
 *  navegacao inteira mora na lateral. */
export default function BarraMobile({ aoAbrirMenu, menuAberto }) {
  const { edicao } = useSessao();

  return (
    <header className="barra-mobile">
      <button
        type="button"
        className="barra-mobile__menu"
        onClick={aoAbrirMenu}
        aria-label={menuAberto ? "Fechar menu" : "Abrir menu"}
        aria-expanded={menuAberto}
      >
        <span className="barra-mobile__hamburguer" aria-hidden="true" />
      </button>

      <img
        src="/acesso/images/star-mascot-amarelo.svg"
        alt=""
        className="barra-mobile__mascote"
      />
      <span className="barra-mobile__nome">Natal Lumen</span>

      {/* So mostra qual edicao esta sendo vista: com a lateral fechada, as
          paginas nao diriam. Trocar continua sendo la dentro. */}
      {edicao && (
        <span className="barra-mobile__edicao">
          {edicao.cidade} {edicao.ano}
        </span>
      )}
    </header>
  );
}
