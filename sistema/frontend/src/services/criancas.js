import { api } from "./api.js";

const API_URL = import.meta.env.VITE_API_URL ?? "/acesso/api";

export function listarCriancas(filtros = {}) {
  const parametros = new URLSearchParams();
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor !== "" && valor !== null && valor !== undefined) {
      parametros.set(chave, valor);
    }
  }
  return api.get(`/criancas?${parametros}`);
}

export const criarCrianca = (dados) => api.post("/criancas", dados);
export const editarCrianca = (id, dados) => api.patch(`/criancas/${id}`, dados);
export const apagarCrianca = (id) => api.delete(`/criancas/${id}`);

/** Envio de arquivo: nao passa pelo api.js, que so manda JSON. */
export async function analisarPlanilha({ arquivo, edicaoId, instituicaoId }) {
  const dados = new FormData();
  dados.append("arquivo", arquivo);
  dados.append("edicao_id", edicaoId);
  if (instituicaoId) dados.append("instituicao_id", instituicaoId);

  const csrf = document.cookie
    .split("; ")
    .find((c) => c.startsWith("nl_csrf="))
    ?.split("=")[1];

  const resposta = await fetch(`${API_URL}/criancas/importar`, {
    method: "POST",
    credentials: "include",
    headers: csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {},
    body: dados,
  });

  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const detalhe = corpo?.detail;
    throw new Error(
      typeof detalhe === "string" ? detalhe : "Não foi possível ler a planilha.",
    );
  }
  return corpo;
}

export const confirmarImportacao = (id) =>
  api.post(`/criancas/importar/${id}/confirmar`);
