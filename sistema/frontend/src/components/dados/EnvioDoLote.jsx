import { useState } from "react";
import Button from "../core/Button.jsx";
import { Baixar, Conversa, Visto } from "../core/icones.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import useTelaEstreita from "../../hooks/useTelaEstreita.js";
import { baixarAgradecimento, obterAgradecimento } from "../../services/padrinhos.js";
import { marcarEnviados } from "../../services/lotes.js";
import { formatarDataHora } from "../../utils/dinheiro.js";
import { primeiroNome } from "../../utils/nomes.js";
import { linkWhatsapp, numeroLimpo, podeCompartilharArquivo } from "../../utils/whatsapp.js";

/** A lista de envio do lote: um padrinho por linha, e quem ja recebeu.
 *
 * Existe para ninguem precisar caçar os padrinhos do grupo no meio da lista
 * geral de padrinhos. O envio e o de sempre desde que a Cloud API foi
 * desligada (08/10/2026): a conversa abre com o texto pronto e a imagem vai
 * anexada por quem envia.
 *
 *   computador -> baixa o(s) agradecimento(s) e abre a conversa no WhatsApp
 *                 Web, sempre na MESMA aba: com quarenta padrinhos, quarenta
 *                 abas novas seriam a bagunca que a lista existe para evitar.
 *   celular    -> a folha de compartilhar do aparelho, com a imagem e o texto
 *                 juntos; a pessoa escolhe o contato no WhatsApp.
 *
 * Ao enviar, a linha fica marcada (POST /lotes/{id}/enviados), e a ficha do
 * padrinho tambem passa a mostrar o agradecimento como enviado. */

function agrupar(linhas) {
  const grupos = new Map();
  for (const l of linhas) {
    if (!grupos.has(l.padrinho_id)) {
      grupos.set(l.padrinho_id, {
        padrinho_id: l.padrinho_id,
        padrinho: l.padrinho,
        whatsapp: l.whatsapp,
        itens: [],
      });
    }
    grupos.get(l.padrinho_id).itens.push(l);
  }
  return [...grupos.values()].map((g) => {
    // Um agradecimento por crianca (cesta e festa da mesma crianca sao um so),
    // e nada para quem desistiu: nao vai ao evento.
    const vistos = new Set();
    const aMandar = g.itens.filter((i) => {
      if (i.desistiu || vistos.has(i.crianca_codigo)) return false;
      vistos.add(i.crianca_codigo);
      return true;
    });
    const enviados = aMandar.filter((i) => i.enviado_em);
    return {
      ...g,
      aMandar,
      enviado: aMandar.length > 0 && enviados.length === aMandar.length,
      enviadoEm: enviados.map((i) => i.enviado_em).sort().at(-1) ?? null,
    };
  });
}

function mensagem(grupo) {
  const nomes = grupo.aMandar.map((i) => primeiroNome(i.crianca));
  const criancas =
    nomes.length > 1 ? `${nomes.slice(0, -1).join(", ")} e ${nomes.at(-1)}` : nomes[0];
  return (
    `Oi, ${primeiroNome(grupo.padrinho)}! Obrigado por apadrinhar ${criancas} no Natal Lumen. ` +
    "Segue o nosso agradecimento."
  );
}

/** A conversa no WhatsApp Web, direto, sem a pagina intermediaria do wa.me. */
function linkWeb(numero, texto) {
  const limpo = numeroLimpo(numero);
  if (!limpo) return null;
  return `https://web.whatsapp.com/send?phone=${limpo}&text=${encodeURIComponent(texto)}`;
}

const esperar = (ms) => new Promise((pronto) => setTimeout(pronto, ms));

