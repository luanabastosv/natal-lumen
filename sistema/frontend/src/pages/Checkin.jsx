import { useCallback, useEffect, useMemo, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
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
import { Cuidado, Visto, Xis } from "../components/core/icones.jsx";
import Estrelinhas from "../components/feedback/Estrelinhas.jsx";
import { formatarData } from "../utils/dinheiro.js";
import EtiquetaDesistente from "../components/core/EtiquetaDesistente.jsx";

export default function Checkin() {
  const { usuario, vinculoAtivo, edicaoAtiva } = useSessao();

  // Uma tela so: a lista. Nao ha leitor de QR no evento — a tela da porta,
  // com o codigo do cracha, saiu. O monitor ve a turma das instituicoes dele;
  // quem alcanca a edicao inteira ve todas, com a busca por nome ou codigo,
  // porque mil nomes sem busca nao se percorrem. Quem separa os dois e o
  // alcance (`instituicoes` so vem preenchido para quem e filtrado por elas).
  const daEdicaoInteira = Boolean(usuario?.admin_geral) || !Array.isArray(vinculoAtivo?.instituicoes);

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
  else conteudo = <CheckinPorLista comBusca={daEdicaoInteira} />;

  return (
    <div>
      {/* O mesmo cabecalho das outras telas, no mesmo lugar: sem a cena do
          onibus, que empurrava o conteudo e so existia aqui. */}
      <div className="pagina__eyebrow">Dia do evento</div>
      <h1 className="pagina__titulo">Check-in</h1>
      <Rabisco className="pagina__onda" />
      <p className="pagina__lede">
        Toque para confirmar a presença ou a falta de cada criança.
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
function CheckinPorLista({ comBusca = false }) {
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
                            <span className="checkin-lista__rotulo">{formatarHora(l.checkin_em)}</span>
                          </span>
                        ) : (
                          <span
                            className="checkin-lista__botao checkin-lista__botao--faltou"
                            role="img"
                            aria-label={`${l.nome}: faltou`}
                          >
                            <Xis t={16} />
                            <span className="checkin-lista__rotulo">Faltou</span>
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
                          {ocupado ? (
                            <Estrelinhas tamanho={13} />
                          ) : (
                            <>
                              <Visto t={18} />
                              <span className="checkin-lista__rotulo">Presente</span>
                            </>
                          )}
                        </button>
                        <button
                          type="button"
                          className="checkin-lista__botao checkin-lista__botao--falta"
                          aria-label={`${l.nome} faltou`}
                          disabled={ocupado || !edicaoAtiva}
                          onClick={() => trocar(l, marcarFalta)}
                        >
                          <Xis t={18} />
                          <span className="checkin-lista__rotulo">Faltou</span>
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
