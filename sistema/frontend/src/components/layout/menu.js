/** Itens do menu e a permissao que cada um exige.
 *
 * Esconder o item e so conveniencia: quem decide o acesso e o backend, que
 * confere a permissao em cada rota.
 */
export const ITENS_MENU = [
  // Sem permissao: o painel e a porta de entrada de todo mundo. Quem tem
  // ver_painel encontra os numeros da edicao ali; quem nao tem, so os
  // atalhos para o que alcanca.
  { para: "/painel", rotulo: "Painel" },
  { para: "/criancas", rotulo: "Crianças", permissao: "ver_criancas" },
  { para: "/padrinhos", rotulo: "Padrinhos", permissao: "ver_padrinhos" },
  { para: "/pagamentos", rotulo: "Pagamentos", permissao: "registrar_pagamentos" },
  { para: "/cartoes", rotulo: "Cartões", permissao: "subir_cartoes" },
  { para: "/kits", rotulo: "Kits", permissao: "gerenciar_kits" },
  { para: "/compras", rotulo: "Compras", permissao: "gerenciar_compras" },
  { para: "/checkin", rotulo: "Check-in", permissao: "fazer_checkin" },
  { para: "/usuarios", rotulo: "Usuários", permissao: "gerenciar_usuarios" },
  { para: "/instituicoes", rotulo: "Instituições", permissao: "gerenciar_cadastros" },
  // Cidades e edicoes nao tem permissao propria: sao da administracao geral.
  { para: "/cidades-edicoes", rotulo: "Cidades e edições", apenasAdmin: true },
];

export function itensVisiveis(pode, admin = false) {
  return ITENS_MENU.filter((item) => {
    if (item.apenasAdmin) return admin;
    if (!item.permissao) return true;
    return pode(item.permissao);
  });
}
