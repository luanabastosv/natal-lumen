import { useCallback, useEffect, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import ConferirCartoes from "../components/dados/ConferirCartoes.jsx";
import { Selecao } from "../components/core/Campo.jsx";
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

  const buscar = useCallback(async () => {
    if (!edicaoAtiva) return;
    try {
      if (!pasta) {
        definirPastas(await listarPastas(edicaoAtiva));
      } else {
        definirCartoes(
          await listarCartoes({
            situacao,
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
  }, [situacao, edicaoAtiva, pasta]);

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
    definirCarregando(true);
    definirPasta(p);
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

      {/* O envio mora DENTRO da pasta: sobe-se a pilha de uma escola, e o
          servidor recusa na previa o arquivo cujo codigo for de outra. No andar
          das pastas nao ha o que subir — nao se sabe de quem seria. */}
      {pasta && pode("subir_cartoes") && (
        <>
          {!previa ? (
            <form className="painel" onSubmit={enviarLote}>
              <h2 className="painel__titulo">Subir cartões digitalizados</h2>
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

                  <span className="pasta__etiquetas">
                    {p.total === 0 && (
                      <span className="etiqueta etiqueta--espera">nenhum cartão ainda</span>
                    )}
                    {p.enviados > 0 && (
                      <span className="etiqueta etiqueta--ok">{p.enviados} enviado(s)</span>
                    )}
                    {/* Cartao sem destinatario: a crianca nao tem padrinho
                        daquele tipo, ou o apadrinhamento dela e so promessa. */}
                    {p.sem_padrinho > 0 && (
                      <span
                        className="etiqueta etiqueta--espera"
                        title="Cartões sem padrinho confirmado: ou a criança não tem padrinho daquele tipo, ou o apadrinhamento ainda é promessa sem pagamento."
                      >
                        {p.sem_padrinho} sem padrinho
                      </span>
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
                {!estreita && (
                  <>
                    <th>Tipo</th>
                    <th>Padrinho</th>
                  </>
                )}
                <th>Situação</th>
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
                  <td>
                    {c.crianca_nome}
                    <br />
                    <span className="campo__dica">{c.instituicao}</span>
                  </td>
                  {!estreita && (
                    <>
                      <td>{c.tipo}</td>
                      <td>
                        {c.padrinho_nome ?? (
                          <span className="etiqueta etiqueta--espera">sem padrinho</span>
                        )}
                        {c.padrinho_whatsapp && <><br />{c.padrinho_whatsapp}</>}
                      </td>
                    </>
                  )}
                  <td>
                    <span className={`etiqueta ${c.status === "enviado" ? "etiqueta--ok" : "etiqueta--espera"}`}>
                      {c.status === "enviado" ? "Enviado" : "A enviar"}
                    </span>
                    {c.enviado_em && (
                      <><br /><span className="campo__dica">{formatarDataHora(c.enviado_em)}</span></>
                    )}
                  </td>
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
          {/* Tipo e o WhatsApp do padrinho entraram aqui quando a lista
              estreita deixou de mostra-los: a janela tem de responder tudo o
              que a linha deixou de dizer. */}
          <dl className="ficha ficha--duas" style={{ marginTop: "var(--space-4)" }}>
            <dt>Instituição</dt>
            <dd>{vendo.instituicao}</dd>
            <dt>Tipo</dt>
            <dd>{vendo.tipo}</dd>
            <dt>Padrinho</dt>
            <dd>
              {vendo.padrinho_nome ?? "sem padrinho ainda"}
              {vendo.padrinho_whatsapp && ` · ${vendo.padrinho_whatsapp}`}
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
