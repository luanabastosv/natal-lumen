import { useNavigate } from "react-router-dom";
import { useSessao } from "../../contexts/useSessao.js";

/** Barra fina que so existe no celular, onde a lateral vira gaveta: sem ela
 *  nao haveria de onde abrir a gaveta. No desktop ela nao e renderizada — a
 *  navegacao inteira mora na lateral. */
export default function BarraMobile({ aoAbrirMenu, menuAberto }) {
  const { edicao } = useSessao();
  const navegar = useNavigate();

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

      {/* A marca leva ao painel, como na lateral do computador. */}
      <button
        type="button"
        className="marca-link"
        onClick={() => navegar("/painel")}
        aria-label="Natal Lumen, ir para o painel"
      >
        <img
          src="/acesso/images/star-mascot-amarelo.svg"
          alt=""
          className="barra-mobile__mascote"
        />
        <span className="barra-mobile__nome">Natal Lumen</span>
      </button>

      {/* So mostra qual edicao esta sendo vista: com a lateral fechada, as
          paginas nao diriam. Trocar continua sendo la dentro. */}
      {edicao && (
        <span className="barra-mobile__edicao">
          {edicao.nome}
        </span>
      )}
    </header>
  );
}
