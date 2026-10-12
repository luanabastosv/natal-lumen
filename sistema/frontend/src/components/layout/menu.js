import {
  Configuracoes,
  MenuCartoes,
  MenuCheckin,
  MenuCriancas,
  MenuCuidados,
  MenuFinanceiro,
  MenuInstituicoes,
  MenuKits,
  MenuPadrinhos,
  MenuPainel,
  MenuProgramacao,
  MenuUsuarios,
} from "../core/icones.jsx";

/** Itens do menu e a permissao que cada um exige.
 *
 * Esconder o item e so conveniencia: quem decide o acesso e o backend, que
 * confere a permissao em cada rota.
 *
 * `Icone` e o desenho do destino: na lateral recolhida e so ele que aparece.
 */
export const ITENS_MENU = [
  // Sem permissao: o painel e a porta de entrada de todo mundo. Quem tem
  // ver_painel encontra os numeros da edicao ali; quem nao tem, so os
  // atalhos para o que alcanca.
  { para: "/painel", rotulo: "Painel", Icone: MenuPainel },
  {
    para: "/criancas",
    rotulo: "Crianças",
    rotuloMenu: "Lista geral",
    permissao: "ver_criancas",
    Icone: MenuCriancas,
  },
  { para: "/padrinhos", rotulo: "Padrinhos", permissao: "ver_padrinhos", Icone: MenuPadrinhos },
  {
    para: "/cartoes",
    rotulo: "Cartões e Autorização",
    rotuloMenu: "Cartões e autorizações",
    permissao: "subir_cartoes",
    Icone: MenuCartoes,
  },
  { para: "/kits", rotulo: "Kits", permissao: "gerenciar_kits", Icone: MenuKits },
  // Duas permissoes, e basta UMA: a coordenacao entra pelas duas abas, mas
  // um perfil pode receber so as saidas. Quem tem so uma delas ve so a sua metade —
  // quem cuida de compras nao precisa saber quanto a edicao arrecadou.
  //
  // Nao ha destino separado para os pagamentos dos padrinhos: eles sao linhas
  // da aba Recebimentos, com o comprovante na propria linha. Dinheiro que
  // entra tem um lugar so.
  {
    para: "/financeiro",
    rotulo: "Financeiro",
    permissoes: ["gerenciar_compras", "registrar_pagamentos"],
    Icone: MenuFinanceiro,
  },
  { para: "/checkin", rotulo: "Check-in", permissao: "fazer_checkin", Icone: MenuCheckin },
  // So a coordenacao geral do evento e a administracao geral: e dado de
  // saude de crianca, junto numa lista so. Pelo PERFIL, e nao por permissao —
  // a coordenacao da captacao tem quase as mesmas. O backend confere de novo.
  {
    para: "/cuidados",
    rotulo: "Cuidados especiais",
    soCoordenacaoGeral: true,
    Icone: MenuCuidados,
  },
  { para: "/usuarios", rotulo: "Usuários", permissao: "gerenciar_usuarios", Icone: MenuUsuarios },
  // O quadro de horarios do dia do evento. Todo perfil da edicao abre: a
  // coordenacao geral monta, e a equipe ve e imprime depois que ela conclui
  // (quem decide o que cada um ve e o backend).
  { para: "/programacao", rotulo: "Programação", Icone: MenuProgramacao },
  {
    para: "/instituicoes",
    rotulo: "Instituições",
    permissao: "gerenciar_cadastros",
    Icone: MenuInstituicoes,
  },
];

/** Cidades e edicoes: so a administracao geral. Mora no grupo Configuracoes,
 *  junto de usuarios e instituicoes. */
export const ITEM_ADMIN = {
  para: "/cidades-edicoes",
  rotulo: "Cidades e edições",
  apenasAdmin: true,
  Icone: Configuracoes,
};

/** Como a lateral se organiza: destinos soltos e grupos.
 *
 *  Um grupo junta destinos do mesmo assunto — tudo o que e da crianca, tudo o
 *  que e cadastro — e so aparece se a pessoa alcanca ao menos um deles. Quem
 *  alcanca so um destino do grupo continua vendo o grupo: o menu tem a mesma
 *  forma para todo mundo, e so o que tem dentro muda. */
export const ESTRUTURA_MENU = [
  { para: "/painel" },
  {
    grupo: "Crianças",
    Icone: MenuCriancas,
    itens: ["/criancas", "/cartoes", "/checkin", "/cuidados"],
  },
  { para: "/padrinhos" },
  { para: "/kits" },
  { para: "/financeiro" },
  // Pagina propria, e nao item de Configuracoes: e o quadro do dia do evento,
  // consultado e impresso, nao um cadastro.
  { para: "/programacao" },
  {
    grupo: "Configurações",
    Icone: Configuracoes,
    itens: ["/usuarios", "/instituicoes", "/cidades-edicoes"],
  },
];

/** Tudo o que tem rota, menu ou nao — e disto que o App monta as rotas. */
export const ROTAS = [...ITENS_MENU, ITEM_ADMIN];

/** Se este destino aparece para quem tem estas permissoes.
 *
 * `permissao` e o caso comum: uma, obrigatoria. `permissoes` e o destino que
 * junta assuntos de donos diferentes — basta UMA da lista, e a propria tela se
 * encarrega de mostrar so a parte que a pessoa alcanca.
 */
/** A coordenacao geral do evento: o perfil "Coordenacao" na edicao ativa, ou
 *  a administracao geral. */
export function eCoordenacaoGeral(usuario, vinculoAtivo) {
  return Boolean(usuario?.admin_geral) || vinculoAtivo?.perfil === "Coordenacao";
}

export function alcanca(item, pode, sessao = {}) {
  if (item.apenasAdmin) return Boolean(sessao.usuario?.admin_geral);
  if (item.soCoordenacaoGeral) return eCoordenacaoGeral(sessao.usuario, sessao.vinculoAtivo);
  if (item.permissoes) return item.permissoes.some((p) => pode(p));
  return !item.permissao || pode(item.permissao);
}

export function itensVisiveis(pode, sessao) {
  return ITENS_MENU.filter((item) => alcanca(item, pode, sessao));
}

/** A estrutura do menu com so o que esta pessoa alcanca: grupos vazios somem. */
export function menuVisivel(pode, sessao) {
  const porCaminho = Object.fromEntries(ROTAS.map((i) => [i.para, i]));
  return ESTRUTURA_MENU.map((entrada) => {
    if (entrada.para) {
      const item = porCaminho[entrada.para];
      return alcanca(item, pode, sessao) ? item : null;
    }
    const itens = entrada.itens.map((p) => porCaminho[p]).filter((i) => alcanca(i, pode, sessao));
    return itens.length ? { ...entrada, itens } : null;
  }).filter(Boolean);
}
