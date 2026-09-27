import { useEffect, useRef, useState } from "react";
import { Xis } from "../core/icones.jsx";

/** Quanto tempo o recado fica na tela antes de sair sozinho. */
const DURACAO = 5000;

/** Tempo da animacao de saida — o mesmo valor do CSS (--dur-slow). */
const SAIDA = 280;

/** Um recado no canto da tela.
 *
 * Sai sozinho depois de alguns segundos, e o X tira na hora. O relogio PARA
 * enquanto o ponteiro esta em cima ou o foco esta dentro: quem foi ler o
 * recado nao pode ve-lo desaparecer no meio da leitura. Ao sair de cima, a
 * contagem recomeca do inicio: e mais simples do que guardar o tempo que
 * faltava, e o erro cai para o lado de deixar o recado tempo demais — nunca
 * de tira-lo cedo demais.
 */
export default function Notificacao({ texto, aoSair }) {
  const [pausado, definirPausado] = useState(false);
  const [saindo, definirSaindo] = useState(false);
  const caixa = useRef(null);

  // `aoSair` chega como funcao nova a cada render do provedor. Guardada no
  // ref, o efeito da saida depende so de `saindo` e o relogio nao reinicia.
  const sair = useRef(aoSair);
  useEffect(() => {
    sair.current = aoSair;
  });

  useEffect(() => {
    if (pausado || saindo) return;
    const relogio = setTimeout(() => definirSaindo(true), DURACAO);
    return () => clearTimeout(relogio);
  }, [pausado, saindo]);

  // A remocao vem por relogio, e nao por `animationend`: o evento nao chega
  // quando a aba esta em segundo plano nem quando o sistema pede menos
  // movimento, e o recado ficaria preso na tela.
  useEffect(() => {
    if (!saindo) return;
    const relogio = setTimeout(() => sair.current(), SAIDA);
    return () => clearTimeout(relogio);
  }, [saindo]);

  function fechar() {
    definirSaindo(true);
    // Fechar com o teclado deixaria o foco num botao que vai sumir. Devolve
    // para o corpo da pagina antes que isso aconteca.
    if (caixa.current?.contains(document.activeElement)) {
      document.activeElement.blur();
    }
  }

  return (
    <div
      ref={caixa}
      className={`notificacao ${saindo ? "notificacao--saindo" : ""}`}
      onMouseEnter={() => definirPausado(true)}
      onMouseLeave={() => definirPausado(false)}
      onFocusCapture={() => definirPausado(true)}
      onBlurCapture={() => definirPausado(false)}
    >
      <p className="notificacao__texto">{texto}</p>
      <button
        type="button"
        className="notificacao__fechar"
        onClick={fechar}
        aria-label="Fechar aviso"
      >
        <Xis t={14} />
      </button>
    </div>
  );
}
