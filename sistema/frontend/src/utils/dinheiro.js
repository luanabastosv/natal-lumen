/** Formatacoes usadas em varias telas. */

export function dinheiro(valor) {
  return Number(valor).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

export function formatarData(iso) {
  if (!iso) return "—";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

/**
 * O dia do evento como as pessoas o chamam. A edicao batiza cada dia
 * ("Sabado", "Domingo") e e assim que a equipe se localiza; a data so aparece
 * quando o dia ficou sem descricao.
 */
export function rotuloDia(data, descricao) {
  return descricao?.trim() || formatarData(data);
}

export function formatarDataHora(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}
