import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Button from "../core/Button.jsx";
import { Visto } from "../core/icones.jsx";
import AgradecerPadrinho from "../dados/AgradecerPadrinho.jsx";
import { useSessao } from "../../contexts/useSessao.js";
import { marcarLinkAvisado, meusLinks } from "../../services/padrinhos.js";
import { dinheiro } from "../../utils/dinheiro.js";
import { linksEmTela } from "../../utils/linksEmTela.js";
import { primeiroNome } from "../../utils/nomes.js";

// De quanto em quanto tempo pergunta, com links esperando pagamento. Sem link
// aberto, pergunta bem menos: so para pegar o que outra aba gerou.
const COM_LINK_MS = 20000;
const SEM_LINK_MS = 120000;

/** O aviso de que um padrinho pagou o link do cartao.
 *
 * O Pix se resolve na hora: o comissario tem o comprovante na mao e manda o
 * agradecimento ali mesmo. O cartao nao: o padrinho paga minutos depois, e
 * quem gerou o link ja esta em outra tela. Este aviso mora no layout e
 * aparece onde a pessoa estiver, ate ela agir: "Agradecer agora" abre o
 * agradecimento; "Depois" so esconde ate a proxima vez que ela abrir o
 * sistema. O aviso so some de vez quando ela abre o agradecimento.
 */
export default function AvisoDeLinkPago() {
  const { pode, usuario } = useSessao();
  const [pagos, definirPagos] = useState([]);
  const [abertos, definirAbertos] = useState(0);
  const [adiados, definirAdiados] = useState(() => new Set());
  const [agradecendo, definirAgradecendo] = useState(null);
  const ligado = Boolean(usuario) && pode("editar_padrinhos");

  const perguntar = useCallback(async () => {
    if (document.visibilityState !== "visible") return;
    try {
      const r = await meusLinks();
      definirPagos(r.pagos);
      definirAbertos(r.abertos);
    } catch {
      // Sem rede ou sem sessao: tenta de novo na proxima volta.
    }
  }, []);

  useEffect(() => {
    if (!ligado) return undefined;
    const primeira = setTimeout(perguntar, 0);
    const id = setInterval(perguntar, abertos > 0 ? COM_LINK_MS : SEM_LINK_MS);
    // Voltar para a aba e o momento em que a pessoa quer saber.
    window.addEventListener("focus", perguntar);
    document.addEventListener("visibilitychange", perguntar);
    return () => {
      clearTimeout(primeira);
      clearInterval(id);
      window.removeEventListener("focus", perguntar);
      document.removeEventListener("visibilitychange", perguntar);
    };
  }, [ligado, abertos, perguntar]);

  const visiveis = pagos.filter(
    (p) => !adiados.has(p.cobranca_id) && !linksEmTela.has(p.cobranca_id),
  );

  async function encerrar(aviso) {
    definirPagos((atual) => atual.filter((p) => p.cobranca_id !== aviso.cobranca_id));
    try {
      await marcarLinkAvisado(aviso.cobranca_id);
    } catch {
      // Se falhar, o aviso volta na proxima pergunta: melhor do que sumir.
    }
  }

  function agradecer(aviso) {
    encerrar(aviso);
    definirAgradecendo(aviso);
  }

  if (!ligado) return null;

  return (
    <>
      {visiveis.length > 0 &&
        createPortal(
          <div className="aviso-link" role="status" aria-live="polite">
            {visiveis.map((p) => (
              <div key={p.cobranca_id} className="aviso-link__cartao">
                <span className="aviso-link__icone" aria-hidden="true">
                  <Visto t={16} />
                </span>
                <div className="aviso-link__corpo">
                  {p.status === "pago" ? (
                    <>
                      <strong>
                        {primeiroNome(p.padrinho_nome)} pagou {dinheiro(p.valor)} no cartão
                      </strong>
                      <span>Falta mandar o agradecimento.</span>
                    </>
                  ) : (
                    <>
                      <strong>
                        {primeiroNome(p.padrinho_nome)} pagou {dinheiro(p.valor)}, depois do prazo
                      </strong>
                      <span>
                        O link já tinha vencido e as crianças foram liberadas. A coordenação
                        decide o destino do dinheiro.
                      </span>
                    </>
                  )}
                  <div className="aviso-link__acoes">
                    {p.status === "pago" && p.apadrinhamentos.length > 0 ? (
                      <>
                        <Button size="sm" variant="primary" onClick={() => agradecer(p)}>
                          Agradecer agora
                        </Button>
                        <button
                          type="button"
                          className="link-conferir"
                          onClick={() =>
                            definirAdiados((atual) => new Set(atual).add(p.cobranca_id))
                          }
                        >
                          Depois
                        </button>
                      </>
                    ) : (
                      <Button size="sm" variant="ghost" onClick={() => encerrar(p)}>
                        Entendi
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>,
          document.body,
        )}

      {agradecendo && (
        <AgradecerPadrinho aviso={agradecendo} aoFechar={() => definirAgradecendo(null)} />
      )}
    </>
  );
}
