import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import BotaoIcone from "../components/core/BotaoIcone.jsx";
import { Imprimir, Visto, Xis } from "../components/core/icones.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";
import { buscarProgramacao, concluirProgramacao, salvarProgramacao } from "../services/programacao.js";
import { formatarData, formatarDataHora } from "../utils/dinheiro.js";
import {
  MODELO_2025,
  NUCLEOS,
  QUADRO_VAZIO,
  corDe,
  duracao,
  hora,
  intervalo,
  minutos,
  tempoEscrito,
  tempoPorNucleo,
} from "../utils/programacao.js";

const LISTA_ATIVIDADES = "programacao-atividades";

/** Uma copia funda, para editar sem mexer no que esta salvo. */
const copia = (x) => JSON.parse(JSON.stringify(x));

/** O texto de uma atividade, na cor dela. */
function Atividade({ nome, atividades }) {
  if (!nome) return <span className="celula--vazia">—</span>;
  const cor = corDe(nome, atividades);
  return (
    <span className="prog__atividade" style={cor ? { color: cor } : undefined}>
      {nome}
    </span>
  );
}

/** Campo de hora em texto ("10:10"), e nao `type="time"`: o seletor nativo
 *  mostrava AM/PM e um icone de relogio que cortavam a hora numa coluna
 *  estreita. Aqui sao cinco caracteres, com teclado numerico no celular. */
function CampoHora({ valor, aoMudar, rotulo }) {
  const [texto, definirTexto] = useState(valor);
  const [ultimo, definirUltimo] = useState(valor);
  if (valor !== ultimo) {
    definirUltimo(valor);
    definirTexto(valor);
  }
  return (
    <input
      className="prog__hora-campo"
      inputMode="numeric"
      maxLength={5}
      value={texto}
      aria-label={rotulo}
      onChange={(e) => {
        // Aceita "1010" e completa para "10:10".
        let v = e.target.value.replace(/[^0-9:]/g, "");
        if (/^\d{4}$/.test(v)) v = `${v.slice(0, 2)}:${v.slice(2)}`;
        definirTexto(v);
        if (/^([01]\d|2[0-3]):[0-5]\d$/.test(v)) aoMudar(v);
      }}
      onBlur={() => definirTexto(valor)}
    />
  );
}

/** Um bloco do quadro (Abertura, Rodizios - Manha...), desenhado como a
 *  planilha de sempre: a faixa com o nome do bloco, uma coluna por horario
 *  com o horario e a duracao, uma linha por nucleo, e o intervalo numa coluna
 *  estreita entre os horarios. Horario de "todos" ocupa as quatro linhas.
 *
 *  As colunas dividem a largura por igual (table-layout fixed): o quadro cabe
 *  inteiro na tela do computador, sem rolar de lado, e as atividades quebram
 *  em duas linhas quando precisam, em vez de cortar. */
