import { useState } from "react";
import { createPortal } from "react-dom";
import Button from "../core/Button.jsx";
import { Baixar, Conversa, Visto } from "../core/icones.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import { baixarAgradecimento } from "../../services/padrinhos.js";
import { primeiroNome } from "../../utils/nomes.js";
import { linkWhatsapp } from "../../utils/whatsapp.js";
import useTelaEstreita from "../../hooks/useTelaEstreita.js";

/** O agradecimento de um pagamento que chegou pelo link do cartao.
 *
 * O mesmo fim do apadrinhar com Pix (baixar a imagem, abrir o WhatsApp), mas
 * aberto pelo aviso: o pagamento do cartao cai minutos depois, quando quem
 * captou o padrinho ja saiu daquela tela. No celular e uma pagina inteira,
 * como o resto do apadrinhar; no computador, uma janela. */
export default function AgradecerPadrinho({ aviso, aoFechar }) {
  const estreita = useTelaEstreita();
  const [erro, definirErro] = useState("");
  const [baixando, definirBaixando] = useState(false);
  const [baixou, definirBaixou] = useState(false);
  const [enviou, definirEnviou] = useState(false);

  // Um agradecimento por crianca: cesta e festa da mesma crianca sao um so.
  const porCrianca = new Map();
  for (const a of aviso.apadrinhamentos) {
    if (!porCrianca.has(a.crianca_id)) porCrianca.set(a.crianca_id, a);
  }
  const lista = [...porCrianca.values()];
  const nomes = lista.map((a) => a.crianca_primeiro_nome);
  const criancas =
    nomes.length > 1 ? `${nomes.slice(0, -1).join(", ")} e ${nomes.at(-1)}` : nomes[0];
  const nome = primeiroNome(aviso.padrinho_nome);
  const zap = linkWhatsapp(
    aviso.padrinho_whatsapp,
    `Oi, ${nome}! Obrigado por apadrinhar ${criancas} no Natal Lumen. ` +
      "Segue o nosso agradecimento.",
  );
  const ondeCai = estreita ? "na galeria do seu celular" : "na pasta de downloads";

  async function baixar() {
    definirErro("");
    definirBaixando(true);
    try {
      for (const a of lista) {
        await baixarAgradecimento(a.id);
        await new Promise((pronto) => setTimeout(pronto, 400));
      }
      definirBaixou(true);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirBaixando(false);
    }
  }

  const meio = (
    <>
      <Mensagem tipo="erro">{erro}</Mensagem>
      <p className="apadrinhar-final__texto">
        <Visto t={16} /> {nome} pagou no cartão, e {criancas}{" "}
        {nomes.length > 1 ? "já contam" : "já conta"} como apadrinhada
        {nomes.length > 1 ? "s" : ""}.
      </p>
      <h2 className="apadrinhar-final__chamada">
        {baixou && enviou ? "Tudo certo!" : "Agora, agradeça ao padrinho"}
      </h2>
      <div className="passo-final__lista">
        <button
          type="button"
          className={`passo-final ${!baixou ? "passo-final--vez" : "passo-final--feito"}`}
          onClick={baixar}
          disabled={baixando}
        >
          <span className="passo-final__icone" aria-hidden="true">
            {baixou ? <Visto t={24} /> : <Baixar t={24} />}
          </span>
          <span className="passo-final__texto">
            <span className="passo-final__numero">Passo 1</span>
            <strong>
              {baixando
                ? "Baixando..."
                : lista.length === 1
                  ? "Baixe o agradecimento"
                  : `Baixe os ${lista.length} agradecimentos`}
            </strong>
            <span>{baixou ? "Salvo." : `A imagem fica ${ondeCai}.`}</span>
            <span className="passo-final__acao">
              <Baixar t={16} />
              {baixou ? "Baixar de novo" : "Baixar agora"}
            </span>
          </span>
        </button>
        <button
          type="button"
          className={`passo-final ${enviou ? "passo-final--feito" : baixou ? "passo-final--vez" : ""}`}
          disabled={!zap}
          onClick={() => {
            window.open(zap, "_blank", "noopener");
            definirEnviou(true);
          }}
        >
          <span className="passo-final__icone" aria-hidden="true">
            {enviou ? <Visto t={24} /> : <Conversa t={24} />}
          </span>
          <span className="passo-final__texto">
            <span className="passo-final__numero">Passo 2</span>
            <strong>Envie no WhatsApp de {nome}</strong>
            <span>
              {!zap
                ? "Este padrinho não tem WhatsApp válido cadastrado."
                : "A conversa abre com a mensagem pronta. Anexe a imagem que você baixou."}
            </span>
            {zap && (
              <span className="passo-final__acao">
                <Conversa t={16} />
                {enviou ? "Abrir de novo" : "Abrir o WhatsApp"}
              </span>
            )}
          </span>
        </button>
      </div>
    </>
  );

  const pe = (
    <div className="passos__rodape">
      <Button variant={baixou && enviou ? "primary" : "ghost"} onClick={aoFechar}>
        {baixou && enviou ? "Concluir" : "Agradecer depois"}
      </Button>
    </div>
  );

  if (estreita) {
    return createPortal(
      <div className="apadrinhar-pagina">
        <header className="apadrinhar-pagina__topo">
          <div className="pagina__eyebrow">Pagamento aprovado</div>
          <h1 className="pagina__titulo">Agradeça a {nome}</h1>
        </header>
        <div className="apadrinhar-pagina__meio">{meio}</div>
        <div className="apadrinhar-pagina__rodape">{pe}</div>
      </div>,
      document.body,
    );
  }
  return (
    <Modal rotulo="Pagamento aprovado" titulo={`Agradeça a ${nome}`} aoFechar={aoFechar} rodape={pe}>
      {meio}
    </Modal>
  );
}
