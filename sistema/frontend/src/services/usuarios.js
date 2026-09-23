import { api } from "./api.js";

export const listarUsuarios = () => api.get("/usuarios");

export const criarUsuario = (dados, vinculo) =>
  api.post("/usuarios", { dados, vinculo });

export const editarUsuario = (id, dados) => api.patch(`/usuarios/${id}`, dados);

export const gerarLinkDeAcesso = (id) => api.post(`/usuarios/${id}/link-de-acesso`);

export const criarVinculo = (usuarioId, dados) =>
  api.post(`/usuarios/${usuarioId}/vinculos`, dados);

export const editarVinculo = (usuarioId, vinculoId, dados) =>
  api.patch(`/usuarios/${usuarioId}/vinculos/${vinculoId}`, dados);
