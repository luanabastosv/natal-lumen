import { useCallback, useEffect, useRef, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import ConferirCartoes from "../components/dados/ConferirCartoes.jsx";
import { PERGUNTAS, RESPOSTAS_PADRAO } from "../components/dados/autorizacao.js";
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
  listarAutorizacoes,
  listarCartoes,
  listarPastas,
  subirLoteDeCartoes,
  urlDaImagem,
  urlDaImagemDaAutorizacao,
  urlDaMiniatura,
  urlDaMiniaturaDaAutorizacao,
  apagarAutorizacao,
  apagarCartao,
  trocarImagemDaAutorizacao,
  trocarImagemDoCartao,
} from "../services/cartoes.js";
import { formatarDataHora } from "../utils/dinheiro.js";

const AUTORIZACAO = "autorizacao";

/** O tipo como se escreve na tela. O servidor manda sem acento. */
const NOME_DO_TIPO = { cesta: "cesta", festa: "festa", autorizacao: "autorização" };

/* A autorizacao mora em rota propria no servidor, mas na tela ela e mais uma
   pilha de papel da pasta: estas tres funcoes escolhem a porta pelo tipo, e o
   resto da tela trata as duas coisas igual. */
const ehAutorizacao = (item) => item.tipo === AUTORIZACAO;
const imagemDe = (item) =>
  ehAutorizacao(item) ? urlDaImagemDaAutorizacao(item.id) : urlDaImagem(item.id);
const miniaturaDe = (item) =>
  ehAutorizacao(item) ? urlDaMiniaturaDaAutorizacao(item.id) : urlDaMiniatura(item.id);

