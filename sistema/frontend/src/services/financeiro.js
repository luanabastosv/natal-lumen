import { api } from "./api.js";

/** Financeiro da edicao: as saidas e os recebimentos.
 *
 * As saidas continuam em /compras no servidor — e a mesma tabela desde o
 * inicio, e renomear a rota so quebraria o que ja esta publicado. A tela
 * chama de "saida" porque nem todo gasto e uma compra.
 */

function comFiltros(caminho, filtros = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filtros)) {
    if (v !== "" && v !== null && v !== undefined) p.set(k, v);
  }
  return api.get(`${caminho}?${p}`);
}

export const listarSaidas = (filtros) => comFiltros("/compras", filtros);
export const criarSaida = (dados) => api.post("/compras", dados);
export const editarSaida = (id, dados) => api.patch(`/compras/${id}`, dados);
export const apagarSaida = (id) => api.delete(`/compras/${id}`);

/** A lista do que ENTROU: junta os pagamentos dos padrinhos e os
 *  recebimentos soltos. Cada linha diz de qual das duas origens veio, em
 *  `fonte` — e e por ela que a tela sabe em qual rota as acoes batem. */
export const listarRecebimentos = (filtros) => comFiltros("/recebimentos", filtros);

export const criarRecebimento = (dados) => api.post("/recebimentos", dados);
export const editarRecebimento = (id, dados) => api.patch(`/recebimentos/${id}`, dados);
export const apagarRecebimento = (id) => api.delete(`/recebimentos/${id}`);

/** Comprovante de um recebimento solto. Separado do POST, como o do
 *  pagamento: o lancamento do dinheiro nao pode falhar por causa do arquivo. */
export function subirComprovanteDoRecebimento(id, arquivo) {
  const dados = new FormData();
  dados.append("arquivo", arquivo);
  return api.enviarArquivo(`/recebimentos/${id}/comprovante`, dados);
}

export const baixarComprovanteDoRecebimento = (id) =>
  api.baixar(`/recebimentos/${id}/comprovante`);

/** Rotulos das categorias, incluindo as DERIVADAS.
 *
 * As de apadrinhamento nao existem em tabela nenhuma: o servidor as calcula a
 * partir do que o pagamento quita. Por isso a lista aqui e maior que a do
 * formulario — ver CATEGORIAS_QUE_SE_ESCOLHEM. */
export const ROTULO_CATEGORIA = {
  apadrinhamento_cesta: "Apadrinhamento - cesta",
  apadrinhamento_festa: "Apadrinhamento - festa",
  // O pagamento que nao quita nada (o apadrinhamento foi desfeito e o dinheiro
  // ficou). Cesta e festa juntas nao caem aqui: cada uma conta no seu tipo.
  apadrinhamento: "Apadrinhamento sem destino",
  doacao: "Doação",
  outros: "Outros",
};

/** As duas que alguem escolhe ao registrar um recebimento.
 *
 * Apadrinhamento nao entra: o pagamento do padrinho se registra SO na ficha
 * dele, na pagina de padrinhos, onde ele nasce ligado as criancas que quita. Na
 * lista do financeiro ele aparece sozinho, sem ser lancado aqui. */
export const CATEGORIAS_QUE_SE_ESCOLHEM = [
  { valor: "doacao", rotulo: "Doação" },
  { valor: "outros", rotulo: "Outros" },
];
