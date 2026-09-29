/** O anel de progresso: uma razao contra um limite, com o numero no meio.
 *
 * NAO e um grafico de pizza, e a diferenca importa. Pizza de duas fatias para
 * uma porcentagem e um dos erros classicos de visualizacao: as duas fatias
 * competem entre si quando so uma delas e a informacao. Isto aqui e um
 * MEDIDOR — trilho cheio, parte preenchida, numero grande no centro —, so que
 * desenhado em arco em vez de em barra. A forma e a mesma da barra do
 * `Progresso`; muda a geometria.
 *
 * O numero no centro e a resposta e fica em tipo grande. O anel e a escala.
 * Quem nao enxergar o arco le o numero do mesmo jeito.
 */

// 140, nao 168: e o anel que define a altura da linha da grade, e cada pixel
// dele vira espaco vazio dentro do cartao de barras ao lado.
const TAMANHO = 140;
const TRACO = 14;
const RAIO = (TAMANHO - TRACO) / 2;
const VOLTA = 2 * Math.PI * RAIO;

export default function Anel({ valor, de, rotulo, nota }) {
  const parte = de > 0 ? Math.min(100, Math.round((valor / de) * 100)) : 0;
  // O arco comeca no topo: -90 graus. Sem isso ele abriria as tres horas, e a
  // leitura de "quanto ja foi" deixa de ser imediata.
  const preenchido = (parte / 100) * VOLTA;

  return (
    <div className="anel">
      <div className="anel__grafico">
        <svg
          width={TAMANHO}
          height={TAMANHO}
          viewBox={`0 0 ${TAMANHO} ${TAMANHO}`}
          role="img"
          aria-label={`${rotulo}: ${valor} de ${de}, ${parte}%`}
        >
          <circle
            className="anel__trilho"
            cx={TAMANHO / 2}
            cy={TAMANHO / 2}
            r={RAIO}
            fill="none"
            strokeWidth={TRACO}
          />
          <circle
            className="anel__parte"
            cx={TAMANHO / 2}
            cy={TAMANHO / 2}
            r={RAIO}
            fill="none"
            strokeWidth={TRACO}
            strokeLinecap="round"
            strokeDasharray={`${preenchido} ${VOLTA - preenchido}`}
            transform={`rotate(-90 ${TAMANHO / 2} ${TAMANHO / 2})`}
          />
        </svg>
        <div className="anel__centro">
          <span className="anel__numero">{parte}%</span>
          <span className="anel__fracao">
            {valor} de {de}
          </span>
        </div>
      </div>
      <span className="anel__rotulo">{rotulo}</span>
      {nota && <span className="anel__nota">{nota}</span>}
    </div>
  );
}
