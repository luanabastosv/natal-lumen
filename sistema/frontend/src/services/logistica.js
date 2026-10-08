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

/** As abas da tela de kits: uma por instituicao, com o que falta montar nela. */
export const instituicoesDosKits = (edicaoId) =>
  comFiltros("/kits/instituicoes", { edicao_id: edicaoId });
/** Quantas criancas de cada idade e sexo em cada instituicao, sem as desistentes. */
export const perfilDosKits = (edicaoId) =>
  comFiltros("/kits/perfil", { edicao_id: edicaoId });
/** Marca o kit (ja montado) como conferido por quem esta usando o sistema. */
export const conferirKit = (criancaId) => api.post(`/kits/${criancaId}/conferir`);
/** Confere varios de uma vez; o que nao estiver montado e pulado. */
export const conferirKits = (criancas) => api.post("/kits/conferir", { criancas });
export const mudarKits = (criancas, status, observacoes = null) =>
  api.post("/kits", { criancas, status, observacoes });

export const fazerCheckin = (codigo, edicaoId) =>
  api.post("/checkin", { codigo, edicao_id: edicaoId });

/** Se hoje e dia do evento da edicao — o check-in so abre nesses dias. */
export const checkinAberto = (edicaoId) =>
  comFiltros("/checkin/aberto", { edicao_id: edicaoId });

/** As criancas que o usuario pode receber, para o monitor confirmar uma a uma. */
export const listaDoCheckin = (edicaoId) =>
  comFiltros("/checkin/lista", { edicao_id: edicaoId });

export const urlDoQrCode = (criancaId) => `${API_URL}/checkin/qrcode/${criancaId}`;
