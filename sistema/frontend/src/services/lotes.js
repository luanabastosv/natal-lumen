import { api } from "./api.js";

/* Apadrinhamento em lote: so a administracao geral (o backend confere em
 * todas as rotas, ver backend/app/routers/lotes.py). */

/** { festa_liberada, valor_cesta, valor_festa, instituicoes: [{ id, nome,
 *  criancas, cesta_livres, festa_livres }] } */
export const instituicoesComVagas = (edicaoId) =>
  api.get(`/lotes/instituicoes?edicao_id=${edicaoId}`);

/** As criancas livres das instituicoes escolhidas, na ordem da sugestao. */
export const vagasDoLote = (edicaoId, instituicaoIds) =>
  api.get(
    `/lotes/vagas?edicao_id=${edicaoId}&instituicao_ids=${instituicaoIds.join(",")}`,
  );

/** Le a planilha do grupo. Nada e gravado. */
export function lerPlanilhaDoLote(edicaoId, arquivo) {
  const dados = new FormData();
  dados.append("edicao_id", edicaoId);
  dados.append("arquivo", arquivo);
  return api.enviarArquivo("/lotes/ler-planilha", dados);
}

/** Grava o lote inteiro, com o comprovante do grupo. `dados.chave_envio`
 *  faz o mesmo envio repetido devolver o lote ja gravado. */
export function gravarLote(dados, comprovante) {
  const corpo = new FormData();
  corpo.append("dados", JSON.stringify(dados));
  corpo.append("comprovante", comprovante);
  return api.enviarArquivo("/lotes", corpo);
}

export const listarLotes = (edicaoId) => api.get(`/lotes?edicao_id=${edicaoId}`);
export const detalharLote = (id) => api.get(`/lotes/${id}`);
export const baixarAgradecimentosDoLote = (id) => api.baixar(`/lotes/${id}/agradecimentos`);

/** Marca que o agradecimento destas criancas foi mandado. Devolve o lote. */
export const marcarEnviados = (id, apadrinhamentoIds) =>
  api.post(`/lotes/${id}/enviados`, { apadrinhamento_ids: apadrinhamentoIds });
