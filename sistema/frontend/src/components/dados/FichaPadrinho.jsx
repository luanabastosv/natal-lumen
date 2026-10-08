import { useState } from "react";
import BotaoIcone from "../core/BotaoIcone.jsx";
import Button from "../core/Button.jsx";
import { Baixar, Desfazer, Enviar } from "../core/icones.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import ApadrinharCriancas from "./ApadrinharCriancas.jsx";
import RegistrarPagamento from "./RegistrarPagamento.jsx";
import { useNotificar } from "../../contexts/useNotificar.js";
import { useSessao } from "../../contexts/useSessao.js";
import { salvarBlob } from "../../services/api.js";
import {
  apagarApadrinhamento,
  baixarAgradecimento,
  baixarTodosAgradecimentos,
  detalharPadrinho,
  editarPadrinho,
  enviarAgradecimento,
  obterAgradecimento,
} from "../../services/padrinhos.js";
import { dinheiro, formatarDataHora } from "../../utils/dinheiro.js";
import { primeiroNome } from "../../utils/nomes.js";
import { linkWhatsapp, podeCompartilharArquivo } from "../../utils/whatsapp.js";
import EtiquetaDesistente from "../core/EtiquetaDesistente.jsx";

const TIPOS = { cesta: "Cesta", festa: "Festa" };

