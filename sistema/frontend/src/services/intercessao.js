import { api } from "./api.js";

/** As quatro vivencias da intercessao, na ordem das colunas da planilha. */
export const VIVENCIAS = [
  { tipo: "missa", rotulo: "Santa Missa", curto: "Missa" },
  { tipo: "adoracao", rotulo: "Adoração", curto: "Ador." },
  { tipo: "terco", rotulo: "Mistério do Terço", curto: "Terço" },
  { tipo: "jejum", rotulo: "Jejum", curto: "Jejum" },
];

/** Marca a vivencia na crianca em nome de quem esta na sessao. Devolve as
 *  marcacoes da crianca ja em dia. */
export const marcarIntercessao = (criancaId, tipo) =>
  api.post(`/intercessao/${criancaId}/${tipo}`);

/** Tira a marcacao de quem esta na sessao. A dos outros fica. */
export const desmarcarIntercessao = (criancaId, tipo) =>
  api.delete(`/intercessao/${criancaId}/${tipo}`);

export const buscarPainelIntercessao = (edicaoId) =>
  api.get(`/intercessao/painel/${edicaoId}`);
