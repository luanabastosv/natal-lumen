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

function porcento(valor, de) {
  return de > 0 ? Math.min(100, Math.round((valor / de) * 100)) : 0;
}

/** `partes`: um arco por serie, desenhados na ordem — o ultimo fica por cima.
 *  E assim que a festa entra: o arco da cesta embaixo, o da festa sobre ele,
 *  os dois partindo do topo. Com uma parte so, o centro diz a fracao; com
 *  duas, o porcento de cada uma, cada um com o nome escrito (a cor nao e a
 *  unica pista). */
export default function Anel({ partes, rotulo, nota }) {
  const arcos = partes.map((p) => ({ ...p, parte: porcento(p.valor, p.de) }));
  const unica = arcos.length === 1 ? arcos[0] : null;
  const descricao = arcos
    .map((a) => `${a.nome ?? rotulo}: ${a.valor} de ${a.de}, ${a.parte}%`)
    .join("; ");

  return (
    <div className="anel">
      <div className="anel__grafico">
        <svg
          width={TAMANHO}
          height={TAMANHO}
          viewBox={`0 0 ${TAMANHO} ${TAMANHO}`}
          role="img"
          aria-label={descricao}
        >
          <circle
            className="anel__trilho"
            cx={TAMANHO / 2}
            cy={TAMANHO / 2}
            r={RAIO}
            fill="none"
            strokeWidth={TRACO}
          />
          {/* O arco comeca no topo: -90 graus. Sem isso ele abriria as tres
              horas, e a leitura de "quanto ja foi" deixa de ser imediata. */}
          {arcos.map((a) => {
            const preenchido = (a.parte / 100) * VOLTA;
            return a.parte > 0 ? (
              <circle
                key={a.tom}
                className={`anel__parte anel__parte--${a.tom}`}
                cx={TAMANHO / 2}
                cy={TAMANHO / 2}
                r={RAIO}
                fill="none"
                strokeWidth={TRACO}
                strokeLinecap="round"
                strokeDasharray={`${preenchido} ${VOLTA - preenchido}`}
                transform={`rotate(-90 ${TAMANHO / 2} ${TAMANHO / 2})`}
              />
            ) : null;
          })}
        </svg>
        <div className="anel__centro">
          {unica ? (
            <>
              <span className="anel__numero">{unica.parte}%</span>
              <span className="anel__fracao">
                {unica.valor} de {unica.de}
              </span>
            </>
          ) : (
            arcos.map((a) => (
              <span key={a.tom} className="anel__serie">
                <span className="anel__numero anel__numero--menor">{a.parte}%</span>
                <span className={`anel__nome anel__nome--${a.tom}`}>{a.nome}</span>
              </span>
            ))
          )}
        </div>
      </div>
      <span className="anel__rotulo">{rotulo}</span>
      {nota && <span className="anel__nota">{nota}</span>}
    </div>
  );
}