function Bloco({ bloco, atividades, editando, aoMudar, aoApagar, estreito = false }) {
  const comNucleos = bloco.horarios.some((h) => h.modo === "por_nucleo");
  const linhas = comNucleos ? NUCLEOS : [null];

  function mudarHorario(i, mudanca) {
    const horarios = bloco.horarios.map((h, j) => (j === i ? { ...h, ...mudanca } : h));
    aoMudar({ ...bloco, horarios });
  }

  function acrescentar() {
    const ultimo = bloco.horarios.at(-1);
    const inicio = ultimo ? minutos(ultimo.fim) + 15 : 600;
    aoMudar({
      ...bloco,
      horarios: [
        ...bloco.horarios,
        { inicio: hora(inicio), fim: hora(inicio + 30), modo: comNucleos || !ultimo ? "por_nucleo" : "todos", atividade: null, nucleos: {} },
      ],
    });
  }

  function tirar(i) {
    aoMudar({ ...bloco, horarios: bloco.horarios.filter((_, j) => j !== i) });
  }

  function campoAtividade(valor, aoTrocar, rotulo) {
    const cor = corDe(valor, atividades);
    if (!editando) {
      return valor ? (
        <span className="prog__atividade" style={cor ? { color: cor } : undefined}>
          {valor}
        </span>
      ) : (
        <span className="prog__vazio">—</span>
      );
    }
    return (
      <input
        className="prog__atividade-campo"
        list={LISTA_ATIVIDADES}
        value={valor ?? ""}
        placeholder="Atividade"
        aria-label={rotulo}
        onChange={(e) => aoTrocar(e.target.value || null)}
        style={cor ? { color: cor } : undefined}
      />
    );
  }

  // As colunas do quadro, ja com os intervalos no meio: assim o <colgroup>,
  // o cabecalho e as linhas leem da mesma lista e nunca se desencontram.
  //
  // Entre dois horarios ha SEMPRE a coluna estreita do intervalo, mesmo quando
  // um emenda no outro: so assim blocos com o mesmo numero de horarios (a
  // manha e a tarde) desenham a mesma grade e as colunas terminam no mesmo
  // ponto, um bloco embaixo do outro. Sem folga, o horario seguinte ocupa
  // tambem a coluna do intervalo (colSpan 2) em vez de deixar um vao vazio.
  const colunas = [];
  const grade = [];
  bloco.horarios.forEach((h, i) => {
    const folga = i > 0 ? intervalo(bloco.horarios[i - 1], h) : 0;
    if (i > 0) grade.push({ chave: `g${i}`, intervalo: true });
    if (folga > 0) colunas.push({ tipo: "intervalo", folga, chave: `i${i}` });
    colunas.push({ tipo: "horario", h, i, chave: `h${i}`, span: i > 0 && folga === 0 ? 2 : 1 });
    grade.push({ chave: `c${i}` });
  });
  // A ultima coluna e marcada pelo nome, e nao por `:last-child`: quando um
  // horario de "todos" ocupa as quatro linhas, nas linhas de baixo o ultimo
  // filho passa a ser a celula do meio, e ela perdia a linha da direita.
  const ultima = colunas.at(-1)?.chave;
  const fim = (c) => (c.chave === ultima ? " prog__ultima" : "");

  // No celular o quadro nao cabe de lado: cada horario vira um cartao, um
  // embaixo do outro, com os quatro nucleos em linhas e o intervalo como um
  // aviso entre dois cartoes. O nome do bloco ja esta na aba escolhida. So
  // leitura: a programacao se edita no computador.
  if (estreito) {
    return (
      <section className="prog-cel">
        {bloco.horarios.length === 0 && <p className="prog__sem-horario">Nenhum horário ainda.</p>}
        {bloco.horarios.map((h, i) => {
          const folga = i > 0 ? intervalo(bloco.horarios[i - 1], h) : 0;
          return (
            <div key={i}>
              {folga > 0 && <p className="prog-cel__intervalo">Intervalo de {tempoEscrito(folga)}</p>}
              <article className="prog-cel__horario">
                <header className="prog-cel__hora">
                  <span className="prog__hora-faixa">
                    {h.inicio}
                    <span className="prog__hora-ate">–</span>
                    {h.fim}
                  </span>
                  <span className="prog__duracao-tag">{duracao(h.inicio, h.fim)}</span>
                </header>
                {h.modo === "todos" ? (
                  <div className="prog-cel__todos">
                    <Atividade nome={h.atividade} atividades={atividades} />
                  </div>
                ) : (
                  <ul className="prog-cel__nucleos">
                    {NUCLEOS.map((n) => (
                      <li key={n}>
                        <span className="prog-cel__letra">{n}</span>
                        <Atividade nome={h.nucleos?.[n]} atividades={atividades} />
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            </div>
          );
        })}
      </section>
    );
  }

  return (
    <section className={`prog__bloco ${editando ? "prog__bloco--editando" : ""}`}>
      <header className="prog__faixa">
        {editando ? (
          <input
            className="prog__faixa-campo"
            value={bloco.titulo}
            aria-label="Nome do bloco"
            onChange={(e) => aoMudar({ ...bloco, titulo: e.target.value })}
          />
        ) : (
          <h2 className="prog__faixa-titulo">{bloco.titulo}</h2>
        )}
        {editando && (
          <span className="prog__faixa-acoes">
            <button type="button" className="prog__faixa-botao" onClick={acrescentar}>
              + Horário
            </button>
            <button type="button" className="prog__faixa-botao" onClick={aoApagar}>
              Apagar bloco
            </button>
          </span>
        )}
      </header>

      {bloco.horarios.length === 0 ? (
        <p className="prog__sem-horario">
          Nenhum horário ainda.{editando ? " Use “+ Horário” na faixa acima." : ""}
        </p>
      ) : (
        <div className="prog__rolagem">
          <table
            className="prog__quadro"
            style={{ minWidth: 56 + bloco.horarios.length * (editando ? 140 : 110) }}
          >
            <colgroup>
              {comNucleos && <col className="prog__col-nucleo" />}
              {grade.map((g) => (
                <col key={g.chave} className={g.intervalo ? "prog__col-intervalo" : undefined} />
              ))}
            </colgroup>
            <tbody>
              <tr className="prog__linha-hora">
                {comNucleos && <th className="prog__canto" rowSpan={editando ? 2 : 1} />}
                {colunas.map((c) =>
                  c.tipo === "intervalo" ? (
                    <td key={c.chave} className="prog__intervalo" rowSpan={(editando ? 2 : 1) + linhas.length}>
                      <span>{c.folga} min</span>
                    </td>
                  ) : (
                    <th key={c.chave} className={`prog__hora${fim(c)}`} scope="col" colSpan={c.span}>
                      {editando ? (
                        <span className="prog__hora-edicao">
                          <CampoHora valor={c.h.inicio} rotulo="Começa" aoMudar={(v) => mudarHorario(c.i, { inicio: v })} />
                          <span aria-hidden="true">–</span>
                          <CampoHora valor={c.h.fim} rotulo="Termina" aoMudar={(v) => mudarHorario(c.i, { fim: v })} />
                          <button
                            type="button"
                            className="prog__tirar"
                            onClick={() => tirar(c.i)}
                            aria-label="Tirar este horário"
                            title="Tirar este horário"
                          >
                            <Xis t={12} />
                          </button>
                        </span>
                      ) : (
                        <>
                          <span className="prog__hora-faixa">
                            {c.h.inicio}
                            <span className="prog__hora-ate">–</span>
                            {c.h.fim}
                          </span>
                          <span className="prog__duracao-tag">{duracao(c.h.inicio, c.h.fim)}</span>
                        </>
                      )}
                    </th>
                  ),
                )}
              </tr>
              {/* Na edicao, a linha de baixo do horario escolhe quem participa.
                  Fora dela nao existe: a duracao ja vai na etiqueta do horario. */}
              {editando && (
                <tr className="prog__linha-duracao">
                  {colunas
                    .filter((c) => c.tipo === "horario")
                    .map((c) => (
                      <td key={c.chave} className={`prog__duracao${fim(c)}`} colSpan={c.span}>
                        <span className="prog__modo" role="group" aria-label="Quem participa">
                          {[
                            ["por_nucleo", "Por núcleo"],
                            ["todos", "Todos"],
                          ].map(([v, r]) => (
                            <button
                              key={v}
                              type="button"
                              className={`prog__modo-opcao ${c.h.modo === v ? "prog__modo-opcao--ativa" : ""}`}
                              aria-pressed={c.h.modo === v}
                              onClick={() => mudarHorario(c.i, { modo: v })}
                            >
                              {r}
                            </button>
                          ))}
                        </span>
                      </td>
                    ))}
                </tr>
              )}
              {linhas.map((n, ln) => (
                <tr key={n ?? "todos"} className="prog__linha-nucleo">
                  {comNucleos && (
                    <th className="prog__nucleo" scope="row">
                      {n}
                    </th>
                  )}
                  {colunas
                    .filter((c) => c.tipo === "horario")
                    .map((c) => {
                      const h = c.h;
                      if (h.modo === "todos") {
                        if (ln > 0) return null;
                        return (
                          <td key={c.chave} className={`prog__todos${fim(c)}`} rowSpan={linhas.length} colSpan={c.span}>
                            {campoAtividade(h.atividade, (v) => mudarHorario(c.i, { atividade: v }), "Atividade de todos os núcleos")}
                          </td>
                        );
                      }
                      return (
                        <td key={c.chave} className={`prog__celula${fim(c)}`} colSpan={c.span}>
                          {campoAtividade(
                            h.nucleos?.[n] ?? null,
                            (v) => mudarHorario(c.i, { nucleos: { ...h.nucleos, [n]: v } }),
                            `Atividade do núcleo ${n}`,
                          )}
                        </td>
                      );
                    })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** As atividades e as cores delas: so na edicao. */
function EditarAtividades({ atividades, aoMudar }) {
  return (
    <section className="prog__secao">
      <div className="prog__secao-topo">
        <h2 className="prog__secao-titulo">Atividades e cores</h2>
        <Button size="sm" variant="ghost" onClick={() => aoMudar([...atividades, { nome: "", cor: "#153377" }])}>
          + Atividade
        </Button>
      </div>
      <p className="prog__secao-dica">A cor de cada atividade no quadro.</p>
      <div className="prog__atividades">
        {atividades.map((a, i) => (
          <span key={i} className="prog__atividade-linha">
            <input
              type="color"
              value={a.cor}
              aria-label={`Cor de ${a.nome || "atividade"}`}
              onChange={(e) => aoMudar(atividades.map((x, j) => (j === i ? { ...x, cor: e.target.value } : x)))}
            />
            <input
              className="campo__controle"
              value={a.nome}
              placeholder="Nome da atividade"
              aria-label="Nome da atividade"
              onChange={(e) => aoMudar(atividades.map((x, j) => (j === i ? { ...x, nome: e.target.value } : x)))}
            />
            <BotaoIcone tamanho="sm" perigo titulo="Tirar a atividade" onClick={() => aoMudar(atividades.filter((_, j) => j !== i))}>
              <Xis t={14} />
            </BotaoIcone>
          </span>
        ))}
      </div>
    </section>
  );
}

/** O nome do dia como a equipe fala: "Sábado · 05/12/2026". */
const nomeDoDia = (d) => [d.descricao?.trim(), formatarData(d.data)].filter(Boolean).join(" · ");

/** Quem esta em cada nucleo num dia: as instituicoes, cada uma com a bolinha
 *  da cor da bata — e pela bata que o monitor acha o grupo no meio do evento.
 *  Vem da organizacao dos nucleos da monitoria; aqui so se le. */
function NucleosDoDia({ dia }) {
  const semNucleo = dia.instituicoes.filter((i) => !i.nucleo);
  return (
    <div className="prog-nucleos">
      <div className="prog-nucleos__grade">
        {NUCLEOS.map((n) => {
          const insts = dia.instituicoes.filter((i) => i.nucleo === n);
          return (
            <div key={n} className="prog-nucleos__coluna">
              <h4 className="prog-nucleos__letra">Núcleo {n}</h4>
              {insts.length === 0 ? (
                <p className="prog__vazio">—</p>
              ) : (
                <ul className="prog-nucleos__lista">
                  {insts.map((i) => (
                    <li key={i.nome}>
                      <span
                        className={`amostra-bata ${i.cor_bata_hex ? "" : "amostra-bata--vazia"}`}
                        style={i.cor_bata_hex ? { background: i.cor_bata_hex } : undefined}
                        title={i.cor_bata_nome ?? "Cor da bata não definida"}
                      />
                      <span>
                        {i.nome}
                        {i.cor_bata_nome && <span className="prog-nucleos__cor"> · {i.cor_bata_nome}</span>}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
      {semNucleo.length > 0 && (
        <p className="prog-nucleos__falta">
          Ainda sem núcleo: {semNucleo.map((i) => i.nome).join(", ")}.
        </p>
      )}
    </div>
  );
}

/** Os nucleos de todos os dias, na tela. */
function NucleosPorDia({ dias, semTitulo = false }) {
  if (dias.length === 0) return null;
  return (
    <section className="prog__secao">
      {/* Na janela o titulo dela ja diz "Núcleos". */}
      {!semTitulo && <h2 className="prog__secao-titulo">Núcleos</h2>}
      {dias.map((d) => (
        <div key={d.dia_evento_id} className="prog-nucleos__dia">
          <h3 className="prog-nucleos__dia-titulo">{nomeDoDia(d)}</h3>
          {d.instituicoes.length === 0 ? (
            <p className="prog__secao-dica">Nenhuma instituição neste dia ainda.</p>
          ) : (
            <NucleosDoDia dia={d} />
          )}
        </div>
      ))}
    </section>
  );
}

/** Quanto tempo cada nucleo passa em cada atividade dos rodizios. */
function TempoPorNucleo({ blocos, atividades }) {
  const conta = tempoPorNucleo(blocos);
  const nomes = Object.keys(conta).sort();
  if (nomes.length === 0) return null;
  return (
    <section className="prog__secao">
      <h2 className="prog__secao-titulo">Tempo de cada núcleo nos rodízios</h2>
      <div className="tabela-rolagem">
        <table className="tabela tabela--densa prog__tempo">
          <thead>
            <tr>
              <th>Atividade</th>
              {NUCLEOS.map((n) => (
                <th key={n} className="prog__tempo-num">Núcleo {n}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {nomes.map((nome) => (
              <tr key={nome}>
                <td><Atividade nome={nome} atividades={atividades} /></td>
                {NUCLEOS.map((n) => (
                  <td key={n} className="prog__tempo-num">
                    {conta[nome][n] ? tempoEscrito(conta[nome][n]) : "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Programacao do dia do evento: o quadro de horarios que a coordenacao monta
 *  todo ano — abertura, rodizios de cada nucleo e as atividades de todos —,
 *  com edicao para ajustar o deste ano. */
export default function Programacao() {
  const { edicaoAtiva, edicao } = useSessao();
  const notificar = useNotificar();
  const [salvo, definirSalvo] = useState(null);
  const [rascunho, definirRascunho] = useState(null);
  const [erro, definirErro] = useState("");
  const [salvando, definirSalvando] = useState(false);
  const [confirmandoConclusao, definirConfirmandoConclusao] = useState(false);
  const [concluindo, definirConcluindo] = useState(false);

  // Trocou de edicao na lateral: a programacao da outra some na hora, durante
  // o render, sem esperar o efeito.
  const [ultimaEdicao, definirUltimaEdicao] = useState(edicaoAtiva);
  if (edicaoAtiva !== ultimaEdicao) {
    definirUltimaEdicao(edicaoAtiva);
    definirSalvo(null);
    definirRascunho(null);
  }

  useEffect(() => {
    if (!edicaoAtiva) return undefined;
    let vivo = true;
    buscarProgramacao(edicaoAtiva)
      .then((r) => vivo && definirSalvo(r))
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, [edicaoAtiva]);

  // No celular a programacao so se le: editar um quadro de rodizios numa
  // tela estreita e trabalho de computador. Um rascunho comecado no
  // computador continua guardado e volta quando a tela alarga.
  const estreito = useTelaEstreita();
  const editando = rascunho !== null && !estreito;
  const quadro = editando ? rascunho : salvo;

  // E aparece por partes, um bloco por aba. Os nucleos, no celular e no
  // computador, ficam numa janela: a pagina e o quadro.
  const [parte, definirParte] = useState(0);
  const [vendoNucleos, definirVendoNucleos] = useState(false);
  const partes = quadro ? quadro.blocos.map((b, i) => ({ id: i, rotulo: b.titulo || "Bloco" })) : [];
  // O bloco escolhido pode deixar de existir: volta para o primeiro.
  const parteAtual = partes.some((p) => p.id === parte) ? parte : 0;
  const mostra = (id) => !estreito || parteAtual === id;


  // A coordenacao geral monta e conclui; o resto da equipe so ve e imprime,
  // e so depois de concluida. Quem diz e o servidor.
  const podeEditar = Boolean(salvo?.pode_editar);
  const concluida = Boolean(salvo?.concluida_em);

  async function mudarConclusao(valor) {
    definirErro("");
    definirConcluindo(true);
    try {
      definirSalvo(await concluirProgramacao(edicaoAtiva, valor));
      definirConfirmandoConclusao(false);
      notificar(valor ? "Programação liberada para as equipes." : "Programação reaberta: só a coordenação vê.");
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirConcluindo(false);
    }
  }

  async function salvar() {
    definirErro("");
    definirSalvando(true);
    try {
      const r = await salvarProgramacao(edicaoAtiva, {
        atividades: rascunho.atividades.filter((a) => a.nome.trim()),
        blocos: rascunho.blocos,
        // A versao que estava salva quando a edicao abriu: se outra pessoa
        // salvou no meio do caminho, o servidor recusa em vez de sobrescrever.
        versao_lida: salvo?.atualizado_em ?? null,
      });
      definirSalvo(r);
      definirRascunho(null);
      notificar("Programação salva.");
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  return (
    <div className="prog-pagina">
      <div className="pagina__cabecalho">
        <div className="pagina__texto">
          <div className="pagina__eyebrow">Dia do evento</div>
          <h1 className="pagina__titulo">Programação</h1>
          <Rabisco className="pagina__onda" />
          <p className="pagina__lede">Horários e rodízios do dia do evento.</p>
          {salvo?.atualizado_em && (
            <p className="prog__editado">
              {podeEditar && (
                <span className={`etiqueta ${concluida ? "etiqueta--ok" : "etiqueta--neutra"}`}>
                  {concluida ? "Liberada para as equipes" : "Em montagem · só a coordenação vê"}
                </span>
              )}
              Editado por {salvo.atualizado_por ?? "alguém da coordenação"} em{" "}
              {formatarDataHora(salvo.atualizado_em)}
            </p>
          )}
        </div>
        {salvo?.existe && !editando && (
          <span className="prog__acoes-topo">
            <Button
              size="sm"
              variant="ghost"
              soIcone
              titulo="Imprimir programação"
              iconLeft={<Imprimir t={15} />}
              onClick={() => window.print()}
            />
            {(salvo.nucleos ?? []).length > 0 && (
              <Button size="sm" variant="ghost" onClick={() => definirVendoNucleos(true)}>
                Ver núcleos
              </Button>
            )}
            {/* Editar so no computador, e so a coordenacao. */}
            {podeEditar && !estreito && (
              <Button size="sm" onClick={() => definirRascunho(copia(salvo))}>
                Editar programação
              </Button>
            )}
          </span>
        )}
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {!salvo && !erro && <Carregando tela>Buscando a programação...</Carregando>}

      {salvo && !salvo.existe && !editando && !podeEditar && (
        <EmptyState
          titulo="A programação ainda não foi liberada"
          corpo="Assim que a coordenação liberar a programação, ela aparece aqui."
        />
      )}

      {salvo && !salvo.existe && !editando && podeEditar && (
        <EmptyState
          titulo="Esta edição ainda não tem programação"
          corpo={
            estreito
              ? "A programação é montada no computador. Assim que for salva, aparece aqui."
              : "Comece pelo quadro de 2025 e ajuste o que mudar neste ano, ou monte do zero."
          }
          acao={
            !estreito && (
              <span style={{ display: "inline-flex", flexWrap: "wrap", gap: "var(--space-2)", justifyContent: "center" }}>
                <Button onClick={() => definirRascunho(copia(MODELO_2025))}>Usar o quadro de 2025</Button>
                <Button variant="ghost" onClick={() => definirRascunho(copia(QUADRO_VAZIO))}>
                  Começar do zero
                </Button>
              </span>
            )
          }
        />
      )}

      {quadro && (editando || quadro.existe) && (
        <>
          {/* As sugestoes dos campos de atividade. */}
          <datalist id={LISTA_ATIVIDADES}>
            {quadro.atividades.map((a) => (
              <option key={a.nome} value={a.nome} />
            ))}
          </datalist>

          {estreito && (
            // Todas as abas a vista, cada uma com a mesma largura, sem arrastar
            // de lado: "Rodizios - Manha" quebra no traco, uma palavra por linha.
            <div className="prog-abas" role="tablist" style={{ gridTemplateColumns: `repeat(${partes.length}, minmax(0, 1fr))` }}>
              {partes.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  role="tab"
                  aria-selected={parteAtual === p.id}
                  className={`aba ${parteAtual === p.id ? "aba--ativa" : ""}`}
                  onClick={() => definirParte(p.id)}
                >
                  {p.rotulo.split(/\s+[-–]\s+/).map((pedaco, k) => (
                    <span key={k}>{pedaco}</span>
                  ))}
                </button>
              ))}
            </div>
          )}

          <div className={editando ? undefined : "prog__quadros"}>
            {quadro.blocos.map((b, i) =>
              mostra(i) ? (
                <Bloco
                  key={i}
                  bloco={b}
                  atividades={quadro.atividades}
                  editando={editando}
                  estreito={estreito}
                  aoMudar={(novo) =>
                    definirRascunho((r) => ({ ...r, blocos: r.blocos.map((x, j) => (j === i ? novo : x)) }))
                  }
                  aoApagar={() =>
                    definirRascunho((r) => ({ ...r, blocos: r.blocos.filter((_, j) => j !== i) }))
                  }
                />
              ) : null,
            )}
          </div>

          {/* Liberar fica embaixo, a direita, longe dos botoes do dia a dia:
              e o passo final, feito uma vez, depois de conferir o quadro. So no
              computador, como a edicao. */}
          {podeEditar && !editando && !estreito && (
            <div className="prog__liberar">
              {concluida ? (
                <Button size="sm" variant="ghost" onClick={() => mudarConclusao(false)} carregando={concluindo}>
                  Reabrir para ajustes
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="suave"
                  iconLeft={<Visto t={15} />}
                  onClick={() => definirConfirmandoConclusao(true)}
                >
                  Liberar para as equipes
                </Button>
              )}
            </div>
          )}

          {editando && (
            <>
              <div className="prog__adicionar-bloco">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    definirRascunho((r) => ({
                      ...r,
                      blocos: [...r.blocos, { titulo: "Novo bloco", horarios: [] }],
                    }))
                  }
                >
                  + Bloco
                </Button>
              </div>
              <EditarAtividades
                atividades={rascunho.atividades}
                aoMudar={(atividades) => definirRascunho((r) => ({ ...r, atividades }))}
              />
            </>
          )}

          {/* O tempo de cada nucleo e conferencia de quem monta o rodizio: so
              aparece na edicao. */}
          {editando && <TempoPorNucleo blocos={quadro.blocos} atividades={quadro.atividades} />}

          {vendoNucleos && !editando && (
            <Modal titulo="Núcleos" rotulo="Programação" tamanho="largo" aoFechar={() => definirVendoNucleos(false)}>
              <div className="prog-info">
                <NucleosPorDia dias={salvo.nucleos ?? []} semTitulo />
              </div>
            </Modal>
          )}

          {editando && (
            <div className="prog__barra-edicao">
              <p>Editando a programação. Nada é gravado até salvar.</p>
              <span className="prog__barra-edicao-acoes">
                <Button size="sm" variant="ghost" onClick={() => definirRascunho(null)} disabled={salvando}>
                  Cancelar
                </Button>
                <Button size="sm" onClick={salvar} carregando={salvando}>
                  Salvar programação
                </Button>
              </span>
            </div>
          )}
        </>
      )}

      {confirmandoConclusao && (
        <Modal
          titulo="Liberar a programação para as equipes?"
          aoFechar={() => definirConfirmandoConclusao(false)}
          rodape={
            <>
              <Button variant="ghost" onClick={() => definirConfirmandoConclusao(false)} disabled={concluindo}>
                Cancelar
              </Button>
              <Button onClick={() => mudarConclusao(true)} carregando={concluindo}>
                Liberar
              </Button>
            </>
          }
        >
          <p className="prog__confirmar">
            Todas as equipes da edição passam a ver e imprimir a programação. Você
            ainda pode editar depois, e quem abrir verá a versão salva.
          </p>
        </Modal>
      )}

      {/* A folha: A4 deitado, o quadro inteiro numa pagina so, para colar na
          parede e entregar a cada monitor. Sai do que esta SALVO, nunca do
          rascunho. A regra @page vai junto, como no ImprimirLista: e o jeito
          confiavel de o papel sair deitado. */}
      {/* A folha fica SEMPRE montada (escondida na tela pelo CSS), e nao so
          enquanto se imprime: no celular o print() nao espera o dialogo
          fechar — volta na hora, e a folha que sumia logo depois saia em
          branco. Montada, tambem vale o "Imprimir" do proprio navegador. */}
      {salvo?.existe &&
        !editando &&
        createPortal(
          <div className="impressao">
            <style>{"@page { size: A4 landscape; margin: 8mm; }"}</style>
{/* Uma folha por dia: o quadro e o mesmo, os nucleos nao. Sem dia
                cadastrado, sai uma folha so, sem os nucleos. */}
            {(salvo.nucleos?.length ? salvo.nucleos : [null]).map((dia) => (
              <section key={dia?.dia_evento_id ?? "unica"} className="impressao__folha prog-folha">
                <header className="prog-folha__topo">
                  <div>
                    <h1>Programação do evento</h1>
                    <p>
                      {edicao?.nome ?? "Natal Lumen"}
                      {dia && <strong> · {nomeDoDia(dia)}</strong>}
                    </p>
                  </div>
                  <p className="prog-folha__quando">
                    Impresso em {new Date().toLocaleDateString("pt-BR")}
                  </p>
                </header>
                {salvo.blocos.map((b, i) => (
                  <Bloco key={i} bloco={b} atividades={salvo.atividades} editando={false} />
                ))}
                {dia && dia.instituicoes.length > 0 && <NucleosDoDia dia={dia} />}
              </section>
            ))}
          </div>,
          document.body,
        )}
    </div>
  );
}
