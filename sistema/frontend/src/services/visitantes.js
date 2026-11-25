import { api } from "./api.js";

/* ---------- A pagina do QR Code (sem sessao) ---------- */

/** Confere o QR Code. 404 quando o codigo nao existe. */
export const conferirQrCode = (codigo) =>
  api.get(`/visitantes/publico/${encodeURIComponent(codigo)}`);

/** Grava o visitante e devolve `{ link_fotos }` (nulo se a galeria nao esta pronta). */
export const cadastrarVisitante = (codigo, dados) =>
  api.post(`/visitantes/publico/${encodeURIComponent(codigo)}`, dados);

/* ---------- O painel (so a coordenacao geral) ---------- */

/** O QR Code da edicao, o link das fotos e os visitantes. */
export const listarVisitantes = (edicaoId) => api.get(`/visitantes?edicao_id=${edicaoId}`);

export const salvarLinkFotos = (edicaoId, link) =>
  api.put(`/visitantes/link?edicao_id=${edicaoId}`, { link_fotos: link || null });

export const baixarPlanilhaVisitantes = (edicaoId) =>
  api.baixar(`/visitantes/planilha?edicao_id=${edicaoId}`);

export const baixarQrCode = (edicaoId, formato) =>
  api.baixar(`/visitantes/qrcode?edicao_id=${edicaoId}&formato=${formato}`);

/** O endereco da imagem do QR, para o <img> da tela. */
export const imagemQrCode = (edicaoId) =>
  `/acesso/api/visitantes/qrcode?edicao_id=${edicaoId}&formato=png`;
