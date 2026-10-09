import { api } from "./api.js";

/** As criancas da edicao com algum cuidado avisado na autorizacao
 *  (necessidade especial, alergia ou restricao alimentar, observacao). So a
 *  coordenacao geral e a administracao geral. */
export const listarCuidados = (edicaoId) => api.get(`/cuidados?edicao_id=${edicaoId}`);
