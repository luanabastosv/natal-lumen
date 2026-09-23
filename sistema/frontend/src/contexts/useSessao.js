import { useContext } from "react";
import { SessaoContexto } from "./sessao-contexto.js";

/** Atalho para ler a sessao.
 *
 * O nome comeca com "use" porque o React identifica hooks por esse prefixo —
 * o resto do codigo segue em portugues.
 */
export function useSessao() {
  const contexto = useContext(SessaoContexto);
  if (contexto === null) {
    throw new Error("useSessao precisa estar dentro de <ProvedorSessao>.");
  }
  return contexto;
}
