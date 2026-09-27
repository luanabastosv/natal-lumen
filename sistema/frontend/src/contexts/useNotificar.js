import { useContext } from "react";
import { NotificacoesContexto } from "./notificacoes-contexto.js";

/** Devolve `notificar(texto)`: um recado curto no canto da tela.
 *
 * E para CONFIRMACAO — "Pagamento registrado.", "Maria atualizada." —, nunca
 * para erro. Erro fica na pagina, junto do que falhou, e espera ser lido; a
 * confirmacao ja passou e nao precisa de espaco fixo.
 *
 * A funcao e estavel entre renders, entao pode entrar em lista de dependencia
 * de efeito sem disparar nada.
 */
export function useNotificar() {
  const notificar = useContext(NotificacoesContexto);
  if (notificar === null) {
    throw new Error("useNotificar precisa estar dentro de <ProvedorNotificacoes>.");
  }
  return notificar;
}