/** A ficha de um padrinho: os dados dele e TODAS as criancas apadrinhadas.
 *
 * Esta janela existe por causa do volume. Um padrinho pode apadrinhar dez ou
 * quinze criancas, e cada apadrinhamento tem tres acoes (agradecimento, WhatsApp,
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
  // Desfazer engano de captacao. Quem capta corrige o que acabou de digitar;
  // desfazer um apadrinhamento JA PAGO mexe onde ha dinheiro, e e da
  // coordenacao.
  podeExcluir = false,
  aoMudar,
  // Quem registra pagamento nao e quem edita padrinho: sao duas permissoes
  // diferentes, e ha comissario que so faz uma das duas.
  podePagar = false,
  // A linha da planilha tem um atalho que abre esta ficha ja no
  // formulario de apadrinhar.
  iniciarLigando = false,
}) {
  const [erro, definirErro] = useState("");
  const notificar = useNotificar();
  const { usuario, vinculoAtivo } = useSessao();

  // O comissario de base so mexe no apadrinhamento que ele mesmo registrou —
  // um padrinho recebe criancas de varios, e desfazer o do colega mudaria o
  // trabalho de outra pessoa sem ela saber. Quem coordena passa por cima.
  const soMinhas = Boolean(vinculoAtivo?.so_criancas_atribuidas);
  const meu = (a) => !soMinhas || a.comissario_id === usuario?.id;

  // Qual das duas perguntas da captacao esta sendo salva. Elas sao respondidas
  // numa conversa que quase nunca e a do cadastro — o doador diz "esse ano
  // quero contribuir todo mes" semanas depois —, entao tem de dar para mudar
  // aqui, e nao so no formulario de criar.
  const [salvandoCampo, definirSalvandoCampo] = useState("");

  async function responder(campo, valor) {
    definirErro("");
    definirSalvandoCampo(campo);
    try {
      aoMudar?.(await editarPadrinho(padrinho.id, { [campo]: valor }));
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvandoCampo("");
    }
  }

  /* Tres estados, e o vazio NAO e "nao": e "ninguem perguntou". Um select de
     sim/nao obrigaria a responder por quem nunca foi perguntado — e e
     justamente a lista dos que faltam perguntar que a captacao reaproveita no
     ano seguinte. */
  /* Funcao que devolve JSX, e nao componente: declarado aqui dentro, um
     componente nasceria diferente a cada render e o <select> remontaria —
     perdendo o foco de quem estava respondendo. */
  function resposta(campo, valor) {
    if (!podeEditar) {
      return <dd>{valor === true ? "Sim" : valor === false ? "Não" : "a perguntar"}</dd>;
    }
    return (
      <dd>
        <select
          className="campo__controle campo__controle--selecao ficha__resposta"
          value={valor === true ? "sim" : valor === false ? "nao" : ""}
          disabled={salvandoCampo === campo}
          onChange={(e) =>
            responder(campo, e.target.value === "" ? null : e.target.value === "sim")
          }
        >
          <option value="">a perguntar</option>
          <option value="sim">Sim</option>
          <option value="nao">Não</option>
        </select>
      </dd>
    );
  }

  // Qual agradecimento esta sendo gerado ou enviado: o PNG e montado no
  // servidor e demora um instante, entao aquele bloco precisa dizer que esta
  // ocupado.
  //
  // "Agradecimento", e nunca "cartao": cartao e so o de cesta e o de festa, o
  // papel que a crianca escreve. O agradecimento e a arte que o sistema monta.
  const [baixandoAgradecimento, definirBaixandoAgradecimento] = useState(null);
  const [baixandoTodos, definirBaixandoTodos] = useState(false);
  const [enviando, definirEnviando] = useState(null);
  const [desfazendo, definirDesfazendo] = useState(null);
  // Qual apadrinhamento PAGO esta esperando confirmacao. Promessa se desfaz num
  // clique — nada se perde, e quem capta erra e corrige na mesma conversa. Com
  // pagamento e outra coisa: o dinheiro fica no caixa sem destino, e isso tem
  // de estar escrito na frente de quem clica, nao na dica do mouse.
  const [aDesfazer, definirADesfazer] = useState(null);

  // Uma aba, nao paineis que abrem e fecham. Paineis inseridos no meio da
  // janela empurravam a lista para baixo a cada clique: a pessoa apertava um
  // botao e o que ela estava lendo mudava de lugar. A faixa de abas fica
  // sempre no mesmo ponto e so o conteudo abaixo dela troca.
  const [aba, definirAba] = useState(iniciarLigando ? "apadrinhar" : "criancas");


  const zap = linkWhatsapp(padrinho.whatsapp);

  const aPagar = padrinho.apadrinhamentos.filter((a) => !a.pago).length;

  // Um agradecimento por crianca, e nao por apadrinhamento: cesta e festa da
  // mesma crianca sao o mesmo agradecimento. E a mesma conta que o servidor
  // faz no ZIP.
  const agradecimentosProntos = new Set(
    padrinho.apadrinhamentos.filter((a) => a.pago).map((a) => a.crianca_id),
  ).size;

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
        // Curto de proposito: a aba divide a largura com as outras duas, e
        // no celular um rotulo longo era cortado no meio da palavra.
        contagem: aPagar === 0 ? "tudo confirmado" : `${aPagar} a confirmar`,
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
    definirDesfazendo(apadrinhamento.id);
    try {
      await apagarApadrinhamento(apadrinhamento.id);
      definirADesfazer(null);
      await recarregar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirDesfazendo(null);
    }
  }

  async function baixarUm(apadrinhamento) {
    definirErro("");
    definirBaixandoAgradecimento(apadrinhamento.id);
    try {
      await baixarAgradecimento(apadrinhamento.id);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirBaixandoAgradecimento(null);
    }
  }

  async function baixarTodos() {
    definirErro("");
    definirBaixandoTodos(true);
    try {
      await baixarTodosAgradecimentos(padrinho.id);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirBaixandoTodos(false);
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
    definirEnviando(apadrinhamento.id);
    try {
      await enviarAgradecimento(apadrinhamento.id);
      notificar(
        `Agradecimento de ${apadrinhamento.crianca_primeiro_nome} enviado para ` +
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
        `Segue o nosso agradecimento.`;

      const arquivo = new File([blob], nomeArquivo, { type: "image/png" });
      if (podeCompartilharArquivo(arquivo)) {
        await navigator.share({ files: [arquivo], text: texto });
        return;
      }

      salvarBlob(blob, nomeArquivo);
      const link = linkWhatsapp(padrinho.whatsapp, texto);
      if (link) window.open(link, "_blank", "noopener");
      notificar(
        `Agradecimento de ${apadrinhamento.crianca_primeiro_nome} baixado. ` +
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
        {/* As duas perguntas da captacao. Ficam junto do contato, e nao no fim:
            e o mesmo assunto — quem e esta pessoa para a campanha — e nao o
            dinheiro que ela ja pos. */}
        <dt>Membro Ser Feliz</dt>
        {resposta("membro_ser_feliz", padrinho.membro_ser_feliz)}
        <dt>Contribuição mensal</dt>
        {resposta("interesse_mensal", padrinho.interesse_mensal)}
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
            <>
              <div className="ficha__lista">
                {padrinho.apadrinhamentos.map((a) => (
                  <div key={a.id} className="ficha__linha">
                    <div className="ficha__linha-corpo">
                      <span className="ficha__linha-etiquetas">
                        <span className="etiqueta etiqueta--neutra">{TIPOS[a.tipo] ?? a.tipo}</span>
                        <span className={`etiqueta ${a.pago ? "etiqueta--ok" : "etiqueta--espera"}`}>
                          {a.pago ? "confirmado" : "promessa · falta pagar"}
                        </span>
                        {a.cartao_status === "enviado" && (
                          <span
                            className="etiqueta etiqueta--ok"
                            title={
                              a.cartao_enviado_em
                                ? `Agradecimento enviado em ${formatarDataHora(a.cartao_enviado_em)}`
                                : "Agradecimento já enviado"
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
                        {/* Quem trouxe esta criança. Um padrinho é captado por
                            mais de um comissário ao longo da campanha, e sem
                            isto a lista fica um monte de nomes sem dono: dois
                            comissários cobram o mesmo doador pela mesma cesta,
                            ou nenhum dos dois cobra.

                            Texto discreto, e não etiqueta: as etiquetas desta
                            linha são o ESTADO daquela criança — o que falta
                            fazer com ela. Quem registrou não é estado, é
                            procedência, e em pílula competia com "a pagar" pela
                            mesma atenção. O nome completo fica na dica do mouse,
                            para dois comissários de mesmo primeiro nome. */}
                        {a.comissario && (
                          <span
                            className="ficha__linha-autor"
                            title={`Apadrinhamento registrado por ${a.comissario}`}
                          >
                            comissário: {primeiroNome(a.comissario)}
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
                        {/* O padrinho ja pagou por quem nao vai: e aqui que a
                            coordenacao percebe e decide o que fazer com ele. */}
                        {a.crianca_desistiu_em && <EtiquetaDesistente className="etiqueta--ao-lado" />}
                      </span>
                    </div>

                    {/* Tres acoes repetidas por crianca: escritas, uma ficha de vinte
                        criancas virava sessenta pilulas. O rotulo nao sumiu — virou a
                        dica do mouse e o nome no leitor de tela. */}
                    <span className="ficha__linha-acoes">
                      {/* O agradecimento e pela doacao: enquanto e promessa nao ha o
                          que agradecer, e o servidor recusa (409). Sem o botao,
                          ninguem clica para receber um erro. O envio pelo
                          WhatsApp segue a mesma regra, pelo mesmo motivo. */}
                      {a.pago && (
                        <>
                          <BotaoIcone
                            titulo={`Baixar o agradecimento de ${a.crianca_primeiro_nome}`}
                            onClick={() => baixarUm(a)}
                            carregando={baixandoAgradecimento === a.id}
                          >
                            <Baixar t={16} />
                          </BotaoIcone>
                          <BotaoIcone
                            titulo={
                              padrinho.whatsapp
                                ? `${a.cartao_status === "enviado" ? "Reenviar" : "Enviar"} o agradecimento de ` +
                                  `${a.crianca_primeiro_nome} pelo WhatsApp`
                                : "Este padrinho não tem WhatsApp cadastrado"
                            }
                            onClick={() => enviarNoWhatsapp(a)}
                            disabled={!padrinho.whatsapp}
                            carregando={enviando === a.id}
                          >
                            <Enviar t={16} />
                          </BotaoIcone>
                        </>
                      )}
                      {/* Sem pagamento, quem capta desfaz. Com pagamento, so a
                          coordenacao — e a dica diz o que vai acontecer com o
                          dinheiro, porque ele NAO some junto. */}
                      {((podeEditar && !a.pago && meu(a)) || podeExcluir) && (
                        <BotaoIcone
                          perigo
                          titulo={
                            a.pago
                              ? `Desfazer o apadrinhamento de ${a.crianca_primeiro_nome}. ` +
                                "O pagamento continua no caixa, sem destino."
                              : `Desfazer o apadrinhamento de ${a.crianca_primeiro_nome}`
                          }
                          onClick={() => (a.pago ? definirADesfazer(a) : desligar(a))}
                          carregando={desfazendo === a.id}
                        >
                          <Desfazer t={16} />
                        </BotaoIcone>
                      )}
                    </span>
                  </div>
                ))}
              </div>
              {/* Depois da lista: primeiro se ve quais criancas estao pagas,
                  depois se baixa o agradecimento de todas de uma vez. */}
              {agradecimentosProntos > 0 && (
                <div className="barra-acoes ficha__baixar-agradecimentos">
                  {/* A dica antes do botao: com a barra alinhada a direita, e
                      o botao que fica na ponta, onde o olho termina a lista. */}
                  {agradecimentosProntos > 1 && (
                    <span className="campo__dica">Num arquivo .zip, um por criança paga.</span>
                  )}
                  <Button
                    size="sm"
                    variant="secondary"
                    iconLeft={<Baixar t={14} />}
                    onClick={baixarTodos}
                    carregando={baixandoTodos}
                  >
                    {agradecimentosProntos === 1
                      ? "Baixar agradecimento"
                      : `Baixar os ${agradecimentosProntos} agradecimentos`}
                  </Button>
                </div>
              )}
            </>
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

      {/* Por cima da ficha, e nao no lugar dela: a pessoa decide sem perder de
          vista de qual padrinho e a lista. */}
      {aDesfazer && (
        <Modal
          rotulo="Apadrinhamento pago"
          titulo={`Desfazer o apadrinhamento de ${aDesfazer.crianca_primeiro_nome}?`}
          aoFechar={() => desfazendo === null && definirADesfazer(null)}
          rodape={
            <div className="barra-acoes barra-acoes--fim" style={{ marginTop: 0 }}>
              <Button
                variant="perigo"
                onClick={() => desligar(aDesfazer)}
                carregando={desfazendo === aDesfazer.id}
              >
                {desfazendo === aDesfazer.id ? "Desfazendo..." : "Desfazer mesmo assim"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => definirADesfazer(null)}
                disabled={desfazendo === aDesfazer.id}
              >
                Cancelar
              </Button>
            </div>
          }
        >
          <p className="exclusao__texto">
            <strong>{aDesfazer.crianca_nome}</strong> volta a ficar disponível para
            apadrinhar, e este apadrinhamento sai das contas do painel.
          </p>
          {/* Sem valor escrito: um mesmo pagamento pode quitar varias criancas
              deste padrinho, e o valor do apadrinhamento nao e o do pagamento. */}
          <Mensagem tipo="aviso">
            O pagamento <strong>continua no caixa</strong>, agora sem este destino — o
            dinheiro entrou de verdade e não desaparece por causa de um engano de cadastro.
            A diferença passa a aparecer na ficha, entre o combinado e o pago.
          </Mensagem>
        </Modal>
      )}
    </Modal>
  );
}
