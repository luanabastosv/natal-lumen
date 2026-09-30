import { useCallback, useEffect, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import ConferirCartoes from "../components/dados/ConferirCartoes.jsx";
import { Selecao } from "../components/core/Campo.jsx";
import FaixaDeAbas from "../components/core/FaixaDeAbas.jsx";
import BotaoIcone from "../components/core/BotaoIcone.jsx";
import { Olho } from "../components/core/icones.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";
import {
  confirmarLote,
  listarCartoes,
  listarPastas,
  marcarEnviados,
  subirLoteDeCartoes,
  urlDaImagem,
} from "../services/cartoes.js";
import { formatarDataHora } from "../utils/dinheiro.js";

export default function Cartoes() {
  // A edicao vem da lateral: e a mesma para o sistema inteiro.
  const { pode, edicaoAtiva } = useSessao();

  const [cartoes, definirCartoes] = useState({ itens: [], total: 0 });
  const [situacao, definirSituacao] = useState("");

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

  const [marcados, definirMarcados] = useState([]);

  // Qual cartao esta aberto para olhar.
  const [vendo, definirVendo] = useState(null);

  // No celular ficam de pe de quem e o cartao e se ele ja foi — o resto ja
  // morava na janela do cartao aberto, que agora e tambem a janela dos
  // detalhes da linha.
  const estreita = useTelaEstreita();

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

  const buscar = useCallback(async () => {
    if (!edicaoAtiva) return;
    try {
      if (!pasta) {
        definirPastas(await listarPastas(edicaoAtiva));
      } else {
        definirCartoes(
          await listarCartoes({
            situacao,
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
  }, [situacao, abaTipo, edicaoAtiva, pasta]);

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
    definirMarcados([]);
  }

  /* Trocar de pasta joga fora a conferencia em curso. A previa e de uma pilha
     de UMA escola — levada para outra pasta, ela ofereceria gravar cartoes que
     nao sao de la, e o rotulo da tela diria a escola errada. */
  function limparEnvio() {
    definirPrevia(null);
    definirArquivos([]);
    definirConferidos([]);
    definirConferindo(false);
  }

  function abrirPasta(p) {
    definirMarcados([]);
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
    definirMarcados([]);
    definirCarregando(true);
    definirAbaTipo(tipoDaAba);
    if (tipoDaAba) definirTipo(tipoDaAba);
  }

  function voltarAsPastas() {
    definirMarcados([]);
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
      limpar();
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  function limpar() {
    definirPrevia(null);
    definirArquivos([]);
    definirConferidos([]);
    definirConferindo(false);
  }


  async function enviar() {
    definirErro("");
    try {
      const enviados = await marcarEnviados(marcados);
      notificar(`${enviados.length} cartão(ões) marcado(s) como enviado(s).`);
      definirMarcados([]);
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  function alternar(id) {
    definirMarcados((atual) =>
      atual.includes(id) ? atual.filter((x) => x !== id) : [...atual, id],
    );
  }

  const podeMarcar = pode("enviar_cartoes");

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

      {/* A volta fica no topo do conteudo, e nao ao lado do titulo: o titulo da
          pagina continua sendo "Cartões", e o nome da escola e onde a pessoa
          esta DENTRO dela. */}
      {pasta && (
        <div className="migalha">
          <Button size="sm" variant="ghost" onClick={voltarAsPastas}>
            ← Todas as instituições
          </Button>
          <span className="migalha__atual">
            {pasta.sigla && <span className="etiqueta etiqueta--neutra">{pasta.sigla}</span>}
            {pasta.instituicao}
          </span>
        </div>
      )}

      {/* As duas pilhas da escola. A contagem em cada aba e o total dela — e o
          numero que diz de que tamanho e o trabalho antes de abrir. */}
      {pasta && (
        <FaixaDeAbas reiniciarEm={pasta.instituicao_id}>
          <button
            type="button"
            role="tab"
            aria-selected={abaTipo === ""}
            className={`aba ${abaTipo === "" ? "aba--ativa" : ""}`}
            onClick={() => trocarAba("")}
          >
            <span>Todos</span>
            <span className="aba__contagem">{pasta.total} cartões</span>
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
            <span className="aba__contagem">{pasta.cesta.a_enviar} a enviar</span>
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
            <span className="aba__contagem">{pasta.festa.a_enviar} a enviar</span>
          </button>
        </FaixaDeAbas>
      )}

      {/* O envio mora DENTRO da pasta: sobe-se a pilha de uma escola, e o
          servidor recusa na previa o arquivo cujo codigo for de outra. No andar
          das pastas nao ha o que subir — nao se sabe de quem seria. */}
      {pasta && pode("subir_cartoes") && (
        <>
          {!previa ? (
            <form className="painel" onSubmit={enviarLote}>
              <h2 className="painel__titulo">Subir cartões digitalizados</h2>
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
            <div className="painel">
              <h2 className="painel__titulo">
                Conferência · {previa.validas} de {previa.total} prontos
              </h2>
              <p className="campo__dica" style={{ marginTop: 0 }}>
                Nada foi gravado ainda. Quem estiver com erro é ignorado — corrija o
                nome do arquivo e suba de novo.
                {faltamConferir > 0
                  ? ` Falta olhar ${faltamConferir} cartão(ões) um a um.`
                  : " Todos já foram conferidos um a um."}
              </p>

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

                      {(a.erros.length > 0 || a.crianca_nome) && (
                        <span className="campo__dica" style={{ marginTop: 2, display: "block" }}>
                          {a.erros.length > 0 ? a.erros.join(" ") : `${a.arquivo} · ${a.instituicao}`}
                        </span>
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
                <Button variant="ghost" onClick={limpar} disabled={salvando}>
                  Descartar
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {pasta && (
        <div className="barra-acoes">
          <Selecao value={situacao} onChange={(e) => definirSituacao(e.target.value)}>
            <option value="">Todos</option>
            <option value="digitalizado">A enviar</option>
            <option value="enviado">Enviados</option>
          </Selecao>
          {podeMarcar && marcados.length > 0 && (
            <Button variant="secondary" size="sm" onClick={enviar}>
              Marcar {marcados.length} como enviado(s)
            </Button>
          )}
          <span className="campo__dica" style={{ marginTop: 0 }}>
            {cartoes.total} cartão(ões)
          </span>
        </div>
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

                  {/* O numero que se procura primeiro e quanto FALTA sair
                      daqui: a pasta existe para ser esvaziada. */}
                  <span className="pasta__conta">
                    <strong>{p.a_enviar}</strong> a enviar
                    <span className="pasta__de"> de {p.total}</span>
                  </span>

                  {/* As duas pilhas, na mesma cor que o painel ja usa para
                      cesta e festa. E o que a pessoa procura antes de abrir:
                      de que tamanho e cada trabalho. */}
                  <span className="pasta__pilhas">
                    {p.total === 0 ? (
                      <span className="etiqueta etiqueta--espera">nenhum cartão ainda</span>
                    ) : (
                      <>
                        <span className="pasta__pilha">
                          <span className="aba__ponto tipo--cesta" />
                          {p.cesta.total} cesta
                        </span>
                        <span className="pasta__pilha">
                          <span className="aba__ponto tipo--festa" />
                          {p.festa.total} festa
                        </span>
                      </>
                    )}
                  </span>
                </span>
              </button>
            ))}
          </div>
        )
      ) : cartoes.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhum cartão nesta instituição"
          corpo={
            situacao
              ? "Nenhum cartão com esse filtro. Limpe o filtro para ver a pasta inteira."
              : "Suba aqui a pilha digitalizada desta escola — o nome de cada arquivo tem de ser o código da criança."
          }
        />
      ) : (
        <div className="tabela-rolagem">
          {/* Sem `tabela--larga` no celular: e a largura minima dela que fazia
              a lista rolar de lado. */}
          <table className={`tabela ${estreita ? "tabela--compacta" : "tabela--larga"}`}>
            {!estreita && (
              <caption className="tabela-dica">
                Arraste a lista para o lado para ver todas as colunas.
              </caption>
            )}
            <thead>
              <tr>
                {podeMarcar && <th className="tabela__acoes" />}
                <th>Criança</th>
                {/* No celular o tipo desce para debaixo do nome: a pilula
                    inteira numa coluna propria nao cabia em cinco colunas a
                    320px, e abrevia-la apagaria justamente a distincao que ela
                    existe para fazer. A cor e a palavra continuam ali. */}
                {!estreita && <th>Tipo</th>}
                <th className="tabela__acoes" />
              </tr>
            </thead>
            <tbody>
              {cartoes.itens.map((c) => (
                <tr key={c.id}>
                  {podeMarcar && (
                    <td className="tabela__acoes">
                      <input
                        type="checkbox"
                        checked={marcados.includes(c.id)}
                        onChange={() => alternar(c.id)}
                        disabled={c.status === "enviado" || !c.padrinho_id}
                        aria-label={`Marcar cartão de ${c.crianca_nome}`}
                      />
                    </td>
                  )}
                  {/* A instituicao nao se repete na linha: ela e a PASTA em que
                      a pessoa esta, e dize-la cinquenta vezes era dizer o mesmo
                      cinquenta vezes. */}
                  <td>
                    {c.crianca_nome}
                    {estreita && (
                      <>
                        <br />
                        <span className={`etiqueta etiqueta--${c.tipo}`}>{c.tipo}</span>
                      </>
                    )}
                  </td>
                  {!estreita && (
                    <td>
                      <span className={`etiqueta etiqueta--${c.tipo}`}>{c.tipo}</span>
                    </td>
                  )}

                  {/* A janela do cartao e tambem a janela dos detalhes: no
                      celular ela e que devolve tipo, padrinho e a hora do
                      envio. Vira icone ali para a coluna caber sem apertar o
                      nome da crianca ao lado. */}
                  <td className="tabela__acoes">
                    {estreita ? (
                      <BotaoIcone
                        titulo={`Ver o cartão de ${c.crianca_nome}`}
                        tamanho="sm"
                        onClick={() => definirVendo(c)}
                      >
                        <Olho t={20} />
                      </BotaoIcone>
                    ) : (
                      <Button size="sm" variant="ghost" onClick={() => definirVendo(c)}>
                        Ver imagem
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
