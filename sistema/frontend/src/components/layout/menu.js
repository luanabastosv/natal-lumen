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
];

/** Fora do menu, de proposito.
 *
 * Todos os destinos acima trabalham DENTRO da edicao escolhida na lateral.
 * Cidades e edicoes e o contrario: e onde essa escolha passa a existir, e so a
 * administracao geral entra. Por isso ele mora na base da lateral, junto de
 * quem esta logado, e nao no meio dos destinos do dia a dia.
 */
export const ITEM_ADMIN = {
  para: "/cidades-edicoes",
  rotulo: "Cadastrar cidades e edições",
  apenasAdmin: true,
};

/** Tudo o que tem rota, menu ou nao — e disto que o App monta as rotas. */
export const ROTAS = [...ITENS_MENU, ITEM_ADMIN];

export function itensVisiveis(pode) {
  return ITENS_MENU.filter((item) => !item.permissao || pode(item.permissao));
}
