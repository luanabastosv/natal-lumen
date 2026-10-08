/* As regras do formulario do padrinho, divididas entre a janela do
   computador e a pagina de cadastro do celular (ver CamposPadrinho.jsx). */

import { numeroLimpo } from "../../utils/whatsapp.js";

// So o formato: alguma coisa, arroba, alguma coisa com ponto. Quem decide de
// verdade e o servidor (EmailStr); isto so evita habilitar o botao cedo.
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/* As duas perguntas da captacao nascem vazias e sao obrigatorias: Sim ou Nao,
   sem "a perguntar". O cadastro so fecha quando a captacao perguntou. */
export const PADRINHO_NOVO = {
  nome: "",
  whatsapp: "",
  email: "",
  observacoes: "",
  membro_ser_feliz: "",
  interesse_mensal: "",
};

/** "" -> null, "sim" -> true, "nao" -> false. */
function resposta(valor) {
  return valor === "" ? null : valor === "sim";
}

/** O caminho de volta: o que esta gravado, do jeito que o formulario le. */
export function paraOFormulario(padrinho) {
  const sel = (v) => (v === true ? "sim" : v === false ? "nao" : "");
  return {
    nome: padrinho.nome ?? "",
    whatsapp: padrinho.whatsapp ?? "",
    email: padrinho.email ?? "",
    observacoes: padrinho.observacoes ?? "",
    membro_ser_feliz: sel(padrinho.membro_ser_feliz),
    interesse_mensal: sel(padrinho.interesse_mensal),
  };
}

/** O que vai para o servidor. Campo apagado vira null, nunca "": o EmailStr
 *  rejeitaria a string vazia. */
export function dadosDoPadrinho(campos) {
  return {
    nome: campos.nome.trim(),
    whatsapp: campos.whatsapp.trim() || null,
    email: campos.email.trim() || null,
    observacoes: campos.observacoes.trim() || null,
    membro_ser_feliz: resposta(campos.membro_ser_feliz),
    interesse_mensal: resposta(campos.interesse_mensal),
  };
}

/** Tudo o que e obrigatorio esta preenchido: nome, WhatsApp com DDD, email
 *  com cara de email e as duas perguntas. So a observacao e opcional. */
export function padrinhoCompleto(campos) {
  return Boolean(
    campos.nome.trim() &&
      numeroLimpo(campos.whatsapp) &&
      EMAIL.test(campos.email.trim()) &&
      campos.membro_ser_feliz &&
      campos.interesse_mensal,
  );
}
