/** A cor de cada dia do evento. */

/** Sem acento e sem caixa, para "Sábado" e "sabado" caírem no mesmo tom. */
function normalizar(texto) {
  return (texto ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

/**
 * Sabado e domingo tem tom fixo: sao os dias que uma edicao usa de verdade e
 * precisam ser inconfundiveis entre si, em qualquer cidade. Qualquer outro
 * nome cai num tom tirado do proprio texto — estavel, para o mesmo dia nao
 * trocar de cor de uma tela para outra.
 *
 * O numero vira a classe .dia--N, que guarda o fundo da etiqueta e a cor do
 * pontinho da aba (ver base.css).
 */
export function tomDoDia(descricao) {
  const texto = normalizar(descricao);
  if (!texto) return 0;
  if (texto.includes("sabado")) return 1;
  if (texto.includes("domingo")) return 2;
  let soma = 0;
  for (let i = 0; i < texto.length; i += 1) soma += texto.charCodeAt(i);
  return 3 + (soma % 2);
}
