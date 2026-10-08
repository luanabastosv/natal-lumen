import { api } from "./api.js";

/** Os lembretes do evento da edicao, um grupo por dia. So a coordenacao
 *  recebe: e preciso enxergar todas as criancas para saber se um padrinho
 *  esta pronto. */
export const listarLembretes = (edicaoId) => api.get(`/lembretes?edicao_id=${edicaoId}`);
