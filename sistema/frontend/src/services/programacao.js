import { api } from "./api.js";

/** A programacao do dia do evento da edicao. `existe: false` quando nao ha. */
export const buscarProgramacao = (edicaoId) => api.get(`/programacao/${edicaoId}`);

/** Grava o quadro inteiro de uma vez. */
export const salvarProgramacao = (edicaoId, dados) =>
  api.put(`/programacao/${edicaoId}`, dados);
