import { api } from "./api.js";

const API_URL = import.meta.env.VITE_API_URL ?? "/acesso/api";

function csrf() {
  const bruto = document.cookie
    .split("; ")
    .find((c) => c.startsWith("nl_csrf="))
    ?.split("=")[1];
  return bruto ? decodeURIComponent(bruto) : null;
}

export function listarCartoes(filtros = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filtros)) {
    if (v !== "" && v !== null && v !== undefined) p.set(k, v);
  }
  return api.get(`/cartoes?${p}`);
}

/** A "versao" da imagem na URL: o caminho do arquivo, que muda quando a
 *  imagem e trocada. Sem isto o navegador seguia mostrando a imagem antiga,
 *  guardada no cache pela MESMA URL (/cartoes/12/miniatura) — a troca
 *  funcionava no servidor e parecia nao ter funcionado na tela. */
const comVersao = (versao) => (versao ? `?v=${encodeURIComponent(versao)}` : "");

/** A mesma imagem, pequena. A visao de arquivo mostra dezenas de uma vez, e o
 *  original tem ~290 KB cada. Vai por <img src>, e nao por fetch: o cookie da
 *  sessao viaja junto por ser mesma origem, e o navegador cuida do cache.
 */
export const urlDaMiniatura = (id, versao) => `${API_URL}/cartoes/${id}/miniatura${comVersao(versao)}`;

export const apagarCartao = (id) => api.delete(`/cartoes/${id}`);

/** Troca a imagem de um cartao que ja existe, sem criar outro registro.
 *
 *  Nao passa pelo api.js porque ele so manda JSON — num FormData quem escreve o
 *  Content-Type e o navegador, o unico que sabe a fronteira entre as partes.
 */
export async function trocarImagemDoCartao(id, arquivo) {
  const dados = new FormData();
  dados.append("arquivo", arquivo);

  const token = csrf();
  const resposta = await fetch(`${API_URL}/cartoes/${id}/trocar`, {
    method: "POST",
    credentials: "include",
    headers: token ? { "X-CSRF-Token": token } : {},
    body: dados,
  });

  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => ({}));
    throw new Error(corpo.detail || "Não foi possível trocar a imagem.");
  }
  return resposta.json();
}

/** As pastas da tela: uma por instituicao, com as contagens de dentro.
 *
 *  Passa pelo mesmo filtro de alcance da lista, entao um monitor recebe so as
 *  pastas das instituicoes dele. A pasta organiza; ela nao decide acesso.
 */
export function listarPastas(edicaoId) {
  return api.get(`/cartoes/pastas?edicao_id=${edicaoId}`);
}

/** Sobe a pilha de cartoes e recebe a previa. Nao grava nada ainda.
 *
 * Nao passa pelo api.js porque ele so manda JSON — e num FormData quem tem de
 * escrever o Content-Type e o navegador, que e o unico que sabe a fronteira
 * entre as partes.
 */
export async function subirLoteDeCartoes({ arquivos, tipo, edicaoId, instituicaoId }) {
  const dados = new FormData();
  for (const arquivo of arquivos) dados.append("arquivos", arquivo);
  dados.append("tipo", tipo);
  dados.append("edicao_id", edicaoId);
  // A pilha sobe DENTRO de uma pasta: o servidor recusa, na previa, o arquivo
  // cujo codigo for de outra instituicao — e diz de qual.
  if (instituicaoId) dados.append("instituicao_id", instituicaoId);

  const token = csrf();
  const resposta = await fetch(`${API_URL}/cartoes/lote`, {
    method: "POST",
    credentials: "include",
    headers: token ? { "X-CSRF-Token": token } : {},
    body: dados,
  });

  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const detalhe = corpo?.detail;
    throw new Error(
      typeof detalhe === "string" ? detalhe : "Não foi possível ler os cartões.",
    );
  }
  return corpo;
}

/** Grava a previa. A pilha de autorizacoes manda junto as respostas de cada
 *  foto, pelo indice no lote; a de cartoes confirma sem corpo. */
export const confirmarLote = (id, respostas) =>
  api.post(`/cartoes/lote/${id}/confirmar`, respostas ? { respostas } : undefined);

export const marcarEnviados = (cartoes) => api.post("/cartoes/enviados", { cartoes });

/** A imagem só sai por rota autenticada — nunca é servida como arquivo estático. */
export const urlDaImagem = (id, versao) => `${API_URL}/cartoes/${id}/imagem${comVersao(versao)}`;

/** A foto de uma previa ainda nao gravada. Mesma porta autenticada: a imagem
 *  esta na pasta temporaria do lote e so sai por aqui. */
export const urlDaImagemDoLote = (idLote, indice) =>
  `${API_URL}/cartoes/lote/${idLote}/${indice}/imagem`;

/* ---------- Autorizacoes ----------
   Sobem pelo mesmo `subirLoteDeCartoes`, com `tipo: "autorizacao"`. O resto
   delas — listar, abrir, corrigir — tem rota propria no servidor. */

export const listarAutorizacoes = ({ edicao_id, instituicao_id }) =>
  api.get(`/autorizacoes?edicao_id=${edicao_id}&instituicao_id=${instituicao_id}`);

export const urlDaImagemDaAutorizacao = (id, versao) =>
  `${API_URL}/autorizacoes/${id}/imagem${comVersao(versao)}`;

export const urlDaMiniaturaDaAutorizacao = (id, versao) =>
  `${API_URL}/autorizacoes/${id}/miniatura${comVersao(versao)}`;

export const apagarAutorizacao = (id) => api.delete(`/autorizacoes/${id}`);

export async function trocarImagemDaAutorizacao(id, arquivo) {
  const dados = new FormData();
  dados.append("arquivo", arquivo);

  const token = csrf();
  const resposta = await fetch(`${API_URL}/autorizacoes/${id}/trocar`, {
    method: "POST",
    credentials: "include",
    headers: token ? { "X-CSRF-Token": token } : {},
    body: dados,
  });

  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => ({}));
    throw new Error(corpo.detail || "Não foi possível trocar a imagem.");
  }
  return resposta.json();
}
