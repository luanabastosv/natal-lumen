import { useEffect, useRef } from "react";

/** Janela sobre a tela. Esc e o fundo fecham.
 *
 * Nao e um modal de pagina inteira: serve para olhar um detalhe sem perder o
 * lugar na planilha.
 *
 * Dois tamanhos, e a escolha e sobre o CONTEUDO, nao sobre a importancia:
 *
 * - `padrao` — formulario. O conteudo e fixo (N campos), entao a altura pode
 *   acompanhar.
 * - `grande` — ficha. O conteudo varia e muda com a janela aberta (apadrinhar
 *   mais uma crianca, desfazer outra). A moldura fica FIXA e quem rola e o
 *   corpo: se a altura acompanhasse, a janela pularia embaixo do ponteiro a
 *   cada acao.
 * - `largo` — visualizador. Largura de ficha, altura do conteudo. E o caso do
 *   cartao aberto para olhar: nada ali muda enquanto a janela esta aberta,
 *   entao travar a altura so deixaria um vao embaixo da imagem.
 */
export default function Modal({
  titulo,
  // Eyebrow acima do titulo — "Nome do padrinho:". Numa ficha, o titulo e um
  // nome proprio solto, e nome proprio sozinho nao diz de que ele e nome.
  rotulo,
  aoFechar,
  children,
  rodape,
  tamanho = "padrao",
}) {
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
        className={`modal ${tamanho === "padrao" ? "" : `modal--${tamanho}`}`}
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
      >
        <div className="modal__topo">
          <div className="modal__identificacao">
            {rotulo && <span className="modal__rotulo">{rotulo}</span>}
            <h2 className="modal__titulo">{titulo}</h2>
          </div>
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