/** "o cartão de Ana" / "a autorização de Ana", para as mensagens. */
const doItem = (item) =>
  `${ehAutorizacao(item) ? "a autorização" : "o cartão"} de ${item.crianca_nome}`;

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
  // So na pilha de autorizacoes: o que o monitor marcou em cada foto, pelo
  // indice no lote. Vive aqui, e nao na janela da conferencia, para fechar e
  // reabrir a conferencia sem perder o que ja foi respondido.
  const [respostas, definirRespostas] = useState({});
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
  // Dentro da pasta, qual pilha esta na mao. Cesta, festa e autorizacao sao
  // tres pilhas separadas no mundo real — recolhidas e conferidas uma de cada
  // vez. Nao ha mais aba "Todos": a autorizacao nao e cartao, e misturar as
  // tres numa grade so faria a pessoa separar de novo com os olhos.
  const [abaTipo, definirAbaTipo] = useState("cesta");
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
      const atualizado = ehAutorizacao(trocandoDe)
        ? { ...(await trocarImagemDaAutorizacao(trocandoDe.id, arquivo)), tipo: AUTORIZACAO }
        : await trocarImagemDoCartao(trocandoDe.id, arquivo);
      notificar(`Imagem d${doItem(trocandoDe)} trocada.`);
      // Se a janela deste cartao estiver aberta, ela acompanha.
      definirVendo((atual) =>
        atual && atual.id === atualizado.id && atual.tipo === atualizado.tipo ? atualizado : atual,
      );
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
      if (ehAutorizacao(apagandoDe)) await apagarAutorizacao(apagandoDe.id);
      else await apagarCartao(apagandoDe.id);
      notificar(
        `${ehAutorizacao(apagandoDe) ? "Autorização" : "Cartão"} de ${apagandoDe.crianca_nome} ${
          ehAutorizacao(apagandoDe) ? "apagada" : "apagado"
        }.`,
      );
      definirVendo((atual) =>
        atual && atual.id === apagandoDe.id && atual.tipo === apagandoDe.tipo ? null : atual,
      );
      definirApagandoDe(null);
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCorrigindo(false);
    }
  }

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
      } else if (abaTipo === AUTORIZACAO) {
        const autorizacoes = await listarAutorizacoes({
          edicao_id: edicaoAtiva,
          instituicao_id: pasta.instituicao_id,
        });
        definirCartoes({
          itens: autorizacoes.map((a) => ({ ...a, tipo: AUTORIZACAO })),
          total: autorizacoes.length,
        });
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
    definirRespostas({});
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
    definirAbaTipo("cesta");
    definirTipo("cesta");
    definirCarregando(true);
    definirPasta(p);
  }

  /* Trocar de aba leva o tipo do envio junto: quem esta com a pilha de festa
     aberta vai subir festa, e ter de dizer isso num select ao lado seria
     repetir o que a aba ja diz — e o lugar exato onde se erra. */
  function trocarAba(tipoDaAba) {
    definirCarregando(true);
    definirAbaTipo(tipoDaAba);
    definirTipo(tipoDaAba);
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
      definirRespostas({});
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
      // Foto que ninguem mexeu vai com o padrao (tudo "Nao"): o padrao e uma
      // resposta, e o servidor pede resposta para cada uma.
      const r = await confirmarLote(
        previa.id,
        previa.tipo === AUTORIZACAO
          ? Object.fromEntries(
              previa.arquivos
                .filter((a) => a.valida)
                .map((a) => [a.indice, respostas[a.indice] ?? RESPOSTAS_PADRAO]),
            )
          : undefined,
      );
      notificar(
        (previa.tipo === AUTORIZACAO
          ? `${r.gravados} autorização(ões) guardada(s).`
          : `${r.gravados} cartão(ões) de ${previa.tipo} guardado(s).`) +
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




  return (
    <div>
      <div className="pagina__eyebrow">Monitoria</div>
      <h1 className="pagina__titulo">Cartões e Autorização</h1>
      <Rabisco className="pagina__onda" />
      <p className="pagina__lede">
        {pasta
          ? "Suba as pilhas desta instituição. Cada arquivo leva o código da criança no nome."
          : "Uma pasta por instituição. Abra a sua para ver e subir cartões e autorizações."}
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
            aria-selected={abaTipo === "cesta"}
            className={`aba ${abaTipo === "cesta" ? "aba--ativa" : ""}`}
            onClick={() => trocarAba("cesta")}
          >
            <span>
              <span className="aba__ponto tipo--cesta" />
              Cartão Cesta
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
              Cartão Festa
            </span>
            <span className="aba__contagem">{pasta.festa} cartões</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={abaTipo === AUTORIZACAO}
            className={`aba ${abaTipo === AUTORIZACAO ? "aba--ativa" : ""}`}
            onClick={() => trocarAba(AUTORIZACAO)}
          >
            <span>
              <span className="aba__ponto tipo--autorizacao" />
              Autorização
            </span>
            <span className="aba__contagem">
              {pasta.autorizacoes} {pasta.autorizacoes === 1 ? "autorização" : "autorizações"}
            </span>
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
                {abaTipo === AUTORIZACAO ? "Subir autorizações" : "Subir cartões"}
              </Button>
            )}
          </div>
        </div>
      )}

      {/* O envio mora DENTRO da pasta: sobe-se a pilha de uma escola, e o
          servidor recusa na previa o arquivo cujo codigo for de outra. No andar
          das pastas nao ha o que subir — nao se sabe de quem seria. */}
      {/* Depois de ler os arquivos esta janela da lugar a conferencia, e nao
          fica aberta atras dela: duas janelas de conferencia empilhadas
          diziam a mesma coisa duas vezes. */}
      {pasta && pode("subir_cartoes") && subindoAberto && !previa && (
        <Modal
          rotulo={`${pasta.instituicao} · ${NOME_DO_TIPO[abaTipo]}`}
          titulo={
            abaTipo === AUTORIZACAO
              ? "Subir autorizações digitalizadas"
              : "Subir cartões digitalizados"
          }
          aoFechar={fecharEnvio}
        >
          <form onSubmit={enviarLote}>
              {/* Perguntar de que tipo e a pilha seria repetir o que a aba ja
                  diz — e seria o lugar exato de errar: escolher "festa" com a
                  aba Cesta na frente subiria a pilha inteira no tipo trocado. */}
              <p className="campo__dica" style={{ marginTop: 0 }}>
                Vai para a pilha de{" "}
                <span className={`etiqueta etiqueta--${abaTipo}`}>{NOME_DO_TIPO[abaTipo]}</span>{" "}
                desta instituição. Para subir outra, troque de aba.
              </p>

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
                  cesta, festa e autorização antes de subir.
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
        </Modal>
      )}

      {carregando ? (
        <Carregando tela>
          {pasta
            ? abaTipo === AUTORIZACAO
              ? "Carregando autorizações..."
              : "Carregando cartões..."
            : "Carregando as instituições..."}
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
                    <Progresso rotulo="Cartão Cesta" valor={p.cesta} de={p.criancas} tom="cesta" />
                    <Progresso rotulo="Cartão Festa" valor={p.festa} de={p.criancas} tom="festa" />
                    <Progresso
                      rotulo="Autorização"
                      valor={p.autorizacoes}
                      de={p.criancas}
                      tom="autorizacao"
                    />
                  </span>
                </span>
              </button>
            ))}
          </div>
        )
      ) : cartoes.itens.length === 0 ? (
        <EmptyState
          titulo={
            abaTipo === AUTORIZACAO
              ? "Nenhuma autorização nesta instituição"
              : `Nenhum cartão de ${abaTipo} nesta instituição`
          }
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
                    <MenuAcoes titulo={`Ações d${doItem(c)}`}
                      itens={acoesDoCartao(c)} />
                  </span>
                )}
                <button
                  type="button"
                  className="mural__abrir"
                  onClick={() => definirVendo(c)}
                  title={`Ver ${doItem(c)}`}
                >
                <span className="mural__imagem">
                  <img
                    src={miniaturaDe(c)}
                    alt={`${NOME_DO_TIPO[c.tipo]} de ${c.crianca_nome}`}
                    /* `lazy`: numa escola de sessenta, so baixa o que esta na
                       tela. Sem isto a grade puxaria tudo de uma vez. */
                    loading="lazy"
                  />
                  <span className={`etiqueta etiqueta--${c.tipo} mural__tipo`}>
                    {NOME_DO_TIPO[c.tipo]}
                  </span>
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
                title={`Ver ${doItem(c)}`}
              >
                <span className="cartoes-lista__mini">
                  <img
                    src={miniaturaDe(c)}
                    alt={`${NOME_DO_TIPO[c.tipo]} de ${c.crianca_nome}`}
                    loading="lazy"
                  />
                </span>
                <span className="cartoes-lista__texto">
                  <span className="cartoes-lista__codigo">{c.crianca_codigo}</span>
                  <span className="cartoes-lista__nome">{c.crianca_nome}</span>
                </span>
                <span className={`etiqueta etiqueta--${c.tipo}`}>{NOME_DO_TIPO[c.tipo]}</span>
              </button>

              {pode("subir_cartoes") && (
                <span className="cartoes-lista__acoes">
                  <MenuAcoes
                    titulo={`Ações d${doItem(c)}`}
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
          rotulo={ehAutorizacao(apagandoDe) ? "Apagar autorização de:" : "Apagar cartão de:"}
          titulo={apagandoDe.crianca_nome}
          aoFechar={() => !corrigindo && definirApagandoDe(null)}
        >
          <p className="campo__dica" style={{ marginTop: 0 }}>
            A imagem sai do disco e o registro{" "}
            {ehAutorizacao(apagandoDe) ? (
              "desta autorização"
            ) : (
              <>
                deste cartão de <strong>{apagandoDe.tipo}</strong>
              </>
            )}{" "}
            some. Não dá para desfazer — se a
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

      {previa && (
        <ConferirCartoes
          previa={previa}
          salvando={salvando}
          erro={erro}
          conferidos={conferidos}
          respostas={respostas}
          aoResponder={(indice, r) => definirRespostas((atual) => ({ ...atual, [indice]: r }))}
          aoConferir={(indice) =>
            definirConferidos((atual) =>
              atual.includes(indice) ? atual : [...atual, indice],
            )
          }
          /* Fechar a conferencia descarta o lote: nada foi gravado, e os
             arquivos continuam no computador de quem subiu. */
          aoFechar={fecharEnvio}
          aoGuardar={gravarLote}
        />
      )}

      {/* A imagem so sai por rota autenticada. Num <img> de mesma origem o
          cookie da sessao vai junto, entao nao precisa de aba nova nem de
          baixar o blob antes. */}
      {vendo && (
        <Modal
          rotulo={ehAutorizacao(vendo) ? "Autorização de" : `Cartão de ${vendo.tipo}`}
          titulo={vendo.crianca_nome}
          tamanho="largo"
          aoFechar={() => definirVendo(null)}
        >
          <img
            className="cartao-imagem"
            src={imagemDe(vendo)}
            alt={`${NOME_DO_TIPO[vendo.tipo]} de ${vendo.crianca_nome}`}
          />
          {/* Esta tela e controle de PAPEL: quantos ha, de que tipo, quais ja
              sairam. Quem e o padrinho de cada crianca e assunto da tela de
              padrinhos — aqui a pergunta e sobre a pilha. */}
          {ehAutorizacao(vendo) ? (
            /* Os campos proprios da autorizacao ainda vao chegar. Por ora ela
               mostra o que ja se sabe dela. */
            <dl className="ficha ficha--duas" style={{ marginTop: "var(--space-4)" }}>
              <dt>Instituição</dt>
              <dd>{vendo.instituicao}</dd>
              <dt>Código</dt>
              <dd>{vendo.crianca_codigo}</dd>
              <dt>Digitalizada</dt>
              <dd>{formatarDataHora(vendo.criado_em)}</dd>
              {/* As respostas que o monitor marcou ao conferir. Nulas so nas
                  que subiram antes de o formulario existir. */}
              {PERGUNTAS.map((p) => (
                <div key={p.sim} style={{ display: "contents" }}>
                  <dt className="ficha__dt-largo">{p.pergunta}</dt>
                  <dd className="ficha__dd-largo">
                    {vendo[p.sim] === true
                      ? `Sim · ${vendo[p.qual]}`
                      : vendo[p.sim] === false
                        ? "Não"
                        : "não respondido"}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
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
          )}
        </Modal>
      )}
    </div>
  );
}