export default function EnvioDoLote({ lote, aoAtualizar }) {
  const estreita = useTelaEstreita();
  const [erro, definirErro] = useState("");
  const [enviando, definirEnviando] = useState(null);
  const [soFaltam, definirSoFaltam] = useState(false);

  const grupos = agrupar(lote.linhas);
  const comAgradecimento = grupos.filter((g) => g.aMandar.length > 0);
  const jaReceberam = comAgradecimento.filter((g) => g.enviado).length;
  const mostrados = soFaltam ? grupos.filter((g) => !g.enviado) : grupos;

  async function marcar(grupo) {
    const atualizado = await marcarEnviados(
      lote.id,
      grupo.aMandar.map((i) => i.apadrinhamento_id),
    );
    aoAtualizar(atualizado);
  }

  async function enviar(grupo) {
    definirErro("");
    definirEnviando(grupo.padrinho_id);
    const texto = mensagem(grupo);
    try {
      if (estreita) {
        const arquivos = [];
        for (const i of grupo.aMandar) {
          const { blob, nomeArquivo } = await obterAgradecimento(i.apadrinhamento_id);
          arquivos.push(new File([blob], nomeArquivo, { type: "image/png" }));
        }
        if (podeCompartilharArquivo(arquivos[0])) {
          try {
            await navigator.share({ files: arquivos, text: texto });
          } catch (e) {
            // Fechou a folha sem mandar: nao marca.
            if (e?.name === "AbortError") return;
            throw e;
          }
        } else {
          for (const i of grupo.aMandar) await baixarAgradecimento(i.apadrinhamento_id);
          const link = linkWhatsapp(grupo.whatsapp, texto);
          if (link) window.open(link, "_blank", "noopener");
        }
      } else {
        // A aba abre ANTES do download: depois de um await o navegador ja nao
        // considera o clique e bloqueia a janela como pop-up.
        const link = linkWeb(grupo.whatsapp, texto);
        if (link) window.open(link, "whatsapp-natal-lumen");
        for (const i of grupo.aMandar) {
          await baixarAgradecimento(i.apadrinhamento_id);
          await esperar(400);
        }
      }
      await marcar(grupo);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirEnviando(null);
    }
  }

  return (
    <section className="painel">
      <h2 className="painel__titulo">Mandar o agradecimento a cada padrinho</h2>
      <p className="emlote__numeros">
        <strong>{jaReceberam}</strong> de <strong>{comAgradecimento.length}</strong> padrinho(s) já
        receberam.
      </p>
      <p className="campo__dica">
        {estreita
          ? "Enviar abre o compartilhar do celular com a imagem e o texto: escolha o WhatsApp e o contato."
          : "Enviar baixa o agradecimento e abre a conversa no WhatsApp Web, com o texto pronto. Arraste a imagem para a conversa e envie."}
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>

      <div className="barra-acoes">
        <Button size="sm" variant="ghost" onClick={() => definirSoFaltam((v) => !v)}>
          {soFaltam ? "Mostrar todos" : "Mostrar só quem falta"}
        </Button>
      </div>

      <ul className="emlote__envios">
        {mostrados.map((g) => {
          const semTelefone = !numeroLimpo(g.whatsapp);
          return (
            <li key={g.padrinho_id} className="emlote__envio">
              <div className="emlote__envio-texto">
                <div className="emlote__nome">{g.padrinho}</div>
                <div className="campo__dica emlote__envio-criancas">
                  {g.itens
                    .map((i) => `${i.crianca_codigo} · ${primeiroNome(i.crianca)}${i.desistiu ? " (desistiu)" : ""}`)
                    .join(" · ")}
                </div>
                {g.enviado ? (
                  <span className="etiqueta etiqueta--ok">
                    <Visto t={10} /> enviado {formatarDataHora(g.enviadoEm)}
                  </span>
                ) : semTelefone ? (
                  <span className="etiqueta etiqueta--parado">sem telefone</span>
                ) : null}
              </div>
              <div className="emlote__envio-acoes">
                {semTelefone ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    iconLeft={<Baixar t={14} />}
                    disabled={!g.aMandar.length}
                    onClick={async () => {
                      for (const i of g.aMandar) await baixarAgradecimento(i.apadrinhamento_id);
                    }}
                  >
                    Baixar
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant={g.enviado ? "ghost" : "suave"}
                    iconLeft={<Conversa t={14} />}
                    carregando={enviando === g.padrinho_id}
                    disabled={!g.aMandar.length || (enviando !== null && enviando !== g.padrinho_id)}
                    onClick={() => enviar(g)}
                  >
                    {g.enviado ? "Enviar de novo" : "Enviar"}
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
