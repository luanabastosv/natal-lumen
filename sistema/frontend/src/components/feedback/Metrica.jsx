/** Um numero do painel, em tile compacto.
 *
 * E o `Numero` apertado: mesmo conteudo, um terco da altura. A diferenca nao
 * e so de estilo — quatro destes cabem numa linha, e e isso que tira o scroll
 * do painel. O `Numero` continua existindo para onde houver espaco de sobra.
 *
 * A barra embaixo NAO e um grafico: e a escala do numero. O numero e a
 * resposta; a barra so diz o tamanho dela contra o total. Sem `de`, ela some
 * — uma barra cheia sem total nao informa nada.
 */

const TONS = {
  cesta: "metrica__trilho--cesta",
  festa: "metrica__trilho--festa",
  neutro: "",
};

export default function Metrica({ rotulo, valor, de, nota, tom = "neutro", destaque }) {
  const parte = de > 0 ? Math.min(100, Math.round((valor / de) * 100)) : null;

  return (
    <div className={`metrica ${destaque ? "metrica--destaque" : ""}`.trim()}>
      <span className="metrica__rotulo">{rotulo}</span>
      <span className="metrica__valor">
        {valor}
        {de != null && <span className="metrica__de">/{de}</span>}
      </span>
      {parte !== null && (
        <div
          className="metrica__trilho"
          role="img"
          aria-label={`${rotulo}: ${valor} de ${de}`}
        >
          <div
            className={`metrica__parte ${TONS[tom] ?? ""}`.trim()}
            style={{ width: `${parte}%` }}
          />
        </div>
      )}
      {nota && <span className="metrica__nota">{nota}</span>}
    </div>
  );
}
