import { useCallback, useEffect, useRef, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import ConferirCartoes from "../components/dados/ConferirCartoes.jsx";
import { Selecao } from "../components/core/Campo.jsx";
import FaixaDeAbas from "../components/core/FaixaDeAbas.jsx";
import { ArquivoIcone, ListaIcone } from "../components/core/icones.jsx";
import MenuAcoes from "../components/core/MenuAcoes.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Progresso from "../components/feedback/Progresso.jsx";
import Modal from "../components/feedback/Modal.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import {
  confirmarLote,
  listarCartoes,
  listarPastas,
  subirLoteDeCartoes,
  urlDaImagem,
  urlDaMiniatura,
  apagarCartao,
  trocarImagemDoCartao,
} from "../services/cartoes.js";
import { formatarDataHora } from "../utils/dinheiro.js";

export default function Cartoes() {
  // A edicao vem da lateral: e a mesma para o sistema inteiro.
  const { pode, edicaoAtiva } = useSessao();

  const [cartoes, definirCartoes] = useState({ itens: [], total: 0 });

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const notificar = useNotificar();

  // Fluxo de digitalizacao
  // Envio em lote: o codigo da crianca vem do NOME DO ARQUIVO.
  const [arquivos, definirArquivos] = useState([]);
  const [tipo, definirTipo] = useState("cesta");
  const [previa, definirPrevia] = useState(null);
  // Quais fotos da previa ja passaram pela conferencia, pelo indice no lote.
  const [conferidos, definirConferidos] = useState([]);
  const [conferindo, definirConferindo] = useState(false);
  const [subindo, definirSubindo] = useState(false);
  const [salvando, definirSalvando] = useState(false);


  // Qual cartao esta aberto para olhar.
  const [vendo, definirVendo] = useState(null);


  // A tela tem dois andares: as pastas (uma por instituicao) e o de dentro de
  // uma delas. `pasta` nulo e o andar de cima.
  //
  // O trabalho com cartao e por instituicao — o monitor recolhe os cartoes de
  // uma escola e confere aquela escola. Numa lista unica, achar os 60 de uma
  // entre 900 era trabalho de filtro, e o filtro sumia a cada recarga.
  const [pastas, definirPastas] = useState([]);
  const [pasta, definirPasta] = useState(null);
  // Dentro da pasta, qual pilha esta na mao: "" e a escola inteira. Cesta e
  // festa sao duas pilhas separadas no mundo real — recolhidas e conferidas uma
  // de cada vez —, e a aba deixa trabalhar numa sem perder de vista a outra.
  const [abaTipo, definirAbaTipo] = useState("");
  // O envio virou janela. Antes era um painel plantado no topo da pasta: ele
  // ocupava meia tela o tempo todo para uma acao que se faz de vez em quando, e
  // empurrava para baixo a lista, que e o que se vem ver aqui.
  const [subindoAberto, definirSubindoAberto] = useState(false);
  /* Lista ou arquivo. Sao duas perguntas diferentes sobre a mesma pasta: a
     lista responde "quem ja entregou o cartao", varrendo nomes de cima a
     baixo; o arquivo responde "e este cartao aqui, de quem e", que e o que se
     faz com uma pilha de papel na mao. Guardado no navegador porque a escolha
     e da PESSOA, nao da pasta: quem prefere um jeito prefere em toda escola, e
     escolher de novo a cada pasta seria cobrar a mesma decisao dez vezes. */
  const [visao, definirVisao] = useState(() => {
    try {
      // Arquivo por padrao: quem chega aqui esta com a pilha de papel na mao e
      // procura UM cartao, e achar pelo desenho e mais rapido que ler nomes.
      return localStorage.getItem("nl_cartoes_visao") === "lista" ? "lista" : "arquivo";
    } catch {
      return "arquivo";
    }
  });

  /* Corrigir um cartao subido errado. A pilha e digitalizada de uma vez, e
     trocar duas fotos de lugar e o erro mais provavel do processo — ate agora
     nao havia como desfazer sem mexer no banco. */
  const [corrigindo, definirCorrigindo] = useState(false);
  const seletorTroca = useRef(null);

  // De QUAL cartao e a correcao em curso. As acoes moram na linha e na
  // miniatura, e nao dentro da janela do cartao aberto: corrigir uma pilha
  // subida errada e varrer a lista mexendo em varios — abrir cada um para
  // chegar no menu cobraria dois cliques a mais por cartao.
  const [trocandoDe, definirTrocandoDe] = useState(null);
  const [apagandoDe, definirApagandoDe] = useState(null);

  function pedirTroca(cartao) {
    definirTrocandoDe(cartao);
    // Zera antes de abrir: sem isto, escolher o MESMO arquivo de novo (depois
    // de um erro) nao dispara onChange.
    seletorTroca.current.value = "";
    seletorTroca.current.click();
  }

  async function trocarImagem(evento) {
    const arquivo = evento.target.files?.[0];
    if (!arquivo || !trocandoDe) return;

    definirErro("");
    definirCorrigindo(true);
    try {
      const atualizado = await trocarImagemDoCartao(trocandoDe.id, arquivo);
      notificar(`Imagem do cartão de ${trocandoDe.crianca_nome} trocada.`);
      // Se a janela deste cartao estiver aberta, ela acompanha.
      definirVendo((atual) => (atual && atual.id === atualizado.id ? atualizado : atual));
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCorrigindo(false);
      definirTrocandoDe(null);
    }
  }

  async function apagar() {
    definirErro("");
    definirCorrigindo(true);
    try {
      await apagarCartao(apagandoDe.id);
      notificar(`Cartão de ${apagandoDe.crianca_nome} apagado.`);
      definirVendo((atual) => (atual && atual.id === apagandoDe.id ? null : atual));
      definirApagandoDe(null);
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCorrigindo(false);
    }
  }

  /* Os motivos das recusas, agrupados e contados. O mesmo motivo repetido
     cinquenta vezes nao e cinquenta informacoes — e uma, com um numero. */
  const motivosDaRecusa = (() => {
    if (!previa) return [];
    const conta = new Map();
    for (const a of previa.arquivos) {
      for (const erro of a.erros) conta.set(erro, (conta.get(erro) ?? 0) + 1);
    }
    return [...conta].sort((x, y) => y[1] - x[1]);
  })();

  /** As correcoes de um cartao, atras dos tres pontinhos. Uma funcao so para as
   *  duas visoes: lista e mural oferecem exatamente o mesmo. */
  function acoesDoCartao(c) {
    return [
      { rotulo: "Substituir imagem", aoEscolher: () => pedirTroca(c) },
      { rotulo: "Apagar imagem", perigo: true, aoEscolher: () => definirApagandoDe(c) },
    ];
  }

  function trocarVisao(nova) {
    definirVisao(nova);
    try {
      localStorage.setItem("nl_cartoes_visao", nova);
    } catch {
      // Nao poder lembrar a preferencia nao e motivo para nao atender agora.
    }
  }

  const buscar = useCallback(async () => {
    if (!edicaoAtiva) return;
    try {
      if (!pasta) {
        definirPastas(await listarPastas(edicaoAtiva));
      } else {
        definirCartoes(
          await listarCartoes({
            tipo: abaTipo,
            edicao_id: edicaoAtiva,
            instituicao_id: pasta.instituicao_id,
          }),
        );
      }
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [abaTipo, edicaoAtiva, pasta]);

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer: a
    // lista so chega depois do await, e nao daria para derivar no render.
    // eslint-disable-next-line react/set-state-in-effect
    if (edicaoAtiva) buscar();
  }, [edicaoAtiva, buscar]);

  // Trocar de edicao na lateral devolve a tela para as pastas: a instituicao
  // aberta era da edicao anterior. Ajustado no render, e nao por efeito, para
  // nao gastar uma busca que ja nasce errada.
  const [ultimaEdicao, definirUltimaEdicao] = useState(edicaoAtiva);
  if (edicaoAtiva !== ultimaEdicao) {
    definirUltimaEdicao(edicaoAtiva);
    definirPasta(null);
  }

  /* Trocar de pasta joga fora a conferencia em curso. A previa e de uma pilha
     de UMA escola — levada para outra pasta, ela ofereceria gravar cartoes que
     nao sao de la, e o rotulo da tela diria a escola errada. */
  function limparEnvio() {
    definirPrevia(null);
    definirArquivos([]);
    definirConferidos([]);
    definirConferindo(false);
    definirSubindoAberto(false);
  }

  /* Fechar a janela no meio da conferencia descarta a previa. Nada se perde de
     verdade: nada foi gravado, e os arquivos continuam no computador de quem
     subiu. Enquanto grava, nao fecha — um Esc sem querer nao pode interromper
     o que ja esta indo para a base. */
  function fecharEnvio() {
    if (!salvando && !subindo) limparEnvio();
  }

  function abrirPasta(p) {
    limparEnvio();
    definirAbaTipo("");
    definirCarregando(true);
    definirPasta(p);
  }

  /* Trocar de aba leva o tipo do envio junto: quem esta com a pilha de festa
     aberta vai subir festa, e ter de dizer isso num select ao lado seria
     repetir o que a aba ja diz — e o lugar exato onde se erra. Na aba "Todos"
     o select continua mandando, porque ali nao ha tipo escolhido. */
  function trocarAba(tipoDaAba) {
    definirCarregando(true);
    definirAbaTipo(tipoDaAba);
    if (tipoDaAba) definirTipo(tipoDaAba);
  }

  function voltarAsPastas() {
    limparEnvio();
    definirCarregando(true);
    definirPasta(null);
  }

  async function enviarLote(evento) {
    evento.preventDefault();
    definirErro("");
    definirSubindo(true);
    try {
      definirPrevia(
        await subirLoteDeCartoes({
          arquivos,
          tipo,
          edicaoId: edicaoAtiva,
          instituicaoId: pasta?.instituicao_id,
        }),
      );
      definirConferidos([]);
      // A conferencia e o passo seguinte do fluxo, nao um extra: quem subiu a
      // pilha subiu para olhar cartao por cartao.
      definirConferindo(true);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSubindo(false);
    }
  }

  async function gravarLote() {
    definirErro("");
    definirSalvando(true);
    try {
      const r = await confirmarLote(previa.id);
      notificar(
        `${r.gravados} cartão(ões) de ${previa.tipo} guardado(s).` +
          (r.ignorados ? ` ${r.ignorados} ignorado(s).` : ""),
      );
      limparEnvio();
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }




  // So as fotos que vao subir precisam de olho: as que ja estao com erro nao
  // vao ser gravadas de qualquer jeito.
  const faltamConferir = previa
    ? previa.arquivos.filter((a) => a.valida && !conferidos.includes(a.indice)).length
    : 0;

  return (
    <div>
      <div className="pagina__eyebrow">Monitoria</div>
      <h1 className="pagina__titulo">Cartões</h1>
      <Rabisco className="pagina__onda" />
      <p className="pagina__lede">
        {pasta
          ? "Os cartões desta instituição. Suba aqui a pilha digitalizada dela — o nome de cada arquivo tem de ser o código da criança."
          : "Uma pasta por instituição. Abra a da escola em que você está trabalhando para ver os cartões dela e subir a pilha digitalizada."}
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {/* A volta em CIMA, sozinha, e o nome da escola embaixo dela.
          Lado a lado, o botao empurrava o nome para a direita e ele deixava de
          comecar onde comeca todo titulo da pagina — parecia deslocado porque
          estava. Aqui a volta e um caminho (de onde vim), e o nome e um titulo
          (onde estou): coisas diferentes, linhas diferentes. */}
      {pasta && (
        <div className="pasta-aberta">
          <button type="button" className="pasta-aberta__voltar" onClick={voltarAsPastas}>
            ← Todas as instituições
          </button>
          <h2 className="pasta-aberta__nome">
            {pasta.sigla && <span className="etiqueta etiqueta--neutra">{pasta.sigla}</span>}
            {pasta.instituicao}
          </h2>
        </div>
      )}

      {/* As duas pilhas da escola. A contagem e o TAMANHO de cada pilha, e nao
          quanto falta enviar dela: acompanhar envio e assunto de outra hora, e
          aqui a pergunta e quantos cartoes ha de cada tipo. */}
      {/* Abas e acoes na MESMA linha: as abas a esquerda, o filtro e o subir na
          ponta direita. Empilhadas, as duas custavam duas faixas de altura
          antes de a lista comecar — e a lista e o que se vem ver aqui. */}
      {pasta && (
        <div className="linha-abas">
          <FaixaDeAbas reiniciarEm={pasta.instituicao_id}>
          <button
            type="button"
            role="tab"
            aria-selected={abaTipo === ""}
            className={`aba ${abaTipo === "" ? "aba--ativa" : ""}`}
            onClick={() => trocarAba("")}
          >
            <span>Todos</span>
            <span className="aba__contagem">{pasta.cesta + pasta.festa} cartões</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={abaTipo === "cesta"}
            className={`aba ${abaTipo === "cesta" ? "aba--ativa" : ""}`}
            onClick={() => trocarAba("cesta")}
          >
            <span>
              <span className="aba__ponto tipo--cesta" />
              Cesta
            </span>
            <span className="aba__contagem">{pasta.cesta} cartões</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={abaTipo === "festa"}
            className={`aba ${abaTipo === "festa" ? "aba--ativa" : ""}`}
            onClick={() => trocarAba("festa")}
          >
            <span>
              <span className="aba__ponto tipo--festa" />
              Festa
            </span>
            <span className="aba__contagem">{pasta.festa} cartões</span>
          </button>
          </FaixaDeAbas>

          <div className="linha-abas__acoes">
            {/* Dois botoes encostados, um so alvo visual: e uma escolha entre
                dois jeitos de ver a mesma coisa, nao duas acoes soltas. */}
            <div className="troca-visao" role="group" aria-label="Como ver os cartões">
              {/* So o icone, mas com `title` e `aria-label`: o desenho conta
                  para quem ja sabe, e o nome continua existindo para o leitor
                  de tela e para quem parar o ponteiro em cima. */}
              <button
                type="button"
                className={`troca-visao__opcao ${visao === "lista" ? "troca-visao__opcao--ativa" : ""}`}
                aria-pressed={visao === "lista"}
                aria-label="Ver como lista"
                title="Ver como lista"
                onClick={() => trocarVisao("lista")}
              >
                <ListaIcone t={16} />
              </button>
              <button
                type="button"
                className={`troca-visao__opcao ${visao === "arquivo" ? "troca-visao__opcao--ativa" : ""}`}
                aria-pressed={visao === "arquivo"}
                aria-label="Ver como arquivo"
                title="Ver como arquivo"
                onClick={() => trocarVisao("arquivo")}
              >
                <ArquivoIcone t={16} />
              </button>
            </div>

            {pode("subir_cartoes") && (
              <Button size="sm" onClick={() => definirSubindoAberto(true)}>
                Subir cartões
              </Button>
            )}
          </div>
        </div>
      )}

      {/* O envio mora DENTRO da pasta: sobe-se a pilha de uma escola, e o
          servidor recusa na previa o arquivo cujo codigo for de outra. No andar
          das pastas nao ha o que subir — nao se sabe de quem seria. */}
      {pasta && pode("subir_cartoes") && subindoAberto && (
        <Modal
          rotulo={`${pasta.instituicao}${abaTipo ? ` · ${abaTipo}` : ""}`}
          titulo={previa ? "Conferência" : "Subir cartões digitalizados"}
          /* Os dois passos pedem molduras diferentes. O formulario tem tres
             campos fixos e cabe no tamanho padrao — em `grande` ele ficaria com
             meia janela vazia embaixo. A conferencia pode ter cinquenta
             arquivos, e ai vale o `grande`: moldura fixa, corpo rolando, sem a
             janela crescer enquanto a pessoa marca um a um.

             Isto nao e a janela mudando de tamanho com o conteudo, que o
             PADROES_UI proibe: sao dois PASSOS da tarefa, e a troca acontece no
             clique que leva de um para o outro — nao embaixo do ponteiro de
             quem esta agindo dentro de um deles. */
          tamanho={previa ? "grande" : "padrao"}
          aoFechar={fecharEnvio}
        >
          {!previa ? (
            <form onSubmit={enviarLote}>
              {/* Com uma pilha aberta, perguntar de que tipo ela e seria
                  repetir o que a aba ja diz — e seria o lugar exato de errar:
                  escolher "festa" com a aba Cesta na frente subiria a pilha
                  inteira no tipo trocado. Na aba "Todos" nao ha tipo escolhido,
                  e o campo volta. */}
              {abaTipo ? (
                <p className="campo__dica" style={{ marginTop: 0 }}>
                  Vai para a pilha de{" "}
                  <span className={`etiqueta etiqueta--${abaTipo}`}>{abaTipo}</span> desta
                  instituição. Para subir a outra, troque de aba.
                </p>
              ) : (
                <div className="linha-campos">
                  <Selecao
                    rotulo="Estes cartões são de"
                    value={tipo}
                    onChange={(e) => definirTipo(e.target.value)}
                  >
                    <option value="cesta">Cesta</option>
                    <option value="festa">Festa</option>
                  </Selecao>
                </div>
              )}

              <label className="campo">
                <span className="campo__rotulo">Arquivos</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png"
                  multiple
                  onChange={(e) => definirArquivos([...(e.target.files ?? [])])}
                />
                <span className="campo__dica">
                  Nomeie cada arquivo com o código da criança. Separe as pilhas de
                  cesta e de festa antes de subir.
                </span>
              </label>

              <div className="barra-acoes barra-acoes--fim">
                <Button
                  type="submit"
                  carregando={subindo}
                  disabled={arquivos.length === 0 || !edicaoAtiva}
                >
                  {arquivos.length > 0
                    ? `Conferir ${arquivos.length} arquivo(s)`
                    : "Conferir"}
                </Button>
              </div>
            </form>
          ) : (
            <div>
              <p className="campo__dica" style={{ marginTop: 0 }}>
                <strong>
                  {previa.validas} de {previa.total} prontos.
                </strong>{" "}
                Nada foi gravado ainda.
                {faltamConferir > 0
                  ? ` Falta olhar ${faltamConferir} cartão(ões) um a um.`
                  : " Todos já foram conferidos um a um."}
              </p>

              {/* O QUE deu errado, em cima e agrupado. Antes o motivo ficava so
                  na linha de cada arquivo, em letra de dica: numa pilha de
                  cinquenta, quem subia via "42 de 50" e nao descobria por que
                  oito ficaram de fora sem caçar linha por linha. */}
              {motivosDaRecusa.length > 0 && (
                <Mensagem tipo="aviso">
                  <strong>
                    {previa.total - previa.validas} de {previa.total} não vão subir:
                  </strong>
                  <ul className="recusa">
                    {motivosDaRecusa.map(([motivo, quantos]) => (
                      <li key={motivo}>
                        {quantos > 1 && <strong>{quantos}× </strong>}
                        {motivo}
                      </li>
                    ))}
                  </ul>
                </Mensagem>
              )}

              <div className="ficha__lista">
                {previa.arquivos.map((a) => (
                  <div key={a.indice} className="ficha__linha">
                    {a.miniatura ? (
                      <img
                        src={`data:image/jpeg;base64,${a.miniatura}`}
                        alt=""
                        style={{
                          width: 44,
                          height: 44,
                          objectFit: "cover",
                          borderRadius: "var(--radius-sm)",
                          border: "var(--stroke-hairline) solid var(--border-default)",
                          flex: "none",
                        }}
                      />
                    ) : (
                      <span style={{ width: 44, flex: "none" }} />
                    )}

                    <div className="ficha__linha-corpo">
                      <span className="ficha__linha-etiquetas">
                        {a.valida ? (
                          <span className="etiqueta etiqueta--ok">
                            {conferidos.includes(a.indice) ? "conferido" : "pronto"}
                          </span>
                        ) : (
                          <span className="etiqueta etiqueta--parado">não vai subir</span>
                        )}
                        {a.avisos.map((aviso) => (
                          <span key={aviso} className="etiqueta etiqueta--espera" title={aviso}>
                            conferir
                          </span>
                        ))}
                      </span>

                      <span className="ficha__linha-nome" title={a.arquivo}>
                        {a.crianca_nome ? (
                          <>
                            <span className="ficha__linha-codigo">{a.codigo}</span>
                            {a.crianca_nome}
                          </>
                        ) : (
                          <span className="celula--vazia">{a.arquivo}</span>
                        )}
                      </span>

                      {/* O motivo da recusa NAO e uma dica: e a unica coisa
                          que importa naquela linha. Em cinza de dica ele tinha
                          o mesmo peso do nome do arquivo ao lado. */}
                      {a.erros.length > 0 ? (
                        <span className="linha-recusa">{a.erros.join(" ")}</span>
                      ) : (
                        a.crianca_nome && (
                          <span className="campo__dica" style={{ marginTop: 2, display: "block" }}>
                            {a.arquivo} · {a.instituicao}
                          </span>
                        )
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="barra-acoes barra-acoes--fim" style={{ marginTop: "var(--space-4)" }}>
                <Button
                  onClick={gravarLote}
                  carregando={salvando}
                  disabled={previa.validas === 0 || faltamConferir > 0}
                >
                  Guardar {previa.validas} cartão(ões)
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => definirConferindo(true)}
                  disabled={salvando}
                >
                  {faltamConferir > 0 ? "Conferir um a um" : "Rever um a um"}
                </Button>
                <Button variant="ghost" onClick={limparEnvio} disabled={salvando}>
                  Descartar
                </Button>
              </div>
            </div>
          )}
        </Modal>
      )}

      {carregando ? (
        <Carregando tela>
          {pasta ? "Carregando cartões..." : "Carregando as instituições..."}
        </Carregando>
      ) : !pasta ? (
        pastas.length === 0 ? (
          <EmptyState
            titulo="Nenhuma instituição nesta edição"
            corpo="As pastas aparecem quando houver instituição com crianças cadastradas."
          />
        ) : (
          <div className="pastas">
            {pastas.map((p) => (
              <button
                key={p.instituicao_id}
                type="button"
                className="pasta"
                onClick={() => abrirPasta(p)}
              >
                <span className="pasta__aba" aria-hidden="true" />
                <span className="pasta__corpo">
                  <span className="pasta__nome">
                    {p.sigla && <span className="etiqueta etiqueta--neutra">{p.sigla}</span>}
                    {p.instituicao}
                  </span>

                  {/* Duas barras: quantos cartoes de cada tipo ja chegaram
                      sobre quantos deveriam chegar. O total e o numero de
                      CRIANCAS da escola — cada uma escreve um de cada tipo.
                      Barra em vez de so o numero porque a pergunta aqui e
                      "qual escola esta atrasada", e isso se ve de longe num
                      comprimento; um numero exige ler e dividir.

                      E o mesmo `Progresso` do painel, com as mesmas cores: duas
                      telas medindo a mesma coisa nao deviam desenha-la de
                      jeitos diferentes. */}
                  <span className="pasta__barras">
                    <Progresso rotulo="Cesta" valor={p.cesta} de={p.criancas} tom="cesta" />
                    <Progresso rotulo="Festa" valor={p.festa} de={p.criancas} tom="festa" />
                  </span>
                </span>
              </button>
            ))}
          </div>
        )
      ) : cartoes.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhum cartão nesta instituição"
          corpo="Suba aqui a pilha digitalizada desta escola — o nome de cada arquivo tem de ser o código da criança."
        />
      ) : (
        visao === "arquivo" ? (
          /* A visao de arquivo: o cartao como coisa, e nao como linha. E o que
             serve a quem esta com a pilha de papel na mao e quer achar ESTE
             aqui — pelo desenho, antes do nome. */
          <div className="mural">
            {cartoes.itens.map((c) => (
              <div key={c.id} className="mural__item">
                {/* Os pontinhos ficam FORA do botao que abre: botao dentro de
                    botao e HTML invalido, e o clique de um viraria o clique do
                    outro. */}
                {pode("subir_cartoes") && (
                  <span className="mural__acoes">
                    <MenuAcoes titulo={`Ações do cartão de ${c.crianca_nome}`}
                      itens={acoesDoCartao(c)} />
                  </span>
                )}
                <button
                  type="button"
                  className="mural__abrir"
                  onClick={() => definirVendo(c)}
                  title={`Ver o cartão de ${c.crianca_nome}`}
                >
                <span className="mural__imagem">
                  <img
                    src={urlDaMiniatura(c.id)}
                    alt={`Cartão de ${c.tipo} de ${c.crianca_nome}`}
                    /* `lazy`: numa escola de sessenta, so baixa o que esta na
                       tela. Sem isto a grade puxaria tudo de uma vez. */
                    loading="lazy"
                  />
                  <span className={`etiqueta etiqueta--${c.tipo} mural__tipo`}>{c.tipo}</span>
                </span>
                <span className="mural__codigo">{c.crianca_codigo}</span>
                <span className="mural__nome">{c.crianca_nome}</span>
                </button>
              </div>
            ))}
          </div>
        ) : (
        /* A lista tambem e de cartoes, so que deitados: uma linha de tabela
           nao parece clicavel, e a pessoa ficava procurando o botao. Com a
           miniatura na frente e a moldura em volta, o alvo e a peca inteira —
           e o "Ver imagem" deixa de precisar existir. */
        <div className="cartoes-lista">
          {cartoes.itens.map((c) => (
            <div key={c.id} className="cartoes-lista__item">
              <button
                type="button"
                className="cartoes-lista__abrir"
                onClick={() => definirVendo(c)}
                title={`Ver o cartão de ${c.crianca_nome}`}
              >
                <span className="cartoes-lista__mini">
                  <img
                    src={urlDaMiniatura(c.id)}
                    alt={`Cartão de ${c.tipo} de ${c.crianca_nome}`}
                    loading="lazy"
                  />
                </span>
                <span className="cartoes-lista__texto">
                  <span className="cartoes-lista__codigo">{c.crianca_codigo}</span>
                  <span className="cartoes-lista__nome">{c.crianca_nome}</span>
                </span>
                <span className={`etiqueta etiqueta--${c.tipo}`}>{c.tipo}</span>
              </button>

              {pode("subir_cartoes") && (
                <span className="cartoes-lista__acoes">
                  <MenuAcoes
                    titulo={`Ações do cartão de ${c.crianca_nome}`}
                    itens={acoesDoCartao(c)}
                  />
                </span>
              )}
            </div>
          ))}
        </div>
        )
      )}

      {/* Um seletor so para a tela inteira: quem diz DE QUAL cartao e a troca e
          o `trocandoDe`, guardado antes de abrir. */}
      <input
        ref={seletorTroca}
        type="file"
        accept="image/jpeg,image/png"
        hidden
        onChange={trocarImagem}
      />

      {apagandoDe && (
        <Modal
          rotulo="Apagar cartão de:"
          titulo={apagandoDe.crianca_nome}
          aoFechar={() => !corrigindo && definirApagandoDe(null)}
        >
          <p className="campo__dica" style={{ marginTop: 0 }}>
            A imagem sai do disco e o registro deste cartão de{" "}
            <strong>{apagandoDe.tipo}</strong> some. Não dá para desfazer — se a
            foto só saiu ruim, use <strong>Substituir imagem</strong>.
          </p>
          <div className="barra-acoes barra-acoes--fim">
            <Button variant="secondary" onClick={apagar} carregando={corrigindo}>
              Apagar
            </Button>
            <Button variant="ghost" onClick={() => definirApagandoDe(null)} disabled={corrigindo}>
              Cancelar
            </Button>
          </div>
        </Modal>
      )}

      {conferindo && previa && (
        <ConferirCartoes
          previa={previa}
          conferidos={conferidos}
          aoConferir={(indice) =>
            definirConferidos((atual) =>
              atual.includes(indice) ? atual : [...atual, indice],
            )
          }
          aoFechar={() => definirConferindo(false)}
          aoGuardar={() => {
            // Fecha antes de gravar: se der erro, a mensagem e o botao de
            // tentar de novo estao no painel, atras da janela.
            definirConferindo(false);
            gravarLote();
          }}
        />
      )}

      {/* A imagem so sai por rota autenticada. Num <img> de mesma origem o
          cookie da sessao vai junto, entao nao precisa de aba nova nem de
          baixar o blob antes. */}
      {vendo && (
        <Modal
          rotulo={`Cartão de ${vendo.tipo}`}
          titulo={vendo.crianca_nome}
          tamanho="largo"
          aoFechar={() => definirVendo(null)}
        >
          <img
            className="cartao-imagem"
            src={urlDaImagem(vendo.id)}
            alt={`Cartão de ${vendo.tipo} de ${vendo.crianca_nome}`}
          />
          {/* Esta tela e controle de CARTAO: quantos ha, de que tipo, quais ja
              sairam. Quem e o padrinho de cada crianca e assunto da tela de
              padrinhos — aqui a pergunta e sobre a pilha de papel. */}
          <dl className="ficha ficha--duas" style={{ marginTop: "var(--space-4)" }}>
            <dt>Instituição</dt>
            <dd>{vendo.instituicao}</dd>
            <dt>Tipo</dt>
            <dd>
              <span className={`etiqueta etiqueta--${vendo.tipo}`}>{vendo.tipo}</span>
            </dd>
            <dt>Situação</dt>
            <dd>
              {vendo.status === "enviado" ? "Enviado" : "A enviar"}
              {vendo.enviado_em && ` · ${formatarDataHora(vendo.enviado_em)}`}
            </dd>
            <dt>Digitalizado</dt>
            <dd>{formatarDataHora(vendo.criado_em)}</dd>
          </dl>
        </Modal>
      )}
    </div>
  );
}
