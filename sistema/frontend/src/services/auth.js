import { api } from "./api.js";

export const entrar = (email, senha) => api.post("/auth/login", { email, senha });

export const sair = () => api.post("/auth/logout");

export const quemSouEu = () => api.get("/auth/eu");

export const definirSenha = (token, senha) =>
  api.post("/auth/definir-senha", { token, senha });

export const esqueciSenha = (email) => api.post("/auth/esqueci-senha", { email });
