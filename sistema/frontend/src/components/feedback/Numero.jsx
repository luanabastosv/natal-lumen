/** Um numero do painel, com barra de progresso quando ha um total. */
export default function Numero({ rotulo, valor, de, nota, tom }) {
  const parte = de ? Math.min(100, Math.round((valor / de) * 100)) : null;

  return (
    <div className="numero">
      <span className="numero__rotulo">{rotulo}</span>
      <span className="numero__valor">
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
