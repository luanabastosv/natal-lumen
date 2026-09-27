/** Barra fina que so existe no celular, onde a lateral vira gaveta: sem ela
 *  nao haveria de onde abrir a gaveta. No desktop ela nao e renderizada — a
 *  navegacao inteira mora na lateral. */
export default function BarraMobile({ aoAbrirMenu, menuAberto }) {
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
    </header>
  );
}
