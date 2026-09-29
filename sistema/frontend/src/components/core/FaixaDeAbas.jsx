import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDireita, ChevronEsquerda } from "./icones.jsx";

/** Faixa de abas que passa de lado por chevron, no lugar da barra de rolagem.
 *
 * Numa cidade grande sao mais de vinte instituicoes, e elas nunca caberiam na
 * largura da tela. A barra de rolagem resolvia isso, mas mal: ela e fina,
 * aparece so quando o ponteiro chega perto, e nao anuncia que ha mais coisa do
 * outro lado. O chevron anuncia.
 *
 * Cada clique anda quase uma tela cheia de abas (PASSO), e nao uma aba por
 * vez: com vinte instituicoes, de aba em aba seriam vinte cliques para chegar
 * na ultima.
 *
 * O arrasto por trackpad continua valendo — a rolagem nao foi desligada, so a
 * barra dela ficou invisivel.
 */

const PASSO = 0.8;

export default function FaixaDeAbas({ children, reiniciarEm }) {
  const trilho = useRef(null);

  // `rola` separado de `inicio`/`fim` porque sao perguntas diferentes: se ha o
  // que passar (senao os chevrons nem aparecem) e se ja se chegou na ponta
  // (ai eles aparecem apagados).
  const [estado, definirEstado] = useState({ rola: false, inicio: true, fim: true });

  const conferir = useCallback(() => {
    const el = trilho.current;
    if (!el) return;

    const sobra = el.scrollWidth - el.clientWidth;
    // A folga de 1px e por causa do zoom do navegador: em 110% a conta fecha
    // em 199,6 de 200 e o chevron da direita nunca apagaria.
    definirEstado({
      rola: sobra > 1,
      inicio: el.scrollLeft <= 1,
      fim: el.scrollLeft >= sobra - 1,
    });
  }, []);

  // A largura muda sem ninguem rolar nada: a janela e redimensionada, a gaveta
  // do celular abre, a lateral recolhe.
  useEffect(() => {
    const el = trilho.current;
    if (!el) return;

    const observador = new ResizeObserver(conferir);
    observador.observe(el);
    return () => observador.disconnect();
  }, [conferir]);

  // A lista de abas em si mudou (trocou a edicao, chegou instituicao nova). O
  // ResizeObserver nao ve isso: a largura do trilho continua a mesma, o que
  // mudou foi o conteudo dentro dele.
  useEffect(conferir, [conferir, children]);

  // Trocar de edicao volta a faixa para o comeco. Sem isto ela ficaria parada
  // no meio, mostrando instituicoes de uma lista que ja nao e aquela — e com
  // "Todas", que fica na primeira posicao e e a aba que acabou de ser
  // escolhida, fora da tela.
  useEffect(() => {
    if (trilho.current) trilho.current.scrollLeft = 0;
  }, [reiniciarEm]);

  function andar(direcao) {
    const el = trilho.current;
    if (!el) return;

    // `scroll-behavior` no CSS nao vence um `behavior` explicito aqui, entao
    // quem respeita "reduzir movimento" tem de ser este lado.
    const suave = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    el.scrollBy({
      left: direcao * el.clientWidth * PASSO,
      behavior: suave ? "smooth" : "auto",
    });
  }

  return (
    <div className="faixa-abas">
      {estado.rola && (
        <button
          type="button"
          className="faixa-abas__seta"
          onClick={() => andar(-1)}
          disabled={estado.inicio}
          aria-label="Ver as instituições anteriores"
        >
          <ChevronEsquerda t={16} />
        </button>
      )}

      <div
        ref={trilho}
        className="abas abas--rolavel"
        role="tablist"
        onScroll={conferir}
      >
        {children}
      </div>

      {estado.rola && (
        <button
          type="button"
          className="faixa-abas__seta"
          onClick={() => andar(1)}
          disabled={estado.fim}
          aria-label="Ver as próximas instituições"
        >
          <ChevronDireita t={16} />
        </button>
      )}
    </div>
  );
}
