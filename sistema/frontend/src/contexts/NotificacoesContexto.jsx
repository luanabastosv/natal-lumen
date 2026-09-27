import { useCallback, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Notificacao from "../components/feedback/Notificacao.jsx";
import { NotificacoesContexto } from "./notificacoes-contexto.js";

/** Quantos recados cabem empilhados. Passando disso, o mais velho sai: uma
 *  coluna de avisos subindo pela tela esconde justamente o conteudo que a
 *  pessoa acabou de mudar. */
const LIMITE = 3;

export function ProvedorNotificacoes({ children }) {
  const [fila, definirFila] = useState([]);
  const proximoId = useRef(0);

  // Estavel entre renders: as paginas guardam esta funcao com o nome que
  // antes era o `definirSucesso` do useState, e algumas a passam adiante.
  const notificar = useCallback((texto) => {
    if (!texto) return;
    const id = (proximoId.current += 1);
    definirFila((atual) => [...atual, { id, texto }].slice(-LIMITE));
  }, []);

  function tirar(id) {
    definirFila((atual) => atual.filter((n) => n.id !== id));
  }

  return (
    <NotificacoesContexto.Provider value={notificar}>
      {children}

      {/* Direto no body, por um portal: a pilha e fixa na tela e nao pode
          herdar `overflow` nem `transform` de nenhuma caixa do layout — a
          gaveta do celular tem transform, e isso sozinho quebraria o
          `position: fixed`. */}
      {createPortal(
        // O aria-live mora aqui, e nao em cada recado: a regiao precisa ja
        // existir no DOM quando o texto chega, senao o leitor de tela nao
        // anuncia.
        <div className="notificacoes" role="status" aria-live="polite">
          {fila.map((n) => (
            <Notificacao key={n.id} texto={n.texto} aoSair={() => tirar(n.id)} />
          ))}
        </div>,
        document.body,
      )}
    </NotificacoesContexto.Provider>
  );
}
