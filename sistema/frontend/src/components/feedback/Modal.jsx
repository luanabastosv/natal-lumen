import { useEffect, useRef } from "react";

/** Janela pequena sobre a tela. Esc e o fundo fecham.
 *
 * Nao e um modal de pagina inteira: serve para olhar um detalhe sem perder o
 * lugar na planilha.
 */
export default function Modal({ titulo, aoFechar, children, rodape }) {
  const botaoFechar = useRef(null);

  useEffect(() => {
    botaoFechar.current?.focus();

    const aoTeclar = (e) => {
      if (e.key === "Escape") aoFechar();
    };
    window.addEventListener("keydown", aoTeclar);

    // Trava a rolagem do fundo enquanto a janela esta aberta.
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      window.removeEventListener("keydown", aoTeclar);
      document.body.style.overflow = antes;
    };
  }, [aoFechar]);

  return (
    <div className="modal-fundo" onMouseDown={(e) => e.target === e.currentTarget && aoFechar()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={titulo}>
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
