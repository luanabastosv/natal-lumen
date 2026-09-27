import { useState } from "react";
import BotaoIcone from "../core/BotaoIcone.jsx";
import { Baixar, Desfazer, Enviar } from "../core/icones.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import ApadrinharCriancas from "./ApadrinharCriancas.jsx";
import RegistrarPagamento from "./RegistrarPagamento.jsx";
import { salvarBlob } from "../../services/api.js";
import {
  apagarApadrinhamento,
  baixarAgradecimento,
  detalharPadrinho,
  enviarAgradecimento,
  obterAgradecimento,
} from "../../services/padrinhos.js";
import { dinheiro, formatarDataHora } from "../../utils/dinheiro.js";
import { linkWhatsapp, podeCompartilharArquivo } from "../../utils/whatsapp.js";

const TIPOS = { cesta: "Cesta", festa: "Festa" };

/** A ficha de um padrinho: os dados dele e TODAS as criancas apadrinhadas.
 *
 * Esta janela existe por causa do volume. Um padrinho pode apadrinhar dez ou
 * quinze criancas, e cada apadrinhamento tem tres acoes (cartao, WhatsApp,
 * desfazer). Na planilha isso virava uma linha de altura indefinida com
 * dezenas de botoes; aqui cada crianca ganha o proprio bloco, com espaco.
 *
 * A janela nao tem estado proprio do padrinho: le da prop e, depois de cada
 * mudanca, recarrega e devolve o padrinho novo pelo `aoMudar`. Assim a linha
 * da planilha atras e o conteudo da janela nunca divergem.
 */
