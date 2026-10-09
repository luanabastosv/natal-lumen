import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import { Entrada } from "../components/core/Campo.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import {
  checkinAberto,
  desfazerCheckin,
  fazerCheckin,
  listaDoCheckin,
  marcarFalta,
} from "../services/logistica.js";
import { Cuidado, Visto } from "../components/core/icones.jsx";
import Estrelinhas from "../components/feedback/Estrelinhas.jsx";
import EtiquetaDia from "../components/core/EtiquetaDia.jsx";
import { formatarData, formatarDataHora } from "../utils/dinheiro.js";
import EtiquetaDesistente from "../components/core/EtiquetaDesistente.jsx";

export default function Checkin() {
  const { usuario, vinculoAtivo, edicaoAtiva } = useSessao();

  // Duas telas para o mesmo check-in. Quem alcanca a edicao inteira fica na
  // porta, com o leitor de QR, e recebe qualquer crianca: para essa pessoa uma
  // lista de mil nomes nao ajudaria. O monitor responde por uma ou duas
  // instituicoes e confirma a turma dele no onibus, a caminho do evento — ali
  // a lista e mais rapida que digitar codigo. Quem separa os dois e o alcance
  // (`instituicoes` so vem preenchido para quem e filtrado por elas), e nao o
  // nome do perfil.
  const porLista = !usuario?.admin_geral && Array.isArray(vinculoAtivo?.instituicoes);
  // A administracao geral ve as duas: o codigo em cima, para a porta, e a
  // lista embaixo, do jeito que o monitor ve — e quem acompanha e testa as
  // duas telas. Confirmar pelo codigo atualiza a lista.
  const asDuas = Boolean(usuario?.admin_geral);
  const [confirmadosPorCodigo, definirConfirmadosPorCodigo] = useState(0);

  // O check-in so abre nos dias do evento da edicao. Quem decide e o backend
  // (ele recusa o registro fora do dia); a tela so pergunta antes, para nao
  // mostrar uma lista que daria erro a cada toque.
  const [situacao, definirSituacao] = useState(null);
  const [erroSituacao, definirErroSituacao] = useState("");

  useEffect(() => {
    if (!edicaoAtiva) return;
    let vivo = true;
    checkinAberto(edicaoAtiva)
      .then((s) => {
        if (!vivo) return;
        definirSituacao(s);
        definirErroSituacao("");
      })
      .catch((e) => vivo && definirErroSituacao(e.message));
    return () => {
      vivo = false;
    };
  }, [edicaoAtiva]);

  let conteudo;
  if (erroSituacao) conteudo = <Mensagem tipo="erro">{erroSituacao}</Mensagem>;
  else if (situacao === null) conteudo = <Estrelinhas />;
  else if (!situacao.aberto) conteudo = <CheckinFechado dias={situacao.dias} hoje={situacao.hoje} />;
  else if (asDuas)
    conteudo = (
      <>
        <CheckinPorCodigo aoConfirmar={() => definirConfirmadosPorCodigo((n) => n + 1)} />
        <h2 className="painel__titulo checkin__titulo-lista">Como o monitor vê</h2>
        <CheckinPorLista recarregarEm={confirmadosPorCodigo} comBusca />
      </>
    );
  else conteudo = porLista ? <CheckinPorLista /> : <CheckinPorCodigo />;

  return (
    <div>
      {/* O mesmo cabecalho das outras telas, no mesmo lugar: sem a cena do
          onibus, que empurrava o conteudo e so existia aqui. */}
      <div className="pagina__eyebrow">Dia do evento</div>
      <h1 className="pagina__titulo">Check-in</h1>
      <Rabisco className="pagina__onda" />
      <p className="pagina__lede">
        {porLista
          ? "Toque para confirmar a presença. O check-in nunca é recusado, só avisa."
          : "Leia o QR do crachá ou digite o código. O check-in nunca é recusado, só avisa."}
      </p>

      {conteudo}
    </div>
  );
}

