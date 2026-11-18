/** Como um nome de pessoa se escreve quando o espaco e curto.
 *
 * Mora aqui, e nao dentro de uma tela, porque sao dois lugares com o mesmo
 * problema: o rodape da barra lateral e a etiqueta do comissario na ficha do
 * padrinho. Nos dois, o nome inteiro estoura e o primeiro nome sozinho nao
 * distingue duas Marias do mesmo time.
 */

/** "Maria da Silva Souza" -> "Maria Souza": nome e sobrenome, sem os ligadores. */
export function nomeCurto(nome) {
  const partes = (nome ?? "").trim().split(/\s+/).filter(Boolean);
  if (partes.length <= 1) return partes[0] ?? "";
  return `${partes[0]} ${partes[partes.length - 1]}`;
}

/** "Maria da Silva Souza" -> "Maria Silva": o primeiro e o segundo nome, pulando
 * os ligadores. E como a equipe chama o monitor responsavel na lista de
 * instituicoes. */
const LIGADORES = new Set(["da", "das", "de", "do", "dos", "e"]);
export function doisNomes(nome) {
  const partes = (nome ?? "").trim().split(/\s+/).filter(Boolean);
  const segundo = partes.slice(1).find((p) => !LIGADORES.has(p.toLowerCase()));
  return segundo ? `${partes[0]} ${segundo}` : partes[0] ?? "";
}

/** Primeiro nome, para quando a frase e falada com a pessoa ("Olá, Maria!"). */
export function primeiroNome(nome) {
  return (nome ?? "").trim().split(/\s+/)[0] ?? "";
}
