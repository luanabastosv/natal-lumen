/**
 * A crianca desistiu de ir ao evento.
 *
 * Uma etiqueta so para o sistema inteiro: a desistente aparece na planilha, na
 * ficha do padrinho, nos cartoes, no check-in — e em todo lugar ela tem de ser
 * reconhecida do mesmo jeito, senao o padrinho continua sendo cobrado e o
 * cartao continua sendo esperado de quem nao vai.
 */
export default function EtiquetaDesistente({ className = "" }) {
  return (
    <span
      className={`etiqueta etiqueta--parado ${className}`.trim()}
      title="Esta criança desistiu de ir ao evento"
    >
      Desistente
    </span>
  );
}
