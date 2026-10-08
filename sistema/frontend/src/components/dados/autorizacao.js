/** As perguntas da autorizacao e a regra de quando elas estao respondidas.
 *
 * Separadas do componente porque a tela de cartoes tambem as usa: para mostrar
 * as respostas gravadas e para saber se a pilha ja pode ser guardada.
 */
export const PERGUNTAS = [
  {
    sim: "necessidade_especial",
    qual: "necessidade_especial_qual",
    pergunta: "Possui alguma necessidade especial?",
  },
  {
    sim: "restricao_alimentar",
    qual: "restricao_alimentar_qual",
    pergunta: "Possui alguma alergia ou restrição alimentar?",
  },
  { sim: "tem_observacao", qual: "observacao", pergunta: "Alguma observação?" },
];

/** Tudo "Nao": e o caso de quase toda crianca, e o monitor so mexe no que o
 *  papel diz diferente. */
export const RESPOSTAS_PADRAO = Object.fromEntries(
  PERGUNTAS.flatMap((p) => [
    [p.sim, false],
    [p.qual, ""],
  ]),
);

export function respostasCompletas(r = RESPOSTAS_PADRAO) {
  return PERGUNTAS.every((p) => r[p.sim] === false || (r[p.sim] === true && r[p.qual].trim()));
}

