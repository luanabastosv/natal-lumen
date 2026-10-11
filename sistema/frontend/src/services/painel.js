import { api } from "./api.js";

export const buscarRelatorio = (edicaoId) => api.get(`/painel/${edicaoId}`);

/** A equipe da edicao e o que cada um fez. So a coordenacao geral. */
export const buscarAtividade = (edicaoId) => api.get(`/painel/${edicaoId}/atividade`);

/** As acoes de uma pessoa, das mais novas para as mais antigas, de 50 em 50. */
export const buscarAtividadeDaPessoa = (edicaoId, usuarioId, antes) =>
  api.get(
    `/painel/${edicaoId}/atividade/${usuarioId}${antes ? `?antes=${antes}` : ""}`,
  );
