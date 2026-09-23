import { api } from "./api.js";

export const buscarRelatorio = (edicaoId) => api.get(`/painel/${edicaoId}`);
