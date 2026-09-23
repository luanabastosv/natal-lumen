import { api } from "./api.js";

const API_URL = import.meta.env.VITE_API_URL ?? "/acesso/api";

function comFiltros(caminho, filtros = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filtros)) {
    if (v !== "" && v !== null && v !== undefined) p.set(k, v);
  }
  return api.get(`${caminho}?${p}`);
}

export const listarKits = (filtros) => comFiltros("/kits", filtros);
export const mudarKits = (criancas, status, observacoes = null) =>
  api.post("/kits", { criancas, status, observacoes });

export const listarCompras = (filtros) => comFiltros("/compras", filtros);
export const criarCompra = (dados) => api.post("/compras", dados);
export const apagarCompra = (id) => api.delete(`/compras/${id}`);

export const fazerCheckin = (codigo, edicaoId) =>
  api.post("/checkin", { codigo, edicao_id: edicaoId });

export const urlDoQrCode = (criancaId) => `${API_URL}/checkin/qrcode/${criancaId}`;
