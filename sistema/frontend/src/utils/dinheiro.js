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

/** O comeco do dia, para comparar datas por dia de calendario e nao por hora. */
function inicioDoDia(data) {
  return new Date(data.getFullYear(), data.getMonth(), data.getDate());
}

/**
 * Quanto tempo faz, em texto curto: "hoje", "ontem", "ha 3 dias", "em
 * 12/08/2026". Sai pronto para entrar numa frase depois de um verbo
 * ("Entrou ha 3 dias").
 *
 * A pergunta que isso responde e "essa pessoa anda usando o sistema?", e
 * proximidade responde melhor que data exata: "ha 3 dias" se le na hora, uma
 * data obriga a contar nos dedos. Passado um mes a conta relativa perde a graca
 * ("ha 7 meses" nao diz mais nada que "sumiu") e a data volta a ser mais util —
 * e por isso que ela reaparece no fim.
 */
export function tempoDesde(iso) {
  if (!iso) return null;

  const quando = new Date(iso);
  if (Number.isNaN(quando.getTime())) return null;

  const dias = Math.round(
    (inicioDoDia(new Date()) - inicioDoDia(quando)) / 86400000,
  );

  // Negativo e relogio adiantado de um lado ou do outro, nao viagem no tempo.
  if (dias <= 0) return "hoje";
  if (dias === 1) return "ontem";
  if (dias < 30) return `há ${dias} dias`;

  // Pela data local, e nao pelos 10 primeiros caracteres do ISO: o ISO vem em
  // UTC, e quem entrou as 21h daqui aparece no dia seguinte por lá.
  return `em ${quando.toLocaleDateString("pt-BR")}`;
}
