import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import { Selecao } from "../components/core/Campo.jsx";
import FaixaDeAbas from "../components/core/FaixaDeAbas.jsx";
import MenuAcoes from "../components/core/MenuAcoes.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import { useSessao } from "../contexts/useSessao.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";
import { listarLembretes } from "../services/lembretes.js";
import { rotuloDia } from "../utils/dinheiro.js";
import { tomDoDia } from "../utils/dias.js";

/** "2026-12-19" -> "sábado, 19 de dezembro". Montada pelas partes, e nao com
 *  new Date("2026-12-19"): essa le a data como meia-noite em UTC, e no Brasil
 *  ela vira o dia anterior. */
function diaPorExtenso(iso) {
  const [ano, mes, dia] = iso.split("-").map(Number);
  return new Date(ano, mes - 1, dia).toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

/** O texto do lembrete, como o padrinho vai le-lo.
 *
 *  E o rascunho do modelo que vai para a aprovacao da Meta (ver
 *  docs/LEMBRETE_DO_EVENTO.md). O mesmo texto para todo mundo: a ultima frase
 *  e que explica a quem recebe duas mensagens por que recebeu duas — uma por
 *  dia, cada uma com os cartoes das criancas daquele dia.
 */
function textoDoLembrete(nome, data) {
  return [
    `Olá, ${nome}!`,
    `O Natal Lumen está chegando, e queremos muito você com a gente no ${diaPorExtenso(data)}.`,
    "Os cartões abaixo foram escritos pelas crianças que você apadrinhou e que estarão no evento neste dia.",
    "Apadrinhou crianças que vão em outro dia do evento? Você vai receber outra mensagem, com os cartões delas.",
  ].join("\n\n");
}

/* A ordem e a da lista: quem ja pode sair vem primeiro, e o que ainda depende
   de alguem vem depois. */
const SITUACOES = {
  pronto: { rotulo: "Pronto", plural: "prontos", classe: "etiqueta--ok", ordem: 0 },
  sem_whatsapp: { rotulo: "Sem WhatsApp", plural: "sem WhatsApp", classe: "etiqueta--parado", ordem: 1 },
  em_progresso: { rotulo: "Em progresso", plural: "em progresso", classe: "etiqueta--espera", ordem: 2 },
};

/** Os cartoes que faltam, do jeito que se procura na pilha: "EE10 festa". */
function oQueFalta(p) {
  return p.cartoes
    .filter((c) => !c.cartao_id)
    .map((c) => `${c.crianca_codigo} ${c.tipo}`)
    .join(", ");
}

/* A tela parte dos DIAS, e nao dos padrinhos: o lembrete e um convite para um
   dia, e o padrinho com criancas no sabado e no domingo recebe dois — um em
   cada aba, cada um com os cartoes das criancas daquele dia. */
export default function EnvioCartoes() {
  const { edicaoAtiva } = useSessao();
  const navegar = useNavigate();
  const estreita = useTelaEstreita();

  const [dias, definirDias] = useState([]);
  const [abaAtiva, definirAbaAtiva] = useState(0);
  const [instituicao, definirInstituicao] = useState("");
  const [situacao, definirSituacao] = useState("");
  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  // O dia cuja mensagem esta aberta na janela. Fora dela, null.
  const [mensagemDe, definirMensagemDe] = useState(null);

  const buscar = useCallback(async () => {
    definirErro("");
    try {
      definirDias(await listarLembretes(edicaoAtiva));
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoAtiva]);

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer.
    // eslint-disable-next-line react/set-state-in-effect
    if (edicaoAtiva) buscar();
  }, [edicaoAtiva, buscar]);

  // Trocar de edicao recomeca a tela: as abas eram os dias da anterior.
  const [ultimaEdicao, definirUltimaEdicao] = useState(edicaoAtiva);
  if (edicaoAtiva !== ultimaEdicao) {
    definirUltimaEdicao(edicaoAtiva);
    definirAbaAtiva(0);
    definirInstituicao("");
  }

  const dia = dias[abaAtiva] ?? null;
  const semDia = dia && !dia.dia_id;

  // O filtro so oferece as instituicoes que tem crianca NESTE dia.
  const instituicoes = new Map();
  for (const p of dia?.padrinhos ?? []) {
    for (const c of p.cartoes) instituicoes.set(String(c.instituicao_id), c.instituicao);
  }

  // O padrinho entra inteiro quando tem ao menos uma crianca da instituicao: o
  // lembrete dele e um so, e mostrar metade dos cartoes enganaria sobre o que
  // vai sair.
  const daInstituicao = (dia?.padrinhos ?? []).filter(
    (p) => !instituicao || p.cartoes.some((c) => String(c.instituicao_id) === instituicao),
  );
  const contagem = (s) => daInstituicao.filter((p) => p.situacao === s).length;
  const linhas = daInstituicao
    .filter((p) => !situacao || p.situacao === situacao)
    .sort((a, b) => SITUACOES[a.situacao].ordem - SITUACOES[b.situacao].ordem);

  return (
    <div>
      <button
        type="button"
        className="pasta-aberta__voltar"
        style={{ marginBottom: "var(--space-3)" }}
        onClick={() => navegar("/padrinhos")}
      >
        ← Padrinhos
      </button>
      <div className="pagina__eyebrow">Captação</div>
      <h1 className="pagina__titulo">Envio de cartões</h1>
      <Rabisco className="pagina__onda" />
      <p className="pagina__lede">
        Um lembrete por padrinho <strong>e por dia</strong>. Só sai com todos os cartões do dia.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {carregando ? (
        <Carregando tela>Montando os lembretes...</Carregando>
      ) : dias.length === 0 ? (
        <EmptyState
          titulo="Nenhum dia do evento cadastrado"
          corpo="Os lembretes são separados por dia. Cadastre os dias da edição e defina o dia de cada instituição."
        />
      ) : (
        <>
          <FaixaDeAbas reiniciarEm={edicaoAtiva}>
            {dias.map((d, i) => (
              /* Os pontinhos sao IRMAOS do botao da aba, e nao filhos: botao
                 dentro de botao e HTML invalido, e um clique viraria o outro. O
                 CSS os posiciona por cima da borda direita da aba. */
              <div key={d.dia_id ?? "sem-dia"} className="aba-com-menu">
                <button
                  type="button"
                  role="tab"
                  aria-selected={abaAtiva === i}
                  className={`aba ${abaAtiva === i ? "aba--ativa" : ""} ${d.dia_id ? "aba--com-menu" : ""}`}
                  onClick={() => {
                    definirAbaAtiva(i);
                    definirInstituicao("");
                    definirSituacao("");
                  }}
                >
                  <span>
                    {d.dia_id ? rotuloDia(d.data, d.descricao) : "Sem dia definido"}
                    {/* Depois do nome, como nas abas de criancas: a cor do dia
                        e a mesma nas duas telas. */}
                    {d.dia_id && <span className={`aba__ponto dia--${tomDoDia(d.descricao)}`} />}
                  </span>
                  <span className="aba__contagem">
                    {d.dia_id
                      ? `${d.padrinhos.filter((p) => p.situacao === "pronto").length} de ${d.padrinhos.length} prontos`
                      : `${d.padrinhos.length} padrinho(s)`}
                  </span>
                </button>
                {/* Sem dia nao ha mensagem: ela diz justamente qual e o dia. */}
                {d.dia_id && (
                  <span
                    className={`aba-com-menu__menu ${abaAtiva === i ? "aba-com-menu__menu--ativa" : ""}`}
                  >
                    <MenuAcoes
                      titulo={`Ações de ${rotuloDia(d.data, d.descricao)}`}
                      itens={[{ rotulo: "Ver mensagem", aoEscolher: () => definirMensagemDe(d) }]}
                    />
                  </span>
                )}
              </div>
            ))}
          </FaixaDeAbas>

          {dia && (
            <div className="barra-acoes">
              <Selecao value={instituicao} onChange={(e) => definirInstituicao(e.target.value)}>
                <option value="">Todas as instituições</option>
                {[...instituicoes].map(([id, nome]) => (
                  <option key={id} value={id}>{nome}</option>
                ))}
              </Selecao>
              {!semDia && (
                <Selecao value={situacao} onChange={(e) => definirSituacao(e.target.value)}>
                  <option value="">Todas as situações</option>
                  {Object.entries(SITUACOES).map(([id, s]) => (
                    <option key={id} value={id}>{s.rotulo}</option>
                  ))}
                </Selecao>
              )}
              {!semDia &&
                Object.entries(SITUACOES).map(([id, s]) => (
                  <span key={id} className={`etiqueta ${s.classe}`}>
                    {contagem(id)} {s.plural}
                  </span>
                ))}

              {!semDia && (
                <div className="barra-acoes__ponta">
                  <Button
                    size="sm"
                    disabled
                    titulo="O disparo entra quando o sistema for conectado ao CRM."
                  >
                    Enviar aos {contagem("pronto")} prontos
                  </Button>
                </div>
              )}
            </div>
          )}

          {semDia && (
            <Mensagem tipo="aviso">
              Instituições ainda sem dia do evento. O lembrete destas crianças só sai depois que
              o dia for definido em Instituições.
            </Mensagem>
          )}

          {dia && linhas.length === 0 ? (
            <EmptyState
              titulo="Nenhum lembrete aqui"
              corpo={
                instituicao || situacao
                  ? "Nenhum padrinho com esse filtro."
                  : "Nenhuma criança deste dia tem apadrinhamento pago ainda."
              }
            />
          ) : (
            dia && (
              <div className="tabela-rolagem">
                <table
                  className={`tabela tabela--densa tabela--ancorada ${
                    estreita ? "tabela--compacta" : ""
                  }`}
                >
                  <colgroup>
                    <col />
                    {!estreita && <col style={{ width: 150 }} />}
                    <col style={{ width: estreita ? 68 : 80 }} />
                    {!estreita && <col />}
                    {!semDia && <col style={{ width: estreita ? 112 : 120 }} />}
                  </colgroup>
                  <thead>
                    <tr>
                      <th>Padrinho</th>
                      {!estreita && <th>WhatsApp</th>}
                      <th title="Cartões já subidos, do total deste dia">Cartões</th>
                      {!estreita && <th>Falta</th>}
                      {!semDia && <th>Situação</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {linhas.map((p) => {
                      const falta = oQueFalta(p);
                      return (
                        <tr key={p.padrinho_id}>
                          <td>
                            {p.padrinho_nome}
                            {p.outros_dias > 0 && (
                              <span
                                className="etiqueta etiqueta--neutra lembrete__dias"
                                title="Tem crianças em mais de um dia do evento: recebe um lembrete por dia."
                              >
                                {p.outros_dias + 1} dias
                              </span>
                            )}
                            {/* No celular o que falta desce para baixo do nome:
                                e a unica informacao da linha que diz o que fazer. */}
                            {estreita && falta && (
                              <>
                                <br />
                                <span className="campo__dica">Falta: {falta}</span>
                              </>
                            )}
                          </td>
                          {!estreita && <td>{p.whatsapp || "—"}</td>}
                          <td>
                            {p.cartoes.length - p.faltam}/{p.cartoes.length}
                          </td>
                          {!estreita && <td className="lembrete__falta">{falta || "—"}</td>}
                          {!semDia && (
                            <td>
                              <span className={`etiqueta ${SITUACOES[p.situacao].classe}`}>
                                {SITUACOES[p.situacao].rotulo}
                              </span>
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )
          )}

          {mensagemDe && (
            <Modal
              rotulo="Mensagem do dia"
              titulo={rotuloDia(mensagemDe.data, mensagemDe.descricao)}
              aoFechar={() => definirMensagemDe(null)}
            >
              <p className="lembretes__texto">
                {textoDoLembrete(
                  mensagemDe.padrinhos.find((p) => p.situacao === "pronto")?.padrinho_nome.split(" ")[0] ??
                    "Maria",
                  mensagemDe.data,
                )}
              </p>
              <p className="campo__dica">
                Rascunho do modelo que vai para a aprovação da Meta. Os cartões seguem junto,
                como imagens. O disparo entra quando o sistema for conectado ao CRM.
              </p>
            </Modal>
          )}
        </>
      )}
    </div>
  );
}
