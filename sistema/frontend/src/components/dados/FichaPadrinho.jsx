import { useState } from "react";
import { useNavigate } from "react-router-dom";
import BotaoIcone from "../core/BotaoIcone.jsx";
import Button from "../core/Button.jsx";
import { Baixar, Desfazer, Enviar } from "../core/icones.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import ApadrinharCriancas from "./ApadrinharCriancas.jsx";
import RegistrarPagamento from "./RegistrarPagamento.jsx";
import { useSessao } from "../../contexts/useSessao.js";
import {
  apagarApadrinhamento,
  baixarAgradecimento,
  baixarTodosAgradecimentos,
  detalharPadrinho,
} from "../../services/padrinhos.js";
import { dinheiro, formatarDataHora } from "../../utils/dinheiro.js";
import { primeiroNome } from "../../utils/nomes.js";
import { linkWhatsapp } from "../../utils/whatsapp.js";
import useTelaEstreita from "../../hooks/useTelaEstreita.js";
import EtiquetaDesistente from "../core/EtiquetaDesistente.jsx";

const TIPOS = { cesta: "Cesta", festa: "Festa" };
// Ate quantos agradecimentos o "baixar todos" entrega soltos; acima, num ZIP.
const LIMITE_SOLTOS = 10;

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
}) {
  const [erro, definirErro] = useState("");
  const { usuario, vinculoAtivo } = useSessao();

  // O comissario de base so mexe no apadrinhamento que ele mesmo registrou —
  // um padrinho recebe criancas de varios, e desfazer o do colega mudaria o
  // trabalho de outra pessoa sem ela saber. Quem coordena passa por cima.
  const soMinhas = Boolean(vinculoAtivo?.so_criancas_atribuidas);
  const meu = (a) => !soMinhas || a.comissario_id === usuario?.id;

  /* As duas perguntas da captacao, so para ler. Responder e no cadastro
     ("Editar informacoes", no menu da linha), que exige Sim ou Nao — a ficha
     nao tem mais seletor. "a perguntar" so aparece em cadastro antigo, de
     antes de as perguntas serem obrigatorias. */
  function resposta(valor) {
    return <dd>{valor === true ? "Sim" : valor === false ? "Não" : "a perguntar"}</dd>;
  }

  // Qual agradecimento esta sendo gerado ou enviado: o PNG e montado no
  // servidor e demora um instante, entao aquele bloco precisa dizer que esta
  // ocupado.
  //
  // "Agradecimento", e nunca "cartao": cartao e so o de cesta e o de festa, o
  // papel que a crianca escreve. O agradecimento e a arte que o sistema monta.
  const [baixandoAgradecimento, definirBaixandoAgradecimento] = useState(null);
  const [baixandoTodos, definirBaixandoTodos] = useState(false);
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
  const [aba, definirAba] = useState("criancas");
  // O passo a passo de apadrinhar abre POR CIMA da ficha, numa janela propria:
  // e uma tarefa com comeco, meio e fim, e nao mais uma aba para olhar.
  const podeApadrinhar = podeEditar && podePagar;
  const [apadrinhando, definirApadrinhando] = useState(false);
  const estreita = useTelaEstreita();
  const navegar = useNavigate();

  /** No celular o passo a passo e uma pagina; no computador, uma janela por
   *  cima da ficha. */
  function apadrinhar() {
    if (estreita) navegar(`/padrinhos/${padrinho.id}/apadrinhar`);
    else definirApadrinhando(true);
  }


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
    podePagar &&
      padrinho.apadrinhamentos.length > 0 && {
        id: "pagamento",
        rotulo: "Pagamentos",
        // Curto de proposito: a aba divide a largura com as outras duas, e
        // no celular um rotulo longo era cortado no meio da palavra. As
        // promessas sao as de antes de o pagamento entrar junto.
        contagem: aPagar === 0 ? "comprovantes" : `${aPagar} promessa(s)`,
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

  /** Ate dez, um arquivo por crianca, soltos — e o que se anexa direto na
   *  conversa com o padrinho. Acima de dez, um ZIP: quinze downloads soltos
   *  viram bagunca na pasta.
   *
   *  Em serie e com uma pausa curta: disparados juntos, o navegador descarta
   *  parte dos downloads. Na primeira vez o Chrome pergunta se o site pode
   *  baixar varios arquivos — e preciso permitir. */
  async function baixarTodos() {
    definirErro("");
    definirBaixandoTodos(true);
    try {
      if (agradecimentosProntos > LIMITE_SOLTOS) {
        await baixarTodosAgradecimentos(padrinho.id);
      } else {
        const porCrianca = new Map();
        for (const a of padrinho.apadrinhamentos) {
          if (a.pago && !porCrianca.has(a.crianca_id)) porCrianca.set(a.crianca_id, a);
        }
        for (const a of porCrianca.values()) {
          await baixarAgradecimento(a.id);
          await new Promise((pronto) => setTimeout(pronto, 400));
        }
      }
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirBaixandoTodos(false);
    }
  }

  /** Abre a conversa com o padrinho no WhatsApp, com a mensagem pronta.
   *
   * So abre: a imagem nao vai por aqui. O link do WhatsApp carrega so texto,
   * e o agradecimento quem baixa e o comissario, pelo botao de baixar ao lado
   * (ou o ZIP de todos), para anexar na conversa que este abre.
   *
   * O envio automatico pela Cloud API da Meta esta DESLIGADO de proposito: o
   * agradecimento sai da conversa de quem captou o padrinho, e nao de um
   * numero do sistema. A rota do servidor (/agradecimento/enviar) continua
   * existindo, so nao e mais chamada daqui.
   *
   * Sincrono de proposito: o `window.open` no mesmo clique nao e barrado como
   * pop-up, e depois de um `await` seria.
   */
  function abrirWhatsapp(apadrinhamento) {
    const texto =
      `Oi, ${padrinho.nome.split(" ")[0]}! Obrigado por apadrinhar ` +
      `${apadrinhamento.crianca_primeiro_nome} no Natal Lumen. ` +
      `Segue o nosso agradecimento.`;
    const link = linkWhatsapp(padrinho.whatsapp, texto);
    if (link) window.open(link, "_blank", "noopener");
  }

  return (
    <Modal
      rotulo="Nome do padrinho:"
      titulo={padrinho.nome}
      aoFechar={aoFechar}
      tamanho="grande"
      /* As duas acoes da ficha no pe, uma de cada lado: um so botao cheio, o
         de apadrinhar, que e o que se vem fazer aqui. Baixar o ZIP so aparece
         com mais de uma crianca paga — com uma, o icone na linha dela ja e o
         caminho, e um segundo botao para a mesma coisa so pesaria. */
      rodape={
        (agradecimentosProntos > 1 || podeApadrinhar) && (
          <div className="ficha__rodape">
            {agradecimentosProntos > 1 && (
              <Button
                size="sm"
                variant="ghost"
                iconLeft={<Baixar t={14} />}
                onClick={baixarTodos}
                carregando={baixandoTodos}
                titulo={
                  agradecimentosProntos > LIMITE_SOLTOS
                    ? "Num arquivo .zip, um por criança paga"
                    : "Um arquivo por criança paga"
                }
              >
                Baixar os {agradecimentosProntos} agradecimentos
              </Button>
            )}
            {podeApadrinhar && (
              <Button size="sm" variant="primary" onClick={apadrinhar}>
                Apadrinhar uma criança
              </Button>
            )}
          </div>
        )
      }
    >
      <Mensagem tipo="erro">{erro}</Mensagem>

      <dl className="ficha ficha--duas">
        <dt>Edição</dt>
        <dd>
          {padrinho.edicao}
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
        {/* Numa linha so, cortado com reticencias: o email inteiro fica na dica
            do mouse e no proprio link. Quebrado em duas, empurrava a ficha. */}
        <dd className="ficha__truncar" title={padrinho.email || undefined}>
          {padrinho.email ? <a href={`mailto:${padrinho.email}`}>{padrinho.email}</a> : "—"}
        </dd>
        {/* As duas perguntas da captacao. Ficam junto do contato, e nao no fim:
            e o mesmo assunto — quem e esta pessoa para a campanha — e nao o
            dinheiro que ela ja pos. */}
        <dt>Membro Ser Feliz</dt>
        {resposta("membro_ser_feliz", padrinho.membro_ser_feliz)}
        <dt>Contribuição mensal</dt>
        {resposta("interesse_mensal", padrinho.interesse_mensal)}
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
                              zap
                                ? `Abrir a conversa com ${padrinho.nome.split(" ")[0]} no WhatsApp, ` +
                                  `com o agradecimento de ${a.crianca_primeiro_nome} escrito`
                                : "Este padrinho não tem WhatsApp válido cadastrado"
                            }
                            onClick={() => abrirWhatsapp(a)}
                            disabled={!zap}
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
            </>
          ))}


        {aba === "pagamento" && (
          <RegistrarPagamento
            padrinho={padrinho}
            aoFechar={voltarParaLista}
            aoRegistrar={recarregar}
          />
        )}
      </div>

      {apadrinhando && (
        <ApadrinharCriancas
          padrinho={padrinho}
          aoMudar={aoMudar}
          aoFechar={() => {
            definirApadrinhando(false);
            voltarParaLista();
          }}
        />
      )}

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
