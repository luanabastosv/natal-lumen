import { api } from "./api.js";

/** Cartoes, autorizacoes, cuidados e nucleos de cada instituicao da edicao. */
export const buscarPainelMonitoria = (edicaoId) => api.get(`/monitoria/${edicaoId}/painel`);

/** Grava nucleo e cor da bata de varias instituicoes de uma vez. */
export const salvarNucleos = (edicaoId, instituicoes) =>
  api.put(`/monitoria/${edicaoId}/nucleos`, { instituicoes });
