import { useEffect, useRef } from "react";

/* Quem esta por cima. Uma janela pode abrir outra — a conferencia dos cartoes
   abre por cima do envio —, e o Esc tem de fechar SO a de cima. Com um ouvinte
   global por janela, sem esta pilha, um Esc fechava as duas de uma vez e a
   pessoa perdia o trabalho de tras junto com o da frente. */
const abertas = [];

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
  // Sem a faixa de topo (rotulo, titulo e o X). E para a janela que nao abre
  // uma tarefa: o convite de oracao do dia, que nao tem o que ser fechado
  // "sem fazer" — a saida dele e o proprio botao de Amem. Um X ali convidaria
  // a descartar, que e o contrario do que a janela pede. `titulo` continua
  // obrigatorio: ele vira o aria-label, e um dialog sem nome nao se anuncia.
  cabecalho = true,
}) {
  const botaoFechar = useRef(null);
  const caixa = useRef(null);
  // A identidade desta janela na pilha. Um ref, e nao um valor de render: e a
  // MESMA janela do inicio ao fim, e e por ela que o Esc sabe quem esta na
  // frente.
  const eu = useRef({});

  // O foco vai UMA vez, ao abrir. Sem esta separacao o efeito dependia de
  // aoFechar — que chega como funcao nova a cada render — e roubava o foco a
  // cada tecla digitada num campo do formulario.
  useEffect(() => {
    // Num formulario, quem espera o foco e o primeiro campo, nao o botao de
    // fechar. Numa janela so de leitura, cai no fechar mesmo.
    const primeiro = caixa.current?.querySelector(
      "input:not([type=hidden]), select, textarea",
    );
    // Sem cabecalho nao ha botao de fechar; o foco cai na propria caixa,
    // senao ele ficaria para tras na pagina e o Tab sairia por baixo da janela.
    (primeiro ?? botaoFechar.current ?? caixa.current)?.focus();
  }, []);

  // Trava a rolagem do fundo enquanto a janela esta aberta.
  useEffect(() => {
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = antes;
    };
  }, []);

  // Entra na pilha ao abrir e sai ao fechar. Efeito proprio, sem dependencia:
  // tem de acontecer UMA vez, na ordem em que as janelas nasceram.
  useEffect(() => {
    const marca = eu.current;
    abertas.push(marca);
    return () => {
      const onde = abertas.indexOf(marca);
      if (onde !== -1) abertas.splice(onde, 1);
    };
  }, []);

  // Este pode reassinar a cada render sem incomodar ninguem: so troca o
  // ouvinte de tecla.
  useEffect(() => {
    const aoTeclar = (e) => {
      // So a janela de cima responde: as de baixo estao cobertas, e fechar o
      // que esta atras do que se esta olhando e perder trabalho sem aviso.
      if (e.key === "Escape" && abertas[abertas.length - 1] === eu.current) {
        aoFechar();
      }
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
        tabIndex={-1}
      >
        {cabecalho && (
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
        )}

        <div className="modal__corpo">{children}</div>

        {rodape && <div className="modal__rodape">{rodape}</div>}
      </div>
    </div>
  );
}
