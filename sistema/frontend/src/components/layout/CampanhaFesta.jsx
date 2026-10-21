import { useState } from "react";
import { createPortal } from "react-dom";
import Button from "../core/Button.jsx";
import { Estrela } from "../core/icones.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import { useNotificar } from "../../contexts/useNotificar.js";
import { useSessao } from "../../contexts/useSessao.js";
import { liberarCampanhaFesta } from "../../services/cadastros.js";

/** O botao especial da lateral: liga e desliga a campanha da festa.
 *
 *  Fica na base da lateral, junto da edicao, e nao no painel: e uma chave da
 *  edicao inteira, ligada quase no fim da campanha da cesta. So a
 *  administracao geral a ve — o servidor confere o mesmo.
 *
 *  A janela vai para o body: no celular a lateral e uma gaveta com transform,
 *  e um `position: fixed` dentro dela ficaria preso a gaveta. */
export default function CampanhaFesta({ recolhida = false }) {
  const { usuario, edicao, recarregarEdicoes } = useSessao();
  const notificar = useNotificar();
  const [confirmando, definirConfirmando] = useState(false);
  const [enviando, definirEnviando] = useState(false);
  const [erro, definirErro] = useState("");

  if (!edicao || !usuario?.admin_geral) return null;

  const ligada = Boolean(edicao.festa_liberada);

  async function alternar() {
    definirErro("");
    definirEnviando(true);
    try {
      await liberarCampanhaFesta(edicao.id, !ligada);
      await recarregarEdicoes();
      definirConfirmando(false);
      notificar(
        ligada
          ? "Campanha da festa desligada: o apadrinhamento de festa voltou a ficar fechado."
          : "Campanha da festa começou: o apadrinhamento de festa está liberado.",
      );
    } catch (e) {
      // Desligar nao passa pela janela: o erro sai no aviso.
      if (confirmando) definirErro(e.message);
      else notificar(e.message);
    } finally {
      definirEnviando(false);
    }
  }

  return (
    <>
      {/* Um interruptor: ligar pede confirmacao (abre a festa para a equipe
          inteira); desligar e na hora, para desfazer um clique errado. */}
      <button
        type="button"
        role="switch"
        aria-checked={ligada}
        className="lateral__festa"
        disabled={enviando}
        onClick={() => (ligada ? alternar() : definirConfirmando(true))}
        title={recolhida ? `Campanha da festa ${ligada ? "ligada" : "desligada"}` : undefined}
        aria-label="Campanha da festa"
      >
        <span className="lateral__festa-icone">
          <Estrela t={18} />
        </span>
        <span className="lateral__festa-texto">
          <strong>Campanha da festa</strong>
        </span>
        <span className={`interruptor ${ligada ? "interruptor--ligado" : ""}`.trim()} aria-hidden="true">
          <span className="interruptor__bolinha" />
        </span>
      </button>

      {confirmando &&
        createPortal(
          <Modal
            titulo="Começar a campanha da festa?"
            aoFechar={() => definirConfirmando(false)}
            rodape={
              <>
                <Button variant="ghost" onClick={() => definirConfirmando(false)} disabled={enviando}>
                  Cancelar
                </Button>
                <Button onClick={alternar} carregando={enviando}>
                  Começar
                </Button>
              </>
            }
          >
            <Mensagem tipo="erro">{erro}</Mensagem>
            <p className="lateral__festa-confirmar">
              A partir de agora, a festa de {edicao.nome} pode ser apadrinhada pela
              coordenação e pelos comissários que receberem a festa de cada criança.
            </p>
          </Modal>,
          document.body,
        )}
    </>
  );
}
