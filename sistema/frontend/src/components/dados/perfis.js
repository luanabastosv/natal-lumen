/** Perfis que respondem por instituicoes especificas; os outros alcancam a
 *  edicao inteira.
 *
 *  O backend usa a mesma regra e a devolve pronta em `filtrado_por_instituicao`
 *  — mas aquilo vale para o perfil JA GRAVADO. Enquanto a escolha esta na tela,
 *  quem decide se o campo de instituicoes aparece e esta lista.
 *
 *  Em arquivo proprio: um modulo que exporta componente e constante quebra o
 *  fast refresh do Vite.
 */
export const PERFIS_POR_INSTITUICAO = ["Comissarios - comissario", "Monitoria - monitores"];

export function pedeInstituicoes(perfil) {
  return PERFIS_POR_INSTITUICAO.includes(perfil?.nome);
}

/** Perfis filtrados tambem crianca a crianca, e nao so por instituicao.
 *
 *  So o comissario: ele ve apenas as criancas com o nome dele na coluna
 *  Comissario, e nao a lista inteira das instituicoes dele. O monitor continua
 *  com a instituicao toda. Mesma historia das listas acima — o backend manda
 *  `so_criancas_atribuidas` no vinculo ja gravado, e esta lista vale enquanto
 *  a escolha ainda esta na tela.
 */
export const PERFIS_POR_CRIANCA = ["Comissarios - comissario"];

export function veSoCriancasAtribuidas(perfil) {
  return PERFIS_POR_CRIANCA.includes(perfil?.nome);
}

/** Perfis que respondem por um grupo da comunidade.
 *
 *  So o comissario: o monitor responde pela instituicao e a coordenacao pela
 *  edicao inteira. Mesma historia da lista acima — o backend devolve
 *  `usa_grupo` para o perfil ja gravado, e esta lista vale enquanto a escolha
 *  ainda esta na tela.
 */
export const PERFIS_COM_GRUPO = ["Comissarios - comissario"];

export function pedeGrupo(perfil) {
  return PERFIS_COM_GRUPO.includes(perfil?.nome);
}

/** A coordenacao e o unico perfil de CIDADE, e nao de edicao.
 *
 *  Quem coordena uma cidade coordena tudo o que esta aberto nela: o servidor
 *  repete o vinculo em todas as edicoes ativas daquela cidade e poe a
 *  coordenacao dentro de toda edicao nova. A tela escolhe uma edicao como
 *  sempre — mas precisa avisar que a escolha vale mais largo do que parece.
 */
export const PERFIL_COORDENACAO = "Coordenacao";

export function valeCidadeInteira(perfil) {
  return perfil?.nome === PERFIL_COORDENACAO;
}

/** Como cada perfil se escreve na tela.
 *
 * O banco guarda o nome sem acento ("Comissario"), do mesmo jeito que as chaves
 * de dependencia: o acento e assunto de tela, e e aqui que o sistema escreve em
 * portugues de verdade. Perfil novo que chegue sem rotulo aparece como veio, em
 * vez de sumir.
 */
const ROTULOS = {
  Coordenacao: "Coordenação",
  // O comissariado tambem e um par, como a monitoria: quem coordena a captacao
  // alcanca a edicao inteira e distribui a lista; o comissario responde pelas
  // criancas no nome dele.
  "Comissarios - coordenacao": "Comissários - coordenação",
  "Comissarios - comissario": "Comissários - comissário",
  // A monitoria e um par: quem coordena alcanca a edicao inteira, os
  // monitores so as instituicoes deles. O rotulo precisa deixar isso obvio na
  // hora de dar acesso, que e o unico momento em que alguem escolhe entre os
  // dois.
  "Monitoria - coordenacao": "Monitoria - coordenação",
  "Monitoria - monitores": "Monitoria - monitores",
  Estrutura: "Estrutura",
  // Nao e um perfil da base: e o atributo da conta que alcanca tudo. Aparece
  // aqui porque a lista de responsaveis por crianca mistura os dois.
  "Administracao geral": "Administração geral",
};

export function rotuloDoPerfil(nome) {
  return ROTULOS[nome] ?? nome;
}
