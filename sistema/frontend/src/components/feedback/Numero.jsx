/** Um numero do painel, com barra de progresso quando ha um total. */
export default function Numero({ rotulo, valor, de, nota }) {
  const parte = de ? Math.min(100, Math.round((valor / de) * 100)) : null;

  return (
    <div className="numero">
      <span className="numero__rotulo">{rotulo}</span>
      <span className="numero__valor">
        {valor}
        {de != null && <span style={{ fontSize: 18, opacity: 0.5 }}> / {de}</span>}
      </span>
      {nota && <span className="numero__nota">{nota}</span>}
      {parte !== null && (
        <div className="barra">
          <div
            className={`barra__preenchida ${parte === 100 ? "barra__preenchida--completa" : ""}`}
            style={{ width: `${parte}%` }}
          />
        </div>
      )}
    </div>
  );
}
