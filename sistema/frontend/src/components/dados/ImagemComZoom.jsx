import { useRef, useState } from "react";

const PASSO = 0.5;
const MAXIMO = 4;

/** A imagem do cartao ou da autorizacao, com zoom.
 *
 * A autorizacao e um formulario escrito a mao pelo responsavel — letra
 * pequena, as vezes apagada —, e a imagem inteira cabendo na janela nao se le.
 * Os botoes ficam por cima da imagem, no canto: mais, menos e voltar ao
 * tamanho que cabe.
 *
 * Com zoom, a imagem se ARRASTA com o mouse (segurar e mover), como em todo
 * visualizador. No celular o dedo ja rola a moldura sozinho, e a pinca do
 * proprio celular continua valendo — por isso o arrasto aqui e so do mouse.
 *
 * Remonta a cada imagem nova (quem chama passa `key`), e o zoom volta a 1.
 */
export default function ImagemComZoom({ src, alt }) {
  const [escala, definirEscala] = useState(1);
  const [arrastando, definirArrastando] = useState(false);
  const moldura = useRef(null);
  const inicio = useRef(null);
  const ampliada = escala > 1;

  function comecar(e) {
    if (!ampliada || e.pointerType !== "mouse" || e.button !== 0) return;
    e.preventDefault();
    inicio.current = {
      x: e.clientX,
      y: e.clientY,
      esquerda: moldura.current.scrollLeft,
      topo: moldura.current.scrollTop,
    };
    moldura.current.setPointerCapture(e.pointerId);
    definirArrastando(true);
  }

  function mover(e) {
    if (!inicio.current) return;
    moldura.current.scrollLeft = inicio.current.esquerda - (e.clientX - inicio.current.x);
    moldura.current.scrollTop = inicio.current.topo - (e.clientY - inicio.current.y);
  }

  function soltar(e) {
    if (!inicio.current) return;
    inicio.current = null;
    moldura.current.releasePointerCapture?.(e.pointerId);
    definirArrastando(false);
  }

  return (
    <div
      className={`imagem-zoom ${ampliada ? "imagem-zoom--ampliada" : ""} ${
        arrastando ? "imagem-zoom--arrastando" : ""
      }`}
    >
      <div
        ref={moldura}
        className="imagem-zoom__moldura"
        onPointerDown={comecar}
        onPointerMove={mover}
        onPointerUp={soltar}
        onPointerCancel={soltar}
      >
        <img
          className="imagem-zoom__img"
          src={src}
          alt={alt}
          draggable={false}
          style={ampliada ? { height: `${escala * 100}%` } : undefined}
          // Duplo clique alterna entre caber e o dobro: o gesto que todo
          // visualizador de imagem tem.
          onDoubleClick={() => definirEscala(ampliada ? 1 : 2)}
        />
      </div>
      <div className="imagem-zoom__controles" role="group" aria-label="Zoom da imagem">
        <button
          type="button"
          onClick={() => definirEscala((v) => Math.max(1, v - PASSO))}
          disabled={!ampliada}
          aria-label="Diminuir o zoom"
          title="Diminuir"
        >
          −
        </button>
        <button
          type="button"
          className="imagem-zoom__nivel"
          onClick={() => definirEscala(1)}
          disabled={!ampliada}
          title="Voltar ao tamanho da janela"
        >
          {Math.round(escala * 100)}%
        </button>
        <button
          type="button"
          onClick={() => definirEscala((v) => Math.min(MAXIMO, v + PASSO))}
          disabled={escala >= MAXIMO}
          aria-label="Aumentar o zoom"
          title="Aumentar"
        >
          +
        </button>
      </div>
    </div>
  );
}
