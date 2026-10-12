/** A programacao do dia do evento: o modelo de 2025 e as contas do quadro. */

export const NUCLEOS = ["A", "B", "C", "D"];

/** O quadro de 2025, de onde a coordenacao parte para ajustar o ano. */
export const MODELO_2025 = {
  atividades: [
    { nome: "Chegada / Café / Louvor", cor: "#153377" },
    { nome: "Oração inicial / Adoração", cor: "#153377" },
    { nome: "Dança de abertura", cor: "#153377" },
    { nome: "Infláveis G", cor: "#e67e22" },
    { nome: "Infláveis P", cor: "#1e63e9" },
    { nome: "Infláveis P (lanche)", cor: "#1e63e9" },
    { nome: "Parquinho", cor: "#43a047" },
    { nome: "Refeitório", cor: "#c0392b" },
    { nome: "Teatro", cor: "#c2185b" },
    { nome: "Mágico", cor: "#1a237e" },
    { nome: "Peça de Natal", cor: "#1a237e" },
    { nome: "Lanche | Marujinho", cor: "#8e44ad" },
  ],
  blocos: [
    {
      titulo: "Abertura",
      horarios: [
        { inicio: "07:30", fim: "09:20", modo: "todos", atividade: "Chegada / Café / Louvor", nucleos: {} },
        { inicio: "09:20", fim: "09:50", modo: "todos", atividade: "Oração inicial / Adoração", nucleos: {} },
        { inicio: "09:50", fim: "10:00", modo: "todos", atividade: "Dança de abertura", nucleos: {} },
      ],
    },
    {
      titulo: "Rodízios - Manhã",
      horarios: [
        { inicio: "10:10", fim: "10:50", modo: "por_nucleo", atividade: null,
          nucleos: { A: "Infláveis G", B: "Infláveis G", C: "Infláveis P", D: "Parquinho" } },
        { inicio: "11:05", fim: "11:30", modo: "por_nucleo", atividade: null,
          nucleos: { A: "Refeitório", B: "Infláveis G", C: "Infláveis P (lanche)", D: "Infláveis G" } },
        { inicio: "11:45", fim: "12:10", modo: "por_nucleo", atividade: null,
          nucleos: { A: "Parquinho", B: "Refeitório", C: "Infláveis G", D: "Infláveis P (lanche)" } },
        { inicio: "12:25", fim: "12:50", modo: "por_nucleo", atividade: null,
          nucleos: { A: "Infláveis P", B: "Parquinho", C: "Refeitório", D: "Infláveis G" } },
        { inicio: "13:05", fim: "13:30", modo: "por_nucleo", atividade: null,
          nucleos: { A: "Infláveis G", B: "Infláveis P", C: "Parquinho", D: "Refeitório" } },
      ],
    },
    {
      titulo: "Rodízios - Tarde",
      horarios: [
        { inicio: "13:45", fim: "14:15", modo: "por_nucleo", atividade: null,
          nucleos: { A: "Teatro", B: "Infláveis P", C: "Infláveis G", D: "Teatro" } },
        { inicio: "14:30", fim: "15:00", modo: "por_nucleo", atividade: null,
          nucleos: { A: "Infláveis P", B: "Teatro", C: "Teatro", D: "Infláveis G" } },
        { inicio: "15:05", fim: "15:35", modo: "todos", atividade: "Mágico", nucleos: {} },
        { inicio: "15:35", fim: "15:50", modo: "todos", atividade: "Peça de Natal", nucleos: {} },
        { inicio: "15:50", fim: "16:00", modo: "todos", atividade: "Lanche | Marujinho", nucleos: {} },
      ],
    },
  ],
};

export const QUADRO_VAZIO = {
  atividades: [],
  blocos: [{ titulo: "Abertura", horarios: [] }],
};

/** "10:10" -> 610. */
export function minutos(hora) {
  const [h, m] = (hora ?? "").split(":").map(Number);
  return Number.isFinite(h) && Number.isFinite(m) ? h * 60 + m : null;
}

/** 610 -> "10:10". */
export function hora(min) {
  const h = Math.floor(min / 60) % 24;
  const m = min % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** Quanto dura: "00:40". */
/** Um tempo escrito como se fala: "40 min", "1h", "1h 10min". */
export function tempoEscrito(m) {
  if (!Number.isFinite(m) || m <= 0) return "—";
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const resto = m % 60;
  return resto ? `${h}h ${resto}min` : `${h}h`;
}

export function duracao(inicio, fim) {
  return tempoEscrito(minutos(fim) - minutos(inicio));
}

/** Os minutos de folga entre um horario e o seguinte (o "15 min" do quadro). */
export function intervalo(anterior, seguinte) {
  if (!anterior || !seguinte) return 0;
  const d = minutos(seguinte.inicio) - minutos(anterior.fim);
  return Number.isFinite(d) && d > 0 ? d : 0;
}

/** A cor de uma atividade pelo nome; sem cadastro, o azul do texto. */
export function corDe(nome, atividades) {
  if (!nome) return null;
  const limpo = nome.trim().toLowerCase();
  return atividades.find((a) => a.nome.trim().toLowerCase() === limpo)?.cor ?? null;
}

/** Quanto tempo cada nucleo passa em cada atividade dos rodizios — a conta
 *  que a planilha fazia embaixo, para ver se o rodizio esta justo. */
export function tempoPorNucleo(blocos) {
  const conta = {};
  for (const b of blocos) {
    for (const h of b.horarios) {
      if (h.modo !== "por_nucleo") continue;
      const d = minutos(h.fim) - minutos(h.inicio);
      if (!(d > 0)) continue;
      for (const n of NUCLEOS) {
        const at = h.nucleos?.[n]?.trim();
        if (!at) continue;
        conta[at] ??= Object.fromEntries(NUCLEOS.map((x) => [x, 0]));
        conta[at][n] += d;
      }
    }
  }
  return conta;
}
