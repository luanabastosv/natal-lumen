import { api } from "./api.js";

/** A crianca pela qual o sistema convida a rezar hoje.
 *
 * Vem so com nome e instituicao: o convite nao abre ficha, nao leva a lugar
 * nenhum e nao precisa do id de ninguem.
 */
export const buscarConvite = (edicaoId) => api.get(`/oracao/${edicaoId}`);
