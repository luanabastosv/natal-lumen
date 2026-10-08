import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import { Entrada } from "../components/core/Campo.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { checkinAberto, fazerCheckin, listaDoCheckin } from "../services/logistica.js";
import { Visto } from "../components/core/icones.jsx";
import Estrelinhas from "../components/feedback/Estrelinhas.jsx";
import EtiquetaDia from "../components/core/EtiquetaDia.jsx";
import { formatarData, formatarDataHora } from "../utils/dinheiro.js";

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
  else conteudo = porLista ? <CheckinPorLista /> : <CheckinPorCodigo />;

  return (
    <div>
      {/* Abertura de dominio: a cena da area a direita do titulo. Uma por
          pagina, e so na tela que abre a area — nao se repete la dentro. */}
      <div className="abertura-dominio">
        <div>
          <div className="pagina__eyebrow">Dia do evento</div>
          <h1 className="pagina__titulo">Check-in</h1>
          <Rabisco className="pagina__onda" />
          <p className="pagina__lede">
            {porLista
              ? "Toque para confirmar a presença. O check-in nunca é recusado, só avisa."
              : "Leia o QR do crachá ou digite o código. O check-in nunca é recusado, só avisa."}
          </p>
        </div>
        <img className="abertura-dominio__cena" src="/acesso/images/cena-onibus.png" alt="" />
      </div>

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
function CheckinPorLista() {
  const { edicaoAtiva, vinculoAtivo } = useSessao();

  const [linhas, definirLinhas] = useState(null);
  const [erro, definirErro] = useState("");
  const [busca, definirBusca] = useState("");
  // Por crianca, e nao um so para a tela: no onibus o monitor toca a fila
  // inteira sem esperar a resposta de cada um, e a rede ali e lenta.
  const [enviando, definirEnviando] = useState(() => new Set());
  const [avisos, definirAvisos] = useState({});
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
    // eslint-disable-next-line react/set-state-in-effect
    carregar();
  }, [carregar]);

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
      const entrada = await fazerCheckin(linha.codigo, Number(edicaoAtiva));
      definirLinhas((ls) =>
        ls.map((l) =>
          l.crianca_id === linha.crianca_id ? { ...l, checkin_em: entrada.checkin_em } : l,
        ),
      );
      definirAvisos((a) => ({ ...a, [linha.crianca_id]: entrada.avisos }));
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

  return (
    <>
      <Mensagem tipo="erro">{erro}</Mensagem>

      <div className="checkin-lista__topo">
        <p className="checkin-lista__contagem">
          <strong>{confirmadas}</strong> de {linhas.length} com presença confirmada
        </p>
        <Entrada
          rotulo="Buscar"
          tipo="search"
          value={busca}
          onChange={(e) => definirBusca(e.target.value)}
          placeholder="Nome ou código"
        />
      </div>

      <div className="tabela-rolagem">
        <table className="tabela checkin-lista">
          <thead>
            <tr>
              <th>Código</th>
              <th>Nome</th>
              <th className="checkin-lista__coluna-acao">Confirmar presença</th>
            </tr>
          </thead>
          <tbody>
            {visiveis.map((l) => {
              const ocupado = enviando.has(l.crianca_id);
              const avisosDaLinha = (avisos[l.crianca_id] ?? []).filter(
                (a) => !a.includes("ja tinha feito check-in"),
              );
              return (
                <tr
                  key={l.crianca_id}
                  className={l.desistiu_em ? "tabela__linha--desistiu" : undefined}
                >
                  <td>{l.codigo}</td>
                  <td>
                    {l.nome}
                    {variasInstituicoes && (
                      <span className="campo__dica">{l.instituicao}</span>
                    )}
                    {l.desistiu_em && <span className="campo__dica">desistiu</span>}
                    {avisosDaLinha.map((a) => (
                      <span key={a} className="checkin-lista__aviso">
                        {a}
                      </span>
                    ))}
                    {errosLinha[l.crianca_id] && (
                      <span className="campo__erro">{errosLinha[l.crianca_id]}</span>
                    )}
                  </td>
                  {/* `tabela__marcar` deixa o botao fora do risco de quem
                      desistiu: o check-in nunca e recusado. */}
                  <td className="tabela__marcar checkin-lista__coluna-acao">
                    {l.checkin_em ? (
                      <span
                        className="checkin-lista__botao checkin-lista__botao--feito"
                        role="img"
                        aria-label={`${l.nome}: presença confirmada às ${formatarHora(l.checkin_em)}`}
                        title={`Confirmada às ${formatarHora(l.checkin_em)}`}
                      >
                        <Visto t={24} />
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="checkin-lista__botao"
                        aria-label={`Confirmar presença de ${l.nome}`}
                        aria-busy={ocupado || undefined}
                        disabled={ocupado || !edicaoAtiva}
                        onClick={() => confirmar(l)}
                      >
                        {ocupado ? <Estrelinhas tamanho={13} /> : <Visto t={24} />}
                      </button>
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
function CheckinPorCodigo() {
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
    } catch (e) {
      definirErro(e.message);
      definirResultado(null);
    } finally {
      definirEnviando(false);
      // Devolve o foco para o campo: na porta, um check-in vem atrás do outro.
      campoCodigo.current?.focus();
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

          {resultado.avisos.length === 0 ? (
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
                      {h.avisos.length === 0 ? (
                        <span className="etiqueta etiqueta--ok">ok</span>
                      ) : (
                        <span className="etiqueta etiqueta--espera">
                          {h.avisos.length} aviso(s)
                        </span>
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
