import { api } from "./api.js";

// Cidades
export const listarCidades = () => api.get("/cidades");
export const criarCidade = (dados) => api.post("/cidades", dados);
export const editarCidade = (id, dados) => api.patch(`/cidades/${id}`, dados);

/* Apagar cidade, edicao ou instituicao leva junto tudo que pendura nelas.
   Por isso vem sempre em dois passos: perguntar o tamanho do estrago, mostrar
   no modal, e so entao apagar. O `confirmar=true` e o que a API exige para
   executar — sem ele, ela recusa e devolve a conta. */
export const dependenciasDaCidade = (id) => api.get(`/cidades/${id}/dependencias`);
export const apagarCidade = (id) => api.delete(`/cidades/${id}?confirmar=true`);

// Edicoes
export const listarEdicoes = () => api.get("/edicoes");
export const criarEdicao = (dados) => api.post("/edicoes", dados);
export const editarEdicao = (id, dados) => api.patch(`/edicoes/${id}`, dados);
export const dependenciasDaEdicao = (id) => api.get(`/edicoes/${id}/dependencias`);
export const apagarEdicao = (id) => api.delete(`/edicoes/${id}?confirmar=true`);

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
export const dependenciasDaInstituicao = (id) =>
  api.get(`/instituicoes/${id}/dependencias`);
export const apagarInstituicao = (id) =>
  api.delete(`/instituicoes/${id}?confirmar=true`);

// Perfis
export const listarPerfis = () => api.get("/perfis");
