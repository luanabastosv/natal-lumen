import { useCallback, useSyncExternalStore } from "react";

/* Computador = ponteiro fino (mouse ou trackpad) E tela larga. Celular e tablet
   tem ponteiro grosso (o dedo); a largura pega o caso do navegador do celular
   pedindo "versao para computador", que muda o tamanho mas nao o dedo. */
const COMPUTADOR = "(pointer: fine) and (min-width: 721px)";

const consulta = () => window.matchMedia(COMPUTADOR);

/** Se a pessoa esta num computador.
 *
 *  Existe para barrar o envio de cartoes e autorizacoes pelo celular. O
 *  sistema descobre de qual crianca e cada foto pelo NOME do arquivo
 *  (`CODIGO_...`), e a foto tirada pelo celular sai com o nome que a camera
 *  da — IMG_1234 —, que nao diz crianca nenhuma. No computador a pilha vem do
 *  scanner, ja com os nomes certos.
 */
export default function useNoComputador() {
  const assinar = useCallback((avisar) => {
    const mq = consulta();
    mq.addEventListener("change", avisar);
    return () => mq.removeEventListener("change", avisar);
  }, []);

  return useSyncExternalStore(assinar, () => consulta().matches, () => true);
}
