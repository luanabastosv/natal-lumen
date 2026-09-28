/** Uma barra rotulada: quanto de `de` ja esta feito.
 *
 * O rotulo e o numero ficam SEMPRE visiveis ao lado da barra, e nao so na cor
 * dela: cesta e festa se distinguem pelo nome escrito, nao pelo tom. Quem nao
 * separa as duas cores le a linha do mesmo jeito.
 */
export default function Progresso({ rotulo, valor, de, tom = "cesta" }) {
  const parte = de > 0 ? Math.min(100, Math.round((valor / de) * 100)) : 0;

  return (
    <div className="progresso">
      <span className="progresso__rotulo">{rotulo}</span>
      <div
        className="progresso__trilho"
        role="img"
        aria-label={`${rotulo}: ${valor} de ${de}`}
      >
        {parte > 0 && (
          <div
            className={`progresso__marca progresso__marca--${tom}`}
            style={{ width: `${parte}%` }}
          />
        )}
      </div>
      <span className="progresso__valor">
        {valor}
        <span className="progresso__de">/{de}</span>
      </span>
    </div>
  );
}
