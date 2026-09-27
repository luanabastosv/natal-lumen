import { useEffect, useLayoutEffect, useRef, useState } from "react";
import BotaoIcone from "./BotaoIcone.jsx";
import { TresPontos } from "./icones.jsx";

/** As acoes de uma linha, atras de tres pontinhos.
 *
 * Existe porque acao escrita por linha nao escala: "Editar · Desativar ·
 * Apagar" em cinquenta linhas sao cento e cinquenta palavras competindo com o
 * dado, e a mais perigosa delas fica a um clique de distancia da mais comum.
 * Atras do menu, cada linha mostra os DADOS, e quem quer agir pede o menu.
 *
 * `itens`: [{ rotulo, aoEscolher, perigo?, disabled? }] — `perigo` marca a
 * que nao tem volta, que vai sempre por ultimo e separada.
 *
 * A lista e `position: fixed` de proposito: a planilha vive dentro de um
 * `.tabela-rolagem`, que corta o que passa da borda — um menu posicionado por
 * dentro dela apareceria cortado pela metade nas ultimas linhas.
 */
export default function MenuAcoes({ titulo = "Ações", itens }) {
  const [aberto, definirAberto] = useState(false);
  const botao = useRef(null);
  const caixa = useRef(null);

  const visiveis = itens.filter(Boolean);

  // A posicao e escrita direto no no, e nao guardada em estado: ela so pode
  // ser calculada depois que a lista existe (precisa da altura dela), e passar
  // por estado obrigaria um segundo render so para mover a caixa de lugar. A
  // lista nasce `visibility: hidden` e aparece aqui, ja no lugar certo.
  useLayoutEffect(() => {
    if (!aberto) return;

    const lista = caixa.current;
    const alvo = botao.current.getBoundingClientRect();
    const abaixo = alvo.bottom + 6;
    // Vira para cima quando nao cabe embaixo: numa planilha longa a ultima
    // linha e justo a que mais recebe clique, e o menu dela cairia fora.
    const cabeAbaixo = abaixo + lista.offsetHeight <= window.innerHeight - 8;

    lista.style.top = `${cabeAbaixo ? abaixo : Math.max(8, alvo.top - 6 - lista.offsetHeight)}px`;
    lista.style.right = `${Math.max(8, window.innerWidth - alvo.right)}px`;
    lista.style.visibility = "visible";

    lista.querySelector("button:not([disabled])")?.focus();
  }, [aberto]);

  useEffect(() => {
    if (!aberto) return;

    const fechar = () => definirAberto(false);

    const clicouFora = (e) => {
      if (!caixa.current?.contains(e.target) && !botao.current?.contains(e.target)) {
        fechar();
      }
    };
    const teclou = (e) => {
      if (e.key === "Escape") {
        fechar();
        // O foco volta para os tres pontinhos, e nao para o `span` que os
        // envolve: quem fechou pelo teclado continua de onde estava.
        botao.current?.querySelector("button")?.focus();
      }
    };

    document.addEventListener("mousedown", clicouFora);
    window.addEventListener("keydown", teclou);
    // Na captura para pegar a rolagem de QUALQUER container, nao so a da
    // janela: a lista esta em coordenadas fixas e descolaria da linha.
    window.addEventListener("scroll", fechar, true);
    window.addEventListener("resize", fechar);

    return () => {
      document.removeEventListener("mousedown", clicouFora);
      window.removeEventListener("keydown", teclou);
      window.removeEventListener("scroll", fechar, true);
      window.removeEventListener("resize", fechar);
    };
  }, [aberto]);

  return (
    <div className="menu-acoes">
      <span ref={botao} className="menu-acoes__alvo">
        <BotaoIcone
          titulo={titulo}
          tamanho="sm"
          onClick={() => definirAberto((estava) => !estava)}
        >
          <TresPontos />
        </BotaoIcone>
      </span>

      {aberto && (
        <div
          ref={caixa}
          className="menu-acoes__lista"
          role="menu"
          aria-label={titulo}
          // Escondida ate o efeito de layout medir a altura e decidir se o
          // menu abre para baixo ou para cima — visivel antes disso, ele
          // piscaria no canto errado.
          style={{ visibility: "hidden" }}
        >
          {visiveis.map((item) => (
            <button
              key={item.rotulo}
              type="button"
              role="menuitem"
              className={`menu-acoes__item${item.perigo ? " menu-acoes__item--perigo" : ""}`}
              disabled={item.disabled}
              onClick={() => {
                definirAberto(false);
                item.aoEscolher();
              }}
            >
              {item.rotulo}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
