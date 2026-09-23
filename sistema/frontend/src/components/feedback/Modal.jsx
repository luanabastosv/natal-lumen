import { useEffect, useRef } from "react";

/** Janela pequena sobre a tela. Esc e o fundo fecham.
 *
 * Nao e um modal de pagina inteira: serve para olhar um detalhe sem perder o
 * lugar na planilha.
 */
export default function Modal({ titulo, aoFechar, children, rodape }) {
  const botaoFechar = useRef(null);
  const caixa = useRef(null);

  // O foco vai UMA vez, ao abrir. Sem esta separacao o efeito dependia de
  // aoFechar — que chega como funcao nova a cada render — e roubava o foco a
  // cada tecla digitada num campo do formulario.
  useEffect(() => {
    // Num formulario, quem espera o foco e o primeiro campo, nao o botao de
    // fechar. Numa janela so de leitura, cai no fechar mesmo.
    const primeiro = caixa.current?.querySelector(
      "input:not([type=hidden]), select, textarea",
    );
    (primeiro ?? botaoFechar.current)?.focus();
  }, []);

  // Trava a rolagem do fundo enquanto a janela esta aberta.
  useEffect(() => {
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = antes;
    };
  }, []);

  // Este pode reassinar a cada render sem incomodar ninguem: so troca o
  // ouvinte de tecla.
  useEffect(() => {
    const aoTeclar = (e) => {
      if (e.key === "Escape") aoFechar();
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [aoFechar]);

  return (
    <div className="modal-fundo" onMouseDown={(e) => e.target === e.currentTarget && aoFechar()}>
      <div
        ref={caixa}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
      >
        <div className="modal__topo">
          <h2 className="modal__titulo">{titulo}</h2>
          <button
            ref={botaoFechar}
            type="button"
            className="modal__fechar"
            onClick={aoFechar}
            aria-label="Fechar"
          >
            ×
          </button>
        </div>

        <div className="modal__corpo">{children}</div>

        {rodape && <div className="modal__rodape">{rodape}</div>}
      </div>
    </div>
  );
}
