/** As duas marcas de caneta do sistema: a onda e os riscos.
 *
 * Nao sao arquivo. Sao dois paths curtos, como os icones, e pelo mesmo motivo:
 * elas aparecem em praticamente toda tela, e nenhuma delas pode custar um
 * pedido de rede num celular no meio do evento. Indo inline, ainda herdam a
 * cor de quem as contem — a mesma onda serve sobre papel e sobre a lateral
 * navy sem nenhuma regra extra.
 *
 *   ~   onda    uma pausa, um respiro. Divide.
 *   //  riscos  atencao, brilho. Aponta.
 *
 * Uma marca por bloco. Duas ondas na mesma tela deixam de ser pontuacao e
 * viram padrao — e padrao e textura, que tem outro lugar.
 *
 * E decorativo: quem usa leitor de tela ouve o texto do lado, nunca isto.
 */

// Proporcao de cada desenho, para a altura sair do tamanho sem deformar.
const FORMAS = {
  onda: {
    viewBox: "0 0 200 100",
    proporcao: 100 / 200,
    d: "M30 72 C22 40 40 22 66 28 C92 34 110 62 132 74 C154 86 174 78 176 48",
    traco: 13,
  },
  riscos: {
    viewBox: "0 0 100 130",
    proporcao: 130 / 100,
    d: "M26 34 L46 112 M64 14 L82 88",
    traco: 14,
  },
};

export default function Rabisco({ tipo = "onda", tamanho = 40, className = "" }) {
  const forma = FORMAS[tipo] ?? FORMAS.onda;

  return (
    <svg
      className={`rabisco ${className}`.trim()}
      width={tamanho}
      height={Math.round(tamanho * forma.proporcao)}
      viewBox={forma.viewBox}
      fill="none"
      stroke="currentColor"
      strokeWidth={forma.traco}
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d={forma.d} />
    </svg>
  );
}
