import { api } from "./api.js";

// Cidades
export const listarCidades = () => api.get("/cidades");
export const criarCidade = (dados) => api.post("/cidades", dados);
export const editarCidade = (id, dados) => api.patch(`/cidades/${id}`, dados);

// Edicoes
export const listarEdicoes = () => api.get("/edicoes");
export const criarEdicao = (dados) => api.post("/edicoes", dados);
export const editarEdicao = (id, dados) => api.patch(`/edicoes/${id}`, dados);

// Dias do evento
export const listarDias = (edicaoId) => api.get(`/edicoes/${edicaoId}/dias`);
export const criarDia = (edicaoId, dados) => api.post(`/edicoes/${edicaoId}/dias`, dados);
export const apagarDia = (edicaoId, diaId) =>
  api.delete(`/edicoes/${edicaoId}/dias/${diaId}`);

/** O dia e da instituicao: definir aqui move todas as criancas dela. */
export const definirDiaDaInstituicao = (edicaoId, instituicaoId, diaEventoId) =>
  api.put(`/edicoes/${edicaoId}/instituicoes/${instituicaoId}/dia`, {
    dia_evento_id: diaEventoId,
  });

// Instituicoes
export const listarInstituicoes = (filtros = {}) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filtros)) {
    if (v !== "" && v !== null && v !== undefined) p.set(k, v);
  }
  const consulta = p.toString();
  return api.get(`/instituicoes${consulta ? `?${consulta}` : ""}`);
};
export const criarInstituicao = (dados) => api.post("/instituicoes", dados);
export const editarInstituicao = (id, dados) => api.patch(`/instituicoes/${id}`, dados);

// Perfis
export const listarPerfis = () => api.get("/perfis");
