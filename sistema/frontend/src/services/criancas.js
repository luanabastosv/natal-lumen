import { api } from "./api.js";

export function listarCriancas(filtros = {}) {
  const parametros = new URLSearchParams();
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor !== "" && valor !== null && valor !== undefined) {
      parametros.set(chave, valor);
    }
  }
  return api.get(`/criancas?${parametros}`);
}

export const criarCrianca = (dados) => api.post("/criancas", dados);
export const resumoInstituicoes = (edicaoId) =>
  api.get(`/criancas/resumo-instituicoes?edicao_id=${edicaoId}`);
export const editarEmLote = (dados) => api.post("/criancas/lote", dados);
/** O time de comissarios da edicao, com as instituicoes que cada um atende. */
export const listarComissarios = (edicaoId) =>
  api.get(`/criancas/comissarios?edicao_id=${edicaoId}`);
export const renumerar = (dados) => api.post("/criancas/renumerar", dados);
export const detalharCrianca = (id) => api.get(`/criancas/${id}`);
export const editarCrianca = (id, dados) => api.patch(`/criancas/${id}`, dados);
/** O recado do comissario sobre a crianca (rota propria: ele nao edita crianca). */
export const salvarObservacaoComissario = (id, texto) =>
  api.patch(`/criancas/${id}/observacao-comissario`, { texto });
/* Apagar crianca leva junto cartao, kit e apadrinhamento: a tela pede a conta
   primeiro, mostra no modal, e so entao apaga. */
export const dependenciasDaCrianca = (id) => api.get(`/criancas/${id}/dependencias`);
export const apagarCrianca = (id) => api.delete(`/criancas/${id}`);
/** Marca (ou desmarca) que a crianca desistiu de ir ao evento. */
export const marcarDesistencia = (id, desistiu) =>
  api.patch(`/criancas/${id}/desistencia`, { desistiu });

/** Sobe a planilha e recebe a previa. Nao grava nada ainda. */
export function analisarPlanilha({ arquivo, edicaoId, instituicaoId }) {
  const dados = new FormData();
  dados.append("arquivo", arquivo);
  dados.append("edicao_id", edicaoId);
  if (instituicaoId) dados.append("instituicao_id", instituicaoId);
  return api.enviarArquivo("/criancas/importar", dados, "Não foi possível ler a planilha.");
}

export const confirmarImportacao = (id) =>
  api.post(`/criancas/importar/${id}/confirmar`);
