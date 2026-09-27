import { api } from "./api.js";

const API_URL = import.meta.env.VITE_API_URL ?? "/acesso/api";

function csrf() {
  const bruto = document.cookie
    .split("; ")
    .find((c) => c.startsWith("nl_csrf="))
    ?.split("=")[1];
  return bruto ? decodeURIComponent(bruto) : null;
}

export function listarCartoes(filtros = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filtros)) {
    if (v !== "" && v !== null && v !== undefined) p.set(k, v);
  }
  return api.get(`/cartoes?${p}`);
}

/** Sobe a pilha de cartoes e recebe a previa. Nao grava nada ainda.
 *
 * Nao passa pelo api.js porque ele so manda JSON — e num FormData quem tem de
 * escrever o Content-Type e o navegador, que e o unico que sabe a fronteira
 * entre as partes.
 */
export async function subirLoteDeCartoes({ arquivos, tipo, edicaoId }) {
  const dados = new FormData();
  for (const arquivo of arquivos) dados.append("arquivos", arquivo);
  dados.append("tipo", tipo);
  dados.append("edicao_id", edicaoId);

  const token = csrf();
  const resposta = await fetch(`${API_URL}/cartoes/lote`, {
    method: "POST",
    credentials: "include",
    headers: token ? { "X-CSRF-Token": token } : {},
    body: dados,
  });

  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const detalhe = corpo?.detail;
    throw new Error(
      typeof detalhe === "string" ? detalhe : "Não foi possível ler os cartões.",
    );
  }
  return corpo;
}

export const confirmarLote = (id) => api.post(`/cartoes/lote/${id}/confirmar`);

export const marcarEnviados = (cartoes) => api.post("/cartoes/enviados", { cartoes });

/** A imagem só sai por rota autenticada — nunca é servida como arquivo estático. */
export const urlDaImagem = (id) => `${API_URL}/cartoes/${id}/imagem`;
