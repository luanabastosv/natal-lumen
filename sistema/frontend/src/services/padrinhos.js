import { api } from "./api.js";

function comFiltros(caminho, filtros = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filtros)) {
    if (v !== "" && v !== null && v !== undefined) p.set(k, v);
  }
  return api.get(`${caminho}?${p}`);
}

export const listarPadrinhos = (filtros) => comFiltros("/padrinhos", filtros);
export const detalharPadrinho = (id) => api.get(`/padrinhos/${id}`);
export const criarPadrinho = (dados) => api.post("/padrinhos", dados);
export const editarPadrinho = (id, dados) => api.patch(`/padrinhos/${id}`, dados);

export const criarApadrinhamento = (dados) => api.post("/apadrinhamentos", dados);
export const editarApadrinhamento = (id, dados) => api.patch(`/apadrinhamentos/${id}`, dados);
export const apagarApadrinhamento = (id) => api.delete(`/apadrinhamentos/${id}`);

export const listarPagamentos = (filtros) => comFiltros("/pagamentos", filtros);
export const criarPagamento = (dados) => api.post("/pagamentos", dados);
export const editarPagamento = (id, dados) => api.patch(`/pagamentos/${id}`, dados);
export const apagarPagamento = (id) => api.delete(`/pagamentos/${id}`);
