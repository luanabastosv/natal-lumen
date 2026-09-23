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

/** Envio de arquivo: nao passa pelo api.js, que so manda JSON. */
export async function analisarCartao({ arquivo, codigo, edicaoId }) {
  const dados = new FormData();
  dados.append("imagem", arquivo);
  dados.append("codigo", codigo);
  dados.append("edicao_id", edicaoId);

  const token = csrf();
  const resposta = await fetch(`${API_URL}/cartoes/analisar`, {
    method: "POST",
    credentials: "include",
    headers: token ? { "X-CSRF-Token": token } : {},
    body: dados,
  });

  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const detalhe = corpo?.detail;
    throw new Error(
      typeof detalhe === "string" ? detalhe : "Não foi possível analisar o cartão.",
    );
  }
  return corpo;
}

export const confirmarCartao = (dados) => api.post("/cartoes/confirmar", dados);
export const marcarEnviados = (cartoes) => api.post("/cartoes/enviados", { cartoes });

/** A imagem só sai por rota autenticada — nunca é servida como arquivo estático. */
export const urlDaImagem = (id) => `${API_URL}/cartoes/${id}/imagem`;
