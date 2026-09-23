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

// Instituicoes
export const listarInstituicoes = () => api.get("/instituicoes");
export const criarInstituicao = (dados) => api.post("/instituicoes", dados);
export const editarInstituicao = (id, dados) => api.patch(`/instituicoes/${id}`, dados);

// Perfis
export const listarPerfis = () => api.get("/perfis");
