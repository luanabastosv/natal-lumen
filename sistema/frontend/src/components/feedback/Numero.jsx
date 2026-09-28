/** Um numero do painel, com barra de progresso quando ha um total.
 *
 * `moeda` nao muda o conteudo — o valor ja chega formatado — so o tamanho:
 * "R$ 12.480,00" tem tres vezes a largura de "1500" e estouraria o card nos
 * 30px do numero cru. `negativo` e o saldo no vermelho, o unico caso em que
 * este numero e uma ma noticia.
 */
export default function Numero({ rotulo, valor, de, nota, tom, moeda, negativo }) {
  const parte = de ? Math.min(100, Math.round((valor / de) * 100)) : null;

  return (
    <div className={`numero ${moeda ? "numero--dinheiro" : ""}`.trim()}>
      <span className="numero__rotulo">{rotulo}</span>
      <span className={`numero__valor ${negativo ? "numero__valor--negativo" : ""}`.trim()}>
        {valor}
        {de != null && <span className="numero__de"> / {de}</span>}
      </span>
      {nota && <span className="numero__nota">{nota}</span>}
      {parte !== null && (
        <div className="barra">
          <div
            /* Com tom definido a cor e a da serie (cesta ou festa) do inicio
               ao fim: mudar de cor ao completar trocaria a identidade da
               barra justamente no momento em que ela vira referencia. */
            className={[
              "barra__preenchida",
              tom
                ? `barra__preenchida--${tom}`
                : parte === 100 && "barra__preenchida--completa",
            ].filter(Boolean).join(" ")}
            style={{ width: `${parte}%` }}
          />
        </div>
      )}
    </div>
  );
}
