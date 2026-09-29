/**
 * O dia do evento, do jeito que a equipe fala dele.
 *
 * A edicao batiza cada dia ("Sabado", "Domingo") e e por esse nome que todo
 * mundo se localiza — a data nao ajuda quem esta conferindo vinte escolas de
 * uma vez. A cor vem junto porque a pergunta que se faz correndo e "essa e do
 * sabado ou do domingo?", e a cor responde antes da leitura.
 */
import { rotuloDia } from "../../utils/dinheiro.js";
import { tomDoDia } from "../../utils/dias.js";

export default function EtiquetaDia({ data, descricao }) {
  return (
    <span className={`etiqueta dia dia--${tomDoDia(descricao)}`}>
      {rotuloDia(data, descricao)}
    </span>
  );
}