export default function FichaPadrinho({
  padrinho,
  aoFechar,
  podeEditar = false,
  aoMudar,
  // Quem registra pagamento nao e quem edita padrinho: sao duas permissoes
  // diferentes, e ha comissario que so faz uma das duas.
  podePagar = false,
  // A linha da planilha tem um atalho que abre esta ficha ja no
  // formulario de apadrinhar.
  iniciarLigando = false,
}) {
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");

  // Qual cartao esta sendo gerado ou enviado: o PNG e montado no servidor e
  // demora um instante, entao aquele bloco precisa dizer que esta ocupado.
  const [baixandoCartao, definirBaixandoCartao] = useState(null);
  const [enviando, definirEnviando] = useState(null);
  const [desfazendo, definirDesfazendo] = useState(null);

  // Uma aba, nao paineis que abrem e fecham. Paineis inseridos no meio da
  // janela empurravam a lista para baixo a cada clique: a pessoa apertava um
  // botao e o que ela estava lendo mudava de lugar. A faixa de abas fica
  // sempre no mesmo ponto e so o conteudo abaixo dela troca.
  const [aba, definirAba] = useState(iniciarLigando ? "apadrinhar" : "criancas");


  const zap = linkWhatsapp(padrinho.whatsapp);

  const aPagar = padrinho.apadrinhamentos.filter((a) => !a.pago).length;

  // A contagem vive no rotulo da aba: e o que diz se vale a pena entrar nela.
  const abas = [
    {
      id: "criancas",
      rotulo: "Crianças",
      contagem: `${padrinho.apadrinhamentos.length} apadrinhada(s)`,
    },
    podeEditar && { id: "apadrinhar", rotulo: "Apadrinhar", contagem: "ligar mais uma" },
    podePagar &&
      padrinho.apadrinhamentos.length > 0 && {
        id: "pagamento",
        rotulo: "Pagamento",
        contagem: aPagar === 0 ? "tudo quitado" : `${aPagar} a pagar`,
      },
  ].filter(Boolean);

  async function recarregar() {
    aoMudar?.(await detalharPadrinho(padrinho.id));
  }

  /** Terminou a acao: volta para a lista, que e de onde se olha o resultado. */
  function voltarParaLista() {
    definirAba("criancas");
  }

  async function desligar(apadrinhamento) {
    definirErro("");
    definirSucesso("");
    definirDesfazendo(apadrinhamento.id);
    try {
      await apagarApadrinhamento(apadrinhamento.id);
      await recarregar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirDesfazendo(null);
    }
  }

  async function baixarCartao(apadrinhamento) {
    definirErro("");
    definirBaixandoCartao(apadrinhamento.id);
    try {
      await baixarAgradecimento(apadrinhamento.id);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirBaixandoCartao(null);
    }
  }

  /** Manda a arte para o WhatsApp do padrinho.
   *
   * Caminho principal: o servidor envia sozinho pela Cloud API da Meta.
   * Se o servidor nao tiver credenciais (503), cai no envio a mao — no
   * celular pela folha de compartilhar nativa, que entrega o PNG de verdade;
   * no desktop baixando o arquivo e abrindo a conversa com o texto pronto,
   * porque o link do WhatsApp so aceita texto, nunca anexo.
   */
  async function enviarNoWhatsapp(apadrinhamento) {
    definirErro("");
    definirSucesso("");
    definirEnviando(apadrinhamento.id);
    try {
      await enviarAgradecimento(apadrinhamento.id);
      definirSucesso(
        `Cartão de ${apadrinhamento.crianca_primeiro_nome} enviado para ` +
          `${padrinho.nome.split(" ")[0]} no WhatsApp.`,
      );
      await recarregar();
    } catch (e) {
      // 503 = este servidor nao tem a Cloud API ligada. Qualquer outro erro
      // (numero invalido, recusa da Meta) e erro de verdade e tem de aparecer.
      if (e.status !== 503) {
        definirErro(e.message);
        return;
      }
      await enviarAMao(apadrinhamento);
    } finally {
      definirEnviando(null);
    }
  }

  /** Reserva: sem Cloud API, quem envia e a pessoa. */
  async function enviarAMao(apadrinhamento) {
    try {
      const { blob, nomeArquivo } = await obterAgradecimento(apadrinhamento.id);
      const texto =
        `Oi, ${padrinho.nome.split(" ")[0]}! Obrigado por apadrinhar ` +
        `${apadrinhamento.crianca_primeiro_nome} no Natal Lumen. ` +
        `Segue o cartão de agradecimento.`;

      const arquivo = new File([blob], nomeArquivo, { type: "image/png" });
      if (podeCompartilharArquivo(arquivo)) {
        await navigator.share({ files: [arquivo], text: texto });
        return;
      }

      salvarBlob(blob, nomeArquivo);
      const link = linkWhatsapp(padrinho.whatsapp, texto);
      if (link) window.open(link, "_blank", "noopener");
      definirSucesso(
        `Cartão de ${apadrinhamento.crianca_primeiro_nome} baixado. ` +
          "Arraste a imagem para a conversa que abriu.",
      );
    } catch (e) {
      // Fechar a folha de compartilhar nao e erro.
      if (e.name !== "AbortError") definirErro(e.message);
    }
  }

  return (
    <Modal
      rotulo="Nome do padrinho:"
      titulo={padrinho.nome}
      aoFechar={aoFechar}
      tamanho="grande"
    >
      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      <dl className="ficha ficha--duas">
        <dt>Edição</dt>
        <dd>
          {padrinho.cidade} {padrinho.ano}
        </dd>
        <dt>WhatsApp</dt>
        <dd>
          {padrinho.whatsapp ? (
            zap ? (
              <a href={zap} target="_blank" rel="noopener noreferrer">
                {padrinho.whatsapp}
              </a>
            ) : (
              padrinho.whatsapp
            )
          ) : (
            "—"
          )}
        </dd>
        <dt>Email</dt>
        <dd>
          {padrinho.email ? <a href={`mailto:${padrinho.email}`}>{padrinho.email}</a> : "—"}
        </dd>
        <dt>Combinado</dt>
        <dd>{dinheiro(padrinho.total_combinado)}</dd>
        <dt>Pago</dt>
        <dd>{dinheiro(padrinho.total_pago)}</dd>
        {padrinho.observacoes && (
          <>
            <dt className="ficha__dt-largo">Observações</dt>
            <dd className="ficha__dd-largo">{padrinho.observacoes}</dd>
          </>
        )}
      </dl>
      {/* A faixa de abas nao sai do lugar: so o que esta abaixo dela troca.
          Antes, cada botao inseria um painel entre o titulo e a lista, e a
          lista descia — apertar um botao mudava de lugar o que se estava
          lendo. E por isso que o amarelo saiu tambem: aquele fundo existia
          para marcar "isto apareceu agora", e agora nada aparece do nada. */}
      {abas.length > 1 && (
        <div className="abas abas--ficha" role="tablist">
          {abas.map((a) => (
            <button
              key={a.id}
              type="button"
              role="tab"
              aria-selected={aba === a.id}
              className={`aba ${aba === a.id ? "aba--ativa" : ""}`}
              onClick={() => {
                definirAba(a.id);
              }}
            >
              <span>{a.rotulo}</span>
              <span className="aba__contagem">{a.contagem}</span>
            </button>
          ))}
        </div>
      )}

      <div role="tabpanel" aria-label={abas.find((a) => a.id === aba)?.rotulo}>
        {aba === "criancas" &&
          (padrinho.apadrinhamentos.length === 0 ? (
            <p className="campo__dica" style={{ marginTop: 0 }}>
              Este padrinho ainda não apadrinhou ninguém.
            </p>
          ) : (
            <div className="ficha__lista">
              {padrinho.apadrinhamentos.map((a) => (
                <div key={a.id} className="ficha__linha">
                  <div className="ficha__linha-corpo">
                    <span className="ficha__linha-etiquetas">
                      <span className="etiqueta etiqueta--neutra">{TIPOS[a.tipo] ?? a.tipo}</span>
                      <span className={`etiqueta ${a.pago ? "etiqueta--ok" : "etiqueta--espera"}`}>
                        {a.pago ? "pago" : "a pagar"}
                      </span>
                      {a.cartao_status === "enviado" && (
                        <span
                          className="etiqueta etiqueta--ok"
                          title={
                            a.cartao_enviado_em
                              ? `Cartão enviado em ${formatarDataHora(a.cartao_enviado_em)}`
                              : "Cartão já enviado"
                          }
                        >
                          enviado
                        </span>
                      )}
                      {a.cartao_status === "falhou" && (
                        <span className="etiqueta etiqueta--espera" title="O último envio falhou">
                          falhou
                        </span>
                      )}
                    </span>

                    {/* Codigo na frente do nome completo: e assim que a linha
                        aqui casa com a linha da planilha de criancas. */}
                    <span
                      className="ficha__linha-nome"
                      title={`${a.crianca_codigo} · ${a.crianca_nome}`}
                    >
                      <span className="ficha__linha-codigo">{a.crianca_codigo}</span>
                      {a.crianca_nome}, {a.crianca_idade}
                    </span>
                  </div>

                  {/* Tres acoes repetidas por crianca: escritas, uma ficha de vinte
                      criancas virava sessenta pilulas. O rotulo nao sumiu — virou a
                      dica do mouse e o nome no leitor de tela. */}
                  <span className="ficha__linha-acoes">
                    <BotaoIcone
                      titulo={`Baixar o cartão de ${a.crianca_primeiro_nome}`}
                      onClick={() => baixarCartao(a)}
                      carregando={baixandoCartao === a.id}
                    >
                      <Baixar t={16} />
                    </BotaoIcone>
                    <BotaoIcone
                      titulo={
                        padrinho.whatsapp
                          ? `${a.cartao_status === "enviado" ? "Reenviar" : "Enviar"} o cartão de ` +
                            `${a.crianca_primeiro_nome} pelo WhatsApp`
                          : "Este padrinho não tem WhatsApp cadastrado"
                      }
                      onClick={() => enviarNoWhatsapp(a)}
                      disabled={!padrinho.whatsapp}
                      carregando={enviando === a.id}
                    >
                      <Enviar t={16} />
                    </BotaoIcone>
                    {podeEditar && !a.pago && (
                      <BotaoIcone
                        perigo
                        titulo={`Desfazer o apadrinhamento de ${a.crianca_primeiro_nome}`}
                        onClick={() => desligar(a)}
                        carregando={desfazendo === a.id}
                      >
                        <Desfazer t={16} />
                      </BotaoIcone>
                    )}
                  </span>
                </div>
              ))}
            </div>
          ))}

        {aba === "apadrinhar" && (
          <ApadrinharCriancas
            padrinho={padrinho}
            aoMudar={aoMudar}
            aoTerminar={voltarParaLista}
          />
        )}

        {aba === "pagamento" && (
          <RegistrarPagamento
            padrinho={padrinho}
            aoFechar={voltarParaLista}
            aoRegistrar={recarregar}
          />
        )}
      </div>
    </Modal>
  );
}
