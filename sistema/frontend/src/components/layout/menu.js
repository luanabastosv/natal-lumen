/** Itens do menu e a permissao que cada um exige.
 *
 * Esconder o item e so conveniencia: quem decide o acesso e o backend, que
 * confere a permissao em cada rota.
 */
export const ITENS_MENU = [
  { para: "/painel", rotulo: "Painel", permissao: "ver_painel" },
  { para: "/criancas", rotulo: "Crianças", permissao: "ver_criancas" },
  { para: "/padrinhos", rotulo: "Padrinhos", permissao: "ver_padrinhos" },
  { para: "/pagamentos", rotulo: "Pagamentos", permissao: "registrar_pagamentos" },
  { para: "/cartoes", rotulo: "Cartões", permissao: "subir_cartoes" },
  { para: "/kits", rotulo: "Kits", permissao: "gerenciar_kits" },
  { para: "/compras", rotulo: "Compras", permissao: "gerenciar_compras" },
  { para: "/checkin", rotulo: "Check-in", permissao: "fazer_checkin" },
  { para: "/usuarios", rotulo: "Usuários", permissao: "gerenciar_usuarios" },
];

export function itensVisiveis(pode) {
  return ITENS_MENU.filter((item) => pode(item.permissao));
}
