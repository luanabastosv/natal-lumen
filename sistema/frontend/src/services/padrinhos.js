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

export const apagarPadrinho = (id) => api.delete(`/padrinhos/${id}`);
export const dependenciasDoPadrinho = (id) => api.get(`/padrinhos/${id}/dependencias`);

export const criarApadrinhamento = (dados) => api.post("/apadrinhamentos", dados);
export const editarApadrinhamento = (id, dados) => api.patch(`/apadrinhamentos/${id}`, dados);
export const apagarApadrinhamento = (id) => api.delete(`/apadrinhamentos/${id}`);

/** Todos os cartoes pagos de um padrinho, num ZIP so. */
export const baixarTodosAgradecimentos = (padrinhoId) =>
  api.baixar(`/padrinhos/${padrinhoId}/agradecimentos`);

/** Baixa o cartao de agradecimento desta crianca, pronto para o WhatsApp. */
export const baixarAgradecimento = (id) =>
  api.baixar(`/apadrinhamentos/${id}/agradecimento`);

/** O mesmo cartao, como blob — para compartilhar em vez de so salvar. */
export const obterAgradecimento = (id) =>
  api.blob(`/apadrinhamentos/${id}/agradecimento`);

/** Manda o cartao ao WhatsApp do padrinho pela Cloud API da Meta. */
export const enviarAgradecimento = (id) =>
  api.post(`/apadrinhamentos/${id}/agradecimento/enviar`);

/** Os pagamentos de um padrinho, para a aba Pagamento da ficha dele: e de
 *  onde se confere o comprovante de cada um. A lista do dinheiro da EDICAO
 *  inteira e outra — GET /recebimentos, no financeiro. */
export const listarPagamentos = (filtros) => comFiltros("/pagamentos", filtros);

/** Sobe o comprovante deste pagamento. Separado do POST /pagamentos: a
 *  quitacao nao pode falhar por causa de um arquivo grande demais. Trocar o
 *  comprovante e subir outro: o anterior sai do disco no servidor. */
export function subirComprovante(id, arquivo) {
  const dados = new FormData();
  dados.append("arquivo", arquivo);
  return api.enviarArquivo(`/pagamentos/${id}/comprovante`, dados);
}

export const baixarComprovante = (id) => api.baixar(`/pagamentos/${id}/comprovante`);
export const criarPagamento = (dados) => api.post("/pagamentos", dados);
export const editarPagamento = (id, dados) => api.patch(`/pagamentos/${id}`, dados);
export const apagarPagamento = (id) => api.delete(`/pagamentos/${id}`);