/** Fora do dia do evento: diz quando o check-in abre. */
function CheckinFechado({ dias, hoje }) {
  const proximos = dias.filter((d) => d.data > hoje);
  const rotulo = (d) =>
    d.descricao ? `${d.descricao} (${formatarData(d.data)})` : formatarData(d.data);

  return (
    <div className="painel">
      <h2 className="painel__titulo">O check-in abre no dia do evento</h2>
      <p style={{ margin: 0 }}>
        {dias.length === 0
          ? "Esta edição ainda não tem dias do evento cadastrados. Fale com a coordenação."
          : proximos.length === 0
            ? "Os dias do evento desta edição já passaram."
            : `Ele fica disponível em: ${proximos.map(rotulo).join(", ")}.`}
      </p>
    </div>
  );
}

/** A lista do monitor: cada crianca com o botao de confirmar presenca. */
/** `comBusca`: o campo de busca por nome ou codigo. O monitor nao precisa —
 *  a turma dele cabe na tela, e ele confere de cima para baixo. Fica para a
 *  administracao, que ve a edicao inteira. */
function CheckinPorLista({ recarregarEm = 0, comBusca = false }) {
  const { edicaoAtiva, vinculoAtivo } = useSessao();

  const [linhas, definirLinhas] = useState(null);
  const [erro, definirErro] = useState("");
  const [busca, definirBusca] = useState("");
  // Por crianca, e nao um so para a tela: no onibus o monitor toca a fila
  // inteira sem esperar a resposta de cada um, e a rede ali e lenta.
  const [enviando, definirEnviando] = useState(() => new Set());
  const [errosLinha, definirErrosLinha] = useState({});

  const carregar = useCallback(async () => {
    if (!edicaoAtiva) return;
    try {
      definirLinhas(await listaDoCheckin(edicaoAtiva));
      definirErro("");
    } catch (e) {
      definirErro(e.message);
    }
  }, [edicaoAtiva]);

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer.
    // `recarregarEm` muda quando alguem confirma pelo codigo na mesma tela.
    // eslint-disable-next-line react/set-state-in-effect
    carregar();
  }, [carregar, recarregarEm]);

  // Monitor costuma ir em dupla ou trio, cada um no seu celular. Ao voltar
  // para a tela (depois de trocar de app, ou de bloquear o celular), a lista
  // e buscada de novo para trazer o que o colega ja confirmou.
  useEffect(() => {
    function aoVoltar() {
      if (document.visibilityState === "visible") carregar();
    }
    document.addEventListener("visibilitychange", aoVoltar);
    return () => document.removeEventListener("visibilitychange", aoVoltar);
  }, [carregar]);

  async function confirmar(linha) {
    definirEnviando((s) => new Set(s).add(linha.crianca_id));
    definirErrosLinha((er) => {
      const resto = { ...er };
      delete resto[linha.crianca_id];
      return resto;
    });
    try {
      // Os avisos que o servidor devolve (dia errado, cartao faltando) nao
      // aparecem aqui: na lista o monitor so marca presente ou falta, e o
      // aviso embaixo de cada nome so empurrava a lista.
      const entrada = await fazerCheckin(linha.codigo, Number(edicaoAtiva));
      definirLinhas((ls) =>
        ls.map((l) =>
          l.crianca_id === linha.crianca_id
            ? { ...l, checkin_em: entrada.checkin_em, falta_em: null }
            : l,
        ),
      );
    } catch (e) {
      definirErrosLinha((er) => ({ ...er, [linha.crianca_id]: e.message }));
    } finally {
      definirEnviando((s) => {
        const novo = new Set(s);
        novo.delete(linha.crianca_id);
        return novo;
      });
    }
  }

  /** Faltou ou desfazer: as duas devolvem a linha atualizada do servidor.
   *  Sem janela de confirmacao — o erro que isto corrige e um toque, e
   *  desfazer e refazer custam um toque cada. */
  async function trocar(linha, acao) {
    definirEnviando((s) => new Set(s).add(linha.crianca_id));
    try {
      const atual = await acao(linha.crianca_id, Number(edicaoAtiva));
      definirLinhas((ls) =>
        ls.map((l) =>
          l.crianca_id === linha.crianca_id
            ? { ...l, checkin_em: atual.checkin_em, falta_em: atual.falta_em }
            : l,
        ),
      );
    } catch (e) {
      definirErrosLinha((er) => ({ ...er, [linha.crianca_id]: e.message }));
    } finally {
      definirEnviando((s) => {
        const novo = new Set(s);
        novo.delete(linha.crianca_id);
        return novo;
      });
    }
  }

  const variasInstituicoes = useMemo(
    () => new Set((linhas ?? []).map((l) => l.instituicao_id)).size > 1,
    [linhas],
  );

  const visiveis = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    if (!termo) return linhas ?? [];
    return (linhas ?? []).filter(
      (l) => l.nome.toLowerCase().includes(termo) || l.codigo.toLowerCase().includes(termo),
    );
  }, [linhas, busca]);

  if (vinculoAtivo?.instituicoes?.length === 0) {
    return (
      <Mensagem tipo="aviso">
        Nenhuma instituição foi atribuída a você nesta edição ainda. Fale com a coordenação.
      </Mensagem>
    );
  }

  if (linhas === null) {
    return erro ? <Mensagem tipo="erro">{erro}</Mensagem> : <Estrelinhas />;
  }

  const confirmadas = linhas.filter((l) => l.checkin_em).length;
  const faltas = linhas.filter((l) => l.falta_em).length;

  return (
    <>
      <Mensagem tipo="erro">{erro}</Mensagem>

      <div className="checkin-lista__topo">
        <p className="checkin-lista__contagem">
          <strong>{confirmadas}</strong> {confirmadas === 1 ? "presente" : "presentes"} ·{" "}
          <strong>{faltas}</strong> {faltas === 1 ? "falta" : "faltas"} · de {linhas.length}
        </p>
        {comBusca && (
          <Entrada
            rotulo="Buscar"
            tipo="search"
            value={busca}
            onChange={(e) => definirBusca(e.target.value)}
            placeholder="Nome ou código"
          />
        )}
      </div>

      <div className="tabela-rolagem">
        <table className="tabela checkin-lista">
          <thead>
            <tr>
              <th>Código</th>
              <th>Nome</th>
              <th className="checkin-lista__coluna-acao">Presença</th>
            </tr>
          </thead>
          <tbody>
            {visiveis.map((l) => {
              const ocupado = enviando.has(l.crianca_id);
              return (
                <tr
                  key={l.crianca_id}
                  className={l.desistiu_em ? "tabela__linha--desistiu" : undefined}
                >
                  <td>{l.codigo}</td>
                  <td>
                    {l.nome}
                    {/* A autorizacao avisa um cuidado: o monitor recebe a
                        crianca, e e para ele que o aviso mais importa. No
                        celular a dica nao existe, entao o que e vai escrito
                        embaixo do nome. */}
                    {l.cuidados && (
                      <span className="checkin-lista__cuidados">
                        <Cuidado t={12} /> {l.cuidados}
                      </span>
                    )}
                    {variasInstituicoes && (
                      <span className="campo__dica">{l.instituicao}</span>
                    )}
                    {l.desistiu_em && <EtiquetaDesistente className="etiqueta--ao-lado" />}
                    {errosLinha[l.crianca_id] && (
                      <span className="campo__erro">{errosLinha[l.crianca_id]}</span>
                    )}
                  </td>
                  {/* `tabela__marcar` deixa o botao fora do risco de quem
                      desistiu: o check-in nunca e recusado. */}
                  <td className="tabela__marcar checkin-lista__coluna-acao">
                    {l.checkin_em || l.falta_em ? (
                      <span className="checkin-lista__feito">
                        {l.checkin_em ? (
                          <span
                            className="checkin-lista__botao checkin-lista__botao--feito"
                            role="img"
                            aria-label={`${l.nome}: presente desde ${formatarHora(l.checkin_em)}`}
                          >
                            <Visto t={16} />
                            {formatarHora(l.checkin_em)}
                          </span>
                        ) : (
                          <span
                            className="checkin-lista__botao checkin-lista__botao--faltou"
                            role="img"
                            aria-label={`${l.nome}: faltou`}
                          >
                            Faltou
                          </span>
                        )}
                        {/* Pequeno e embaixo, e nao no lugar do botao:
                            desfazer e o gesto raro, e nao pode estar onde o
                            dedo bate para marcar. */}
                        <button
                          type="button"
                          className="checkin-lista__desfazer"
                          disabled={ocupado}
                          onClick={() => trocar(l, desfazerCheckin)}
                          aria-label={`Desfazer a marcação de ${l.nome}`}
                        >
                          {ocupado ? "..." : "desfazer"}
                        </button>
                      </span>
                    ) : (
                      /* Duas respostas, lado a lado: o monitor fecha a turma
                         dele dizendo quem chegou E quem faltou. "Sem marcacao"
                         passa a ser so quem ainda nao foi conferido. */
                      <span className="checkin-lista__escolha">
                        <button
                          type="button"
                          className="checkin-lista__botao"
                          aria-label={`${l.nome} presente`}
                          aria-busy={ocupado || undefined}
                          disabled={ocupado || !edicaoAtiva}
                          onClick={() => confirmar(l)}
                        >
                          {ocupado ? <Estrelinhas tamanho={13} /> : "Presente"}
                        </button>
                        <button
                          type="button"
                          className="checkin-lista__botao checkin-lista__botao--falta"
                          aria-label={`${l.nome} faltou`}
                          disabled={ocupado || !edicaoAtiva}
                          onClick={() => trocar(l, marcarFalta)}
                        >
                          Faltou
                        </button>
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
            {visiveis.length === 0 && (
              <tr>
                <td colSpan={3} className="campo__dica">
                  {linhas.length === 0
                    ? "Nenhuma criança na sua instituição nesta edição."
                    : "Nenhuma criança com esse nome ou código."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

function formatarHora(iso) {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

/** A tela da porta: leitor de QR ou codigo digitado, para qualquer crianca. */
function CheckinPorCodigo({ aoConfirmar }) {
  // A edicao vem da lateral: e a mesma para o sistema inteiro.
  const { edicaoAtiva } = useSessao();

  const [codigo, definirCodigo] = useState("");
  const [resultado, definirResultado] = useState(null);
  const [historico, definirHistorico] = useState([]);
  const [erro, definirErro] = useState("");
  const [enviando, definirEnviando] = useState(false);

  const campoCodigo = useRef(null);

  async function registrar(evento) {
    evento.preventDefault();
    definirErro("");
    definirEnviando(true);

    // O QR do crachá traz "edicao:codigo"; digitado, vem só o código.
    const lido = codigo.trim();
    const soCodigo = lido.includes(":") ? lido.split(":").pop() : lido;

    try {
      const entrada = await fazerCheckin(soCodigo, Number(edicaoAtiva));
      definirResultado(entrada);
      definirHistorico((h) => [entrada, ...h].slice(0, 15));
      definirCodigo("");
      aoConfirmar?.();
    } catch (e) {
      definirErro(e.message);
      definirResultado(null);
    } finally {
      definirEnviando(false);
      // Devolve o foco para o campo: na porta, um check-in vem atrás do outro.
      campoCodigo.current?.focus();
    }
  }

  /** Desfaz a entrada (o codigo trocado na porta): a crianca volta a nao ter
   *  check-in, e a linha fica marcada como desfeita no historico. */
  async function desfazerEntrada(entrada) {
    definirErro("");
    try {
      await desfazerCheckin(entrada.crianca_id, Number(edicaoAtiva));
      const marcar = (h) => (h.crianca_id === entrada.crianca_id ? { ...h, desfeito: true } : h);
      definirHistorico((hs) => hs.map(marcar));
      definirResultado((r) => (r && r.crianca_id === entrada.crianca_id ? marcar(r) : r));
      aoConfirmar?.();
    } catch (e) {
      definirErro(e.message);
    }
  }

  return (
    <>
      <Mensagem tipo="erro">{erro}</Mensagem>

      <form className="painel" onSubmit={registrar}>
        <div className="linha-campos">
          <Entrada
            rotulo="Código da criança"
            value={codigo}
            onChange={(e) => definirCodigo(e.target.value)}
            ref={campoCodigo}
            autoFocus
            dica="O leitor de QR digita sozinho e confirma."
          />
        </div>
        <Button type="submit" carregando={enviando} disabled={!codigo.trim() || !edicaoAtiva}>
          Registrar entrada
        </Button>
      </form>

      {resultado && (
        <div className={`painel ${resultado.avisos.length ? "painel--destaque" : ""}`}>
          <h2 className="painel__titulo">
            {resultado.nome}, {resultado.idade} anos
          </h2>
          <p style={{ margin: "0 0 var(--space-4)", fontSize: "var(--size-body-sm)" }}>
            {resultado.instituicao}
            {resultado.dia_evento && (
              <>
                {" · "}
                <EtiquetaDia
                  data={resultado.dia_evento}
                  descricao={resultado.dia_evento_descricao}
                />
              </>
            )}
            {/* O kit e montado ou nao: o estado "entregue" saiu do sistema, e
                a entrega no dia e este proprio check-in. Nulo quer dizer outra
                coisa: quem esta na porta nao monta kit, e o estado dele nao e
                assunto dessa pessoa. */}
            {resultado.kit_status !== null && (
              <>
                {" · "}
                <span
                  className={`etiqueta etiqueta--${resultado.kit_status === "montado" ? "ok" : "espera"}`}
                >
                  kit {resultado.kit_status}
                </span>
              </>
            )}
          </p>

          {resultado.desfeito ? (
            <Mensagem tipo="aviso">Check-in desfeito: esta criança não está mais com presença.</Mensagem>
          ) : resultado.avisos.length === 0 ? (
            <Mensagem tipo="sucesso">Tudo certo. Pode entrar!</Mensagem>
          ) : (
            <Mensagem tipo="aviso">
              <strong>Atenção:</strong>
              <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                {resultado.avisos.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </Mensagem>
          )}

          {!resultado.desfeito && (
            <Button size="sm" variant="ghost" onClick={() => desfazerEntrada(resultado)}>
              Desfazer check-in
            </Button>
          )}
        </div>
      )}

      {historico.length > 0 && (
        <>
          <h2 className="painel__titulo">Últimas entradas</h2>
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Criança</th>
                  {/* No celular a instituicao desce para debaixo do nome em vez
                      de virar coluna: sao quatro colunas e a tela do check-in e
                      quase sempre um celular na porta do onibus. Uma janela
                      para esconder um dado so custaria um toque por linha numa
                      lista que se le de relance. */}
                  <th className="so-no-monitor">Instituição</th>
                  <th>Hora</th>
                  <th>Avisos</th>
                  <th className="tabela__acoes" />
                </tr>
              </thead>
              <tbody>
                {historico.map((h, i) => (
                  <tr key={`${h.crianca_id}-${i}`}>
                    <td>
                      {h.nome}
                      <span className="so-no-celular">
                        <br />
                        <span className="campo__dica">{h.instituicao}</span>
                      </span>
                    </td>
                    <td className="so-no-monitor">{h.instituicao}</td>
                    <td>{formatarDataHora(h.checkin_em)}</td>
                    <td>
                      {h.desfeito ? (
                        <span className="etiqueta etiqueta--neutra">desfeito</span>
                      ) : h.avisos.length === 0 ? (
                        <span className="etiqueta etiqueta--ok">ok</span>
                      ) : (
                        <span className="etiqueta etiqueta--espera">
                          {h.avisos.length} aviso(s)
                        </span>
                      )}
                    </td>
                    <td className="tabela__acoes">
                      {!h.desfeito && (
                        <button
                          type="button"
                          className="checkin-lista__desfazer"
                          onClick={() => desfazerEntrada(h)}
                          aria-label={`Desfazer o check-in de ${h.nome}`}
                        >
                          desfazer
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
