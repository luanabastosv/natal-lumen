import { api } from "./api.js";

/* ---------- A pagina do QR Code (sem sessao) ---------- */

/** O dia do QR Code. 404 quando o codigo nao existe. */
export const buscarDiaPublico = (codigo) =>
  api.get(`/visitantes/publico/${encodeURIComponent(codigo)}`);

/** Grava o visitante e devolve `{ link_fotos }` (nulo se a galeria nao esta pronta). */
export const cadastrarVisitante = (codigo, dados) =>
  api.post(`/visitantes/publico/${encodeURIComponent(codigo)}`, dados);

/* ---------- O painel (so a coordenacao geral) ---------- */

/** Os dias da edicao, com o QR Code e o link das fotos, e os visitantes. */
export const listarVisitantes = (edicaoId) => api.get(`/visitantes?edicao_id=${edicaoId}`);

export const salvarLinkFotos = (diaId, link) =>
  api.put(`/visitantes/dias/${diaId}/link`, { link_fotos: link || null });

export const baixarPlanilhaVisitantes = (edicaoId) =>
  api.baixar(`/visitantes/planilha?edicao_id=${edicaoId}`);

export const baixarQrCode = (diaId, formato) =>
  api.baixar(`/visitantes/dias/${diaId}/qrcode?formato=${formato}`);

/** O endereco da imagem do QR, para o <img> da tela. */
export const imagemQrCode = (diaId) => `/acesso/api/visitantes/dias/${diaId}/qrcode?formato=png`;
