import { useCallback, useSyncExternalStore } from "react";

/* O mesmo ponto em que a `.tabela--larga` comeca a rolar, e logo abaixo do
   720px onde o texto da pagina ja se reorganiza: daqui para baixo uma planilha
   de doze colunas nao e mais uma planilha, e vira uma tira que rola de lado. */
const ESTREITA = "(max-width: 720px)";


/** Se a tela e estreita o bastante para a lista mostrar so o essencial.
 *
 *  E JS, e nao CSS, de proposito: numa tabela `table-layout: fixed` esconder
 *  celulas com `display: none` nao tira a coluna — o <col> continua reservando
 *  a largura dela. A unica forma de a coluna sumir de verdade e nao existir no
 *  HTML, entao quem decide o que renderizar e o componente.
 *
 *  `useSyncExternalStore` e nao `useEffect` + estado: a largura da janela e um
 *  dado que vive fora do React, e por aqui a primeira pintura ja sai com o
 *  valor certo — sem o piscar de uma planilha larga que vira estreita.
 *
 *  `midia` troca o ponto de corte, para a lista que precisa de um degrau a
 *  mais entre o celular e a tela grande (ver Kits).
 */
export default function useTelaEstreita(midia = ESTREITA) {
  const assinar = useCallback(
    (avisar) => {
      const mq = window.matchMedia(midia);
      mq.addEventListener("change", avisar);
      return () => mq.removeEventListener("change", avisar);
    },
    [midia],
  );

  return useSyncExternalStore(
    assinar,
    () => window.matchMedia(midia).matches,
    // No servidor nao ha janela: a lista nasce larga, como sempre foi.
    () => false,
  );
}
