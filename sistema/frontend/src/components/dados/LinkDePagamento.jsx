import { useEffect, useRef, useState } from "react";
import Button from "../core/Button.jsx";
import { Conversa, Visto } from "../core/icones.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import { cancelarLink, conferirLink } from "../../services/padrinhos.js";
import { dinheiro } from "../../utils/dinheiro.js";
import { primeiroNome } from "../../utils/nomes.js";
import { linkWhatsapp } from "../../utils/whatsapp.js";
import { linksEmTela } from "../../utils/linksEmTela.js";

// De quanto em quanto tempo a tela pergunta se o padrinho ja pagou, enquanto
// esta aberta. No servidor o aviso do Mercado Pago chega sozinho; no seu
// computador ele nao alcanca, e e esta pergunta que faz o pagamento aparecer.
const INTERVALO_MS = 15000;

/** Um link de pagamento ainda valendo: copiar, mandar no WhatsApp, conferir
 *  se ja foi pago e cancelar.
 *
 *  `aoMudar` recebe o padrinho atualizado depois de conferir ou cancelar.
 *  Com `vigiar`, confere sozinho de tempos em tempos (a tela logo depois de
 *  gerar o link, com o padrinho ainda na conversa). */
export default function LinkDePagamento({
  link,
  padrinho,
  aoMudar,
  vigiar = false,
  // O comissario de base so cancela o link que ele mesmo gerou.
  podeCancelar = true,
  // Na ficha do padrinho: uma faixa curta, sem repetir as criancas.
  compacto = false,
}) {
  const [erro, definirErro] = useState("");
  const [copiado, definirCopiado] = useState(false);
  const [conferindo, definirConferindo] = useState(false);
  const [cancelando, definirCancelando] = useState(false);
  const [aviso, definirAviso] = useState("");
  const ocupado = useRef(false);

  const mensagem =
    `Oi, ${primeiroNome(padrinho.nome)}! Este é o link para pagar o seu ` +
    `apadrinhamento no Natal Lumen (${dinheiro(link.valor)}), no cartão: ${link.link} ` +
    `O link vale até ${quando(link.expira_em)}.`;
  const zap = linkWhatsapp(padrinho.whatsapp, mensagem);

  async function copiar() {
    definirErro("");
    try {
      await navigator.clipboard.writeText(link.link);
      definirCopiado(true);
      setTimeout(() => definirCopiado(false), 2500);
    } catch {
      definirErro("Não deu para copiar aqui. Selecione o link e copie à mão.");
    }
  }

  async function conferir(silencioso = false) {
    if (ocupado.current) return;
    ocupado.current = true;
    if (!silencioso) {
      definirErro("");
      definirAviso("");
      definirConferindo(true);
    }
    try {
      const atualizado = await conferirLink(link.id);
      const agora = atualizado.ultimo_link;
      if (agora?.status === "aguardando" && !silencioso) {
        definirAviso(
          agora.status_mercadopago === "in_process" || agora.status_mercadopago === "pending"
            ? "O pagamento está em análise no Mercado Pago. As crianças seguem reservadas."
            : agora.status_mercadopago === "rejected"
              ? "O cartão foi recusado. O padrinho pode tentar de novo pelo mesmo link."
              : "Ainda não foi pago.",
        );
      }
      if (agora?.status !== "aguardando" || !silencioso) aoMudar?.(atualizado);
    } catch (e) {
      if (!silencioso) definirErro(e.message);
    } finally {
      ocupado.current = false;
      if (!silencioso) definirConferindo(false);
    }
  }

  async function cancelar() {
    definirErro("");
    definirCancelando(true);
    try {
      aoMudar?.(await cancelarLink(link.id));
    } catch (e) {
      definirErro(e.message);
      // O 409 de "ja foi pago" traz o pagamento junto: confere para a tela
      // mostrar as criancas pagas.
      conferir(true);
    } finally {
      definirCancelando(false);
    }
  }

  useEffect(() => {
    if (!vigiar) return undefined;
    // Esta janela cuida do link: o aviso do canto da tela espera.
    linksEmTela.add(link.id);
    const id = setInterval(() => conferir(true), INTERVALO_MS);
    return () => {
      clearInterval(id);
      linksEmTela.delete(link.id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vigiar, link.id]);

  const prazo = quando(link.expira_em);
  const nome = primeiroNome(padrinho.nome);

  const secundarias = (
    <span className="link-envio__secundarias">
      <button
        type="button"
        className="link-conferir"
        onClick={() => conferir(false)}
        disabled={conferindo}
      >
        {conferindo ? "Conferindo..." : "Conferir agora"}
      </button>
      {podeCancelar && (
        <button
          type="button"
          className="link-conferir link-envio__cancelar"
          onClick={cancelar}
          disabled={cancelando}
        >
          {cancelando ? "Cancelando..." : "Cancelar link"}
        </button>
      )}
    </span>
  );

  const botoes = (
    <>
      <Button
        size="sm"
        variant="primary"
        iconLeft={<Conversa t={16} />}
        disabled={!zap}
        titulo={zap ? undefined : "Este padrinho não tem WhatsApp válido cadastrado"}
        onClick={() => window.open(zap, "_blank", "noopener")}
      >
        Mandar no WhatsApp
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={copiar}
        iconLeft={copiado ? <Visto t={14} /> : null}
      >
        {copiado ? "Link copiado" : "Copiar link"}
      </Button>
    </>
  );

  /* Na ficha: uma faixa so, com as criancas que ESTE link cobra. Elas tambem
     aparecem na lista abaixo, mas e aqui que se decide cancelar, e e preciso
     ver o que o cancelar solta (pedido de 07/11/2026). */
  if (compacto) {
    return (
      <div className="link-aberto">
        <div className="link-aberto__texto">
          <span className="link-envio__ponto" aria-hidden="true" />
          <span>
            <strong>Link de {dinheiro(link.valor)} esperando pagamento</strong>
            <span className="link-aberto__detalhe">
              Vale até {prazo}
              {link.criado_por ? ` · gerado por ${primeiroNome(link.criado_por)}` : ""}
            </span>
          </span>
        </div>
        {link.criancas?.length > 0 && (
          <ul className="link-aberto__criancas" aria-label="Crianças deste link">
            {link.criancas.map((c) => {
              const m = c.match(/^(\S+)\s+(.*?)\s+\((cesta|festa)\)$/);
              return (
                <li key={c}>
                  {m ? (
                    <>
                      <span className="link-aberto__codigo">{m[1]}</span>
                      {m[2]}
                      <span className="link-aberto__tipo">{m[3]}</span>
                    </>
                  ) : (
                    c
                  )}
                </li>
              );
            })}
          </ul>
        )}
        <Mensagem tipo="erro">{erro}</Mensagem>
        <Mensagem tipo="aviso">{aviso}</Mensagem>
        <div className="link-aberto__acoes">
          <span className="link-envio__botoes">{botoes}</span>
          {secundarias}
        </div>
      </div>
    );
  }

  /* Logo depois de gerar: uma pergunta so ("como mando isto?"), respondida
     pelos dois botoes. O resto e conferencia, em letra de nota. */
  return (
    <div className="link-envio">
      <p className="link-envio__titulo">Mande o link para {nome} pagar no cartão</p>
      <div className="link-envio__botoes">{botoes}</div>

      <dl className="link-envio__resumo">
        <dt>Valor</dt>
        <dd>{dinheiro(link.valor)}</dd>
        <dt>{link.criancas?.length === 1 ? "Criança" : "Crianças"}</dt>
        <dd>
          {(link.criancas ?? []).map((c) => (
            <span key={c} className="link-envio__crianca">
              {c}
            </span>
          ))}
        </dd>
        <dt>Vale até</dt>
        <dd>{prazo}</dd>
      </dl>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="aviso">{aviso}</Mensagem>

      <div className="link-envio__rodape">
        <span className="link-envio__estado" role="status">
          <span className="link-envio__ponto" aria-hidden="true" />
          Esperando o pagamento. Esta tela atualiza sozinha.
        </span>
        {secundarias}
      </div>
    </div>
  );
}

/** "09/11 às 13:54": o ano e os segundos so pesam. */
function quando(iso) {
  const d = new Date(iso);
  const dia = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${dia} às ${hora}`;
}
