import { useCallback, useEffect, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import { Entrada } from "../components/core/Campo.jsx";
import EtiquetaDia from "../components/core/EtiquetaDia.jsx";
import FaixaDeAbas from "../components/core/FaixaDeAbas.jsx";
import Button from "../components/core/Button.jsx";
import { Imprimir } from "../components/core/icones.jsx";
import ImprimirLista from "../components/dados/ImprimirLista.jsx";
import {
  EstatisticasImpressas,
  TabelaEstatisticas,
} from "../components/dados/EstatisticasKits.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { formatarData, formatarDataHora } from "../utils/dinheiro.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";
import {
  instituicoesDosKits,
  listarKits,
  montagemDaInstituicao,
  perfilDosKits,
  salvarMontagemDaInstituicao,
} from "../services/logistica.js";
import EtiquetaDesistente from "../components/core/EtiquetaDesistente.jsx";

const TODAS = "todas";

/* A tela toda parte das criancas, e nao dos kits: a crianca existe desde a
   importacao e o kit so ganha registro quando alguem mexe nele. Uma crianca
   cadastrada hoje aparece aqui hoje, pendente — e por isso a lista nunca
   diverge da de criancas. */
export default function Kits() {
  const { edicaoAtiva } = useSessao();

  const [dados, definirDados] = useState({ itens: [], total: 0, resumo: {} });
  const [abas, definirAbas] = useState([]);
  const [abaAtiva, definirAbaAtiva] = useState(TODAS);
  // A janela de "Montagem + Conferencia": null fechada; aberta, os dois nomes
  // e quantos kits a escola tem.
  const [montagem, definirMontagem] = useState(null);
  const [salvandoMontagem, definirSalvandoMontagem] = useState(false);
  const [imprimindo, definirImprimindo] = useState(false);
  // A conta de idade e sexo da instituicao da aba, que e a que vai para a
  // compra dos presentes. null = janela fechada.
  const [estatisticas, definirEstatisticas] = useState(null);
  /* A ordem e do servidor, e nao do navegador: ordenar so o que ja veio
     ordenaria a PAGINA, e nao a lista. Comeca por codigo porque e assim que a
     lista de papel da instituicao chega, e conferir uma contra a outra e o que
     a equipe faz o dia todo. */
  const [ordem, definirOrdem] = useState({ por: "codigo", sentido: "asc" });

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");

  const estreita = useTelaEstreita();

  const buscar = useCallback(async () => {
    try {
      definirDados(
        await listarKits({
          edicao_id: edicaoAtiva,
          instituicao_id: abaAtiva === TODAS ? "" : abaAtiva,
          ordenar_por: ordem.por,
          ordem: ordem.sentido,
          // As abas ja recortam por escola, entao a lista de uma aba cabe
          // inteira. Sem isto, a tela mostrava as 100 primeiras e calava sobre
          // o resto — e a equipe montaria a escola pela metade.
          por_pagina: 500,
        }),
      );
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoAtiva, abaAtiva, ordem]);

  const recarregarAbas = useCallback(async () => {
    if (!edicaoAtiva) return;
    try {
      definirAbas(await instituicoesDosKits(edicaoAtiva));
    } catch (e) {
      definirErro(e.message);
    }
  }, [edicaoAtiva]);

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer.
    // eslint-disable-next-line react/set-state-in-effect
    if (edicaoAtiva) buscar();
  }, [edicaoAtiva, abaAtiva, ordem, buscar]);

  useEffect(() => {
    // eslint-disable-next-line react/set-state-in-effect
    recarregarAbas();
  }, [recarregarAbas]);

  // Trocar de edicao recomeca a tela: as abas eram da edicao anterior.
  const [ultimaEdicao, definirUltimaEdicao] = useState(edicaoAtiva);
  if (edicaoAtiva !== ultimaEdicao) {
    definirUltimaEdicao(edicaoAtiva);
    definirAbaAtiva(TODAS);
  }

  /** Abre a "Montagem + Conferencia" da instituicao da aba, ja com os
   *  nomes que estiverem gravados — e por ela tambem que se corrige. */
  async function abrirMontagem() {
    definirErro("");
    try {
      const atual = await montagemDaInstituicao(edicaoAtiva, abaAtiva);
      definirMontagem({
        montado_por: atual.montado_por ?? "",
        conferido_por: atual.conferido_por ?? "",
        kits: atual.kits,
      });
    } catch (e) {
      definirErro(e.message);
    }
  }

  /** A montagem e por ESCOLA: a equipe monta a pilha inteira de uma
   *  instituicao e outra pessoa confere tudo. Os dois nomes valem para todos
   *  os kits dela (sem as desistentes) — e quem monta e voluntario do dia,
   *  sem conta no sistema, por isso e nome escrito, e nao usuario. */
  async function salvarMontagem(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvandoMontagem(true);
    try {
      await salvarMontagemDaInstituicao({
        edicao_id: edicaoAtiva,
        instituicao_id: Number(abaAtiva),
        montado_por: montagem.montado_por.trim() || null,
        conferido_por: montagem.conferido_por.trim() || null,
      });
      definirMontagem(null);
      await Promise.all([buscar(), recarregarAbas()]);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvandoMontagem(false);
    }
  }

  /** A celula de quem montou ou conferiu: so leitura. */
  function celulaNome(nome) {
    return nome ? <span title={nome}>{nome}</span> : <span className="celula--vazia">—</span>;
  }

  /* O papel sai com a lista INTEIRA do filtro, e nao com a pagina que esta na
     tela: a equipe leva a folha para a mesa de montagem, e uma lista cortada na
     centesima crianca faria faltar caixa sem ninguem entender por que. */
  async function todosOsItens() {
    const tudo = await listarKits({
      edicao_id: edicaoAtiva,
      instituicao_id: abaAtiva === TODAS ? "" : abaAtiva,
      ordenar_por: ordem.por,
      ordem: ordem.sentido,
      por_pagina: 2000,
    });
    return tudo.itens;
  }

  /** As linhas de idade e sexo, ja recortadas pela aba. Busca na hora: a conta
   *  muda quando alguem cadastra ou desiste, e a janela nao pode mostrar a
   *  de ontem. */
  async function buscarEstatisticas() {
    const linhas = await perfilDosKits(edicaoAtiva);
    return abaAtiva === TODAS
      ? linhas
      : linhas.filter((l) => String(l.instituicao_id) === String(abaAtiva));
  }

  async function abrirEstatisticas() {
    definirErro("");
    try {
      definirEstatisticas(await buscarEstatisticas());
    } catch (e) {
      definirErro(e.message);
    }
  }

  /* No papel, cada folha leva a conta da propria instituicao. Sem agrupar, a
     folha unica leva a conta de tudo o que esta nela. */
  async function prepararEstatisticas() {
    const linhas = await buscarEstatisticas();
    return (grupo) => (
      <EstatisticasImpressas
        linhas={grupo ? linhas.filter((l) => l.instituicao === grupo) : linhas}
      />
    );
  }

  /* O dia vai em toda folha, sempre: a pilha de cada escola tem de estar
     pronta para o dia DELA, e a folha anda solta pela mesa de montagem. O dia
     e o da instituicao (o da aba); sem agrupar, a folha so ganha dia se todas
     as criancas nela forem no mesmo. */
  function diaDaFolha(grupo, itens) {
    const aba = grupo && abas.find((a) => a.instituicao === grupo);
    let dia = aba?.dia_evento ? { data: aba.dia_evento, descricao: aba.dia_evento_descricao } : null;
    if (!aba) {
      const datas = new Set(itens.map((k) => k.dia_evento));
      if (datas.size === 1 && itens[0]?.dia_evento) {
        dia = { data: itens[0].dia_evento, descricao: itens[0].dia_evento_descricao };
      } else if (datas.size > 1) {
        return null;
      }
    }
    if (!dia) return "Dia a definir";
    return dia.descricao?.trim()
      ? `${dia.descricao.trim()} · ${formatarData(dia.data)}`
      : formatarData(dia.data);
  }

  /* Clicar no titulo da coluna ordena por ela; clicar de novo inverte. E o
     gesto que qualquer planilha tem, e aqui ele importa: a equipe precisa da
     lista por idade para separar presente, por sexo para separar brinquedo, e
     por codigo para conferir contra o papel. */
  function ordenarPor(coluna) {
    definirOrdem((atual) =>
      atual.por === coluna
        ? { por: coluna, sentido: atual.sentido === "asc" ? "desc" : "asc" }
        : { por: coluna, sentido: "asc" },
    );
  }

  /** O <th> clicavel. Funcao que devolve JSX, e nao componente declarado aqui
   *  dentro: um componente nasceria diferente a cada render e o botao
   *  remontaria, tirando o foco de quem ordena pelo teclado.
   *
   *  O botao vai POR DENTRO do <th>, e nao o <th> inteiro clicavel: e o botao
   *  que entra na ordem do Tab e se anuncia como acionavel. */
  function coluna(id, rotulo) {
    const ativa = ordem.por === id;
    return (
      <th aria-sort={ativa ? (ordem.sentido === "asc" ? "ascending" : "descending") : "none"}>
        <button
          type="button"
          className={`coluna-ordem ${ativa ? "coluna-ordem--ativa" : ""}`}
          onClick={() => ordenarPor(id)}
          title={`Ordenar por ${rotulo.toLowerCase()}`}
        >
          {rotulo}
          <span className="coluna-ordem__seta">
            {ativa ? (ordem.sentido === "desc" ? "▾" : "▴") : "⇅"}
          </span>
        </button>
      </th>
    );
  }

  const abaDaVez = abas.find((a) => String(a.instituicao_id) === String(abaAtiva));
  const montados = dados.resumo.montado ?? 0;
  const pendentes = dados.resumo.pendente ?? 0;

  return (
    <div>
      {/* Imprimir no alto, ao lado do titulo, so o icone: o mesmo lugar e o
          mesmo botao da lista de criancas, em toda tela que imprime. */}
      <div className="pagina__cabecalho">
        <div className="pagina__texto">
          <div className="pagina__eyebrow">Estrutura</div>
          <h1 className="pagina__titulo">Kits</h1>
          <Rabisco className="pagina__onda" />
          <p className="pagina__lede">
            Uma criança, um kit. Montagem e conferência são por instituição; riscada é quem desistiu.
          </p>
        </div>
        <div className="pagina__acoes">
          <Button
            size="sm"
            variant="ghost"
            soIcone
            titulo="Imprimir lista"
            iconLeft={<Imprimir t={15} />}
            onClick={() => definirImprimindo(true)}
            disabled={!edicaoAtiva}
          />
        </div>
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      <FaixaDeAbas reiniciarEm={edicaoAtiva}>
        <button
          type="button"
          role="tab"
          aria-selected={abaAtiva === TODAS}
          className={`aba ${abaAtiva === TODAS ? "aba--ativa" : ""}`}
          onClick={() => definirAbaAtiva(TODAS)}
        >
          <span>Todas</span>
          <span className="aba__contagem">
            {abas.reduce((s, a) => s + a.total - a.desistentes, 0)} confirmadas
          </span>
        </button>

        {abas.map((a) => (
          <button
            key={a.instituicao_id}
            type="button"
            role="tab"
            aria-selected={String(abaAtiva) === String(a.instituicao_id)}
            className={`aba ${String(abaAtiva) === String(a.instituicao_id) ? "aba--ativa" : ""}`}
            onClick={() => definirAbaAtiva(a.instituicao_id)}
            title={a.desistentes > 0 ? `${a.desistentes} desistente(s) nesta lista` : undefined}
          >
            <span>{a.instituicao}</span>
            {/* As confirmadas, sem as desistentes: e quantas caixas a escola
                leva. O que falta montar fica na etiqueta dentro da aba. */}
            <span className="aba__contagem">
              {a.total - a.desistentes}{" "}
              {a.total - a.desistentes === 1 ? "confirmada" : "confirmadas"}
            </span>
          </button>
        ))}
      </FaixaDeAbas>

      <div className="barra-acoes">
        <span className="etiqueta etiqueta--ok">{montados} montados</span>
        <span className="etiqueta etiqueta--espera">{pendentes} a montar</span>
        {abaDaVez?.dia_evento && (
          <EtiquetaDia data={abaDaVez.dia_evento} descricao={abaDaVez.dia_evento_descricao} />
        )}

        <div className="barra-acoes__ponta">
          {/* So dentro de uma instituicao: a conta e da compra de UMA escola. */}
          {abaAtiva !== TODAS && (
            <>
              <Button size="sm" variant="ghost" onClick={abrirEstatisticas}>
                Ver estatísticas
              </Button>
              {/* A montagem e por escola: so dentro da aba de uma
                  instituicao, nunca na aba Todas. */}
              <Button size="sm" variant="secondary" onClick={abrirMontagem}>
                Montagem + Conferência
              </Button>
            </>
          )}
        </div>
      </div>

      {montagem && (
        <Modal
          rotulo={abaDaVez?.instituicao}
          titulo="Montagem + Conferência"
          aoFechar={() => !salvandoMontagem && definirMontagem(null)}
        >
          <form onSubmit={salvarMontagem}>
            <p className="campo__dica" style={{ marginTop: 0 }}>
              Os nomes valem para os {montagem.kits}{" "}
              {montagem.kits === 1 ? "kit" : "kits"} desta instituição (sem as
              desistentes). Com quem montou, todos ficam montados; com quem
              conferiu, todos ficam conferidos. Apagar um nome desfaz.
            </p>
            <Entrada
              rotulo="Montado por"
              value={montagem.montado_por}
              onChange={(e) => definirMontagem({ ...montagem, montado_por: e.target.value })}
              placeholder="Nome de quem montou"
              maxLength={120}
            />
            <Entrada
              rotulo="Conferido por"
              value={montagem.conferido_por}
              onChange={(e) => definirMontagem({ ...montagem, conferido_por: e.target.value })}
              placeholder="Nome de quem conferiu"
              maxLength={120}
              dica={
                montagem.conferido_por.trim() && !montagem.montado_por.trim()
                  ? "Diga primeiro quem montou."
                  : undefined
              }
            />
            <div className="barra-acoes barra-acoes--fim" style={{ justifyContent: "flex-end" }}>
              <Button
                type="submit"
                variant="secondary"
                carregando={salvandoMontagem}
                disabled={Boolean(montagem.conferido_por.trim() && !montagem.montado_por.trim())}
              >
                Salvar
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {estatisticas && (
        <Modal
          titulo={abaDaVez?.instituicao ?? "Instituição"}
          rotulo="Estatísticas:"
          aoFechar={() => definirEstatisticas(null)}
        >
          <TabelaEstatisticas linhas={estatisticas} />
          <p className="campo__dica">Sem as desistentes: a caixa delas não se monta.</p>
        </Modal>
      )}

      {imprimindo && (
        <ImprimirLista
          titulo="Kits"
          subtitulo="Montagem"
          aoFechar={() => definirImprimindo(false)}
          buscarTudo={todosOsItens}
          etiquetaDoGrupo={diaDaFolha}
          extra={{
            rotulo: "Estatísticas de idade e sexo no topo de cada folha",
            preparar: prepararEstatisticas,
          }}
          colunas={[
            { id: "codigo", rotulo: "Código", valor: (k) => k.crianca_codigo },
            {
              id: "nome",
              rotulo: "Criança",
              valor: (k) => k.crianca_nome,
              riscar: (k) => Boolean(k.desistiu_em),
            },
            { id: "idade", rotulo: "Idade", valor: (k) => k.idade },
            { id: "sexo", rotulo: "Sexo", valor: (k) => k.sexo },
            { id: "instituicao", rotulo: "Instituição", valor: (k) => k.instituicao },
            { id: "montado_por", rotulo: "Montado por", valor: (k) => k.montado_por ?? "" },
            { id: "conferido_por", rotulo: "Conferido por", valor: (k) => k.conferido_por ?? "" },
            {
              id: "checkin",
              rotulo: "Check-in",
              valor: (k) => (k.checkin_em ? `Sim, ${formatarDataHora(k.checkin_em)}` : ""),
            },
            {
              id: "situacao",
              rotulo: "Status",
              // Em maiuscula so a desistente: no papel e ela que precisa saltar
              // aos olhos de quem monta, porque e a caixa que NAO se faz.
              valor: (k) => (k.desistiu_em ? "DESISTENTE" : "Confirmada"),
            },
          ]}
          /* A sugestao e o formato que a equipe de estrutura usa toda semana:
             uma folha por instituicao, deitado (cabem mais linhas por folha e
             sobra largura para o nome inteiro), com o quadradinho para marcar a
             lapis enquanto monta. A coluna de instituicao fica de fora porque
             ela ja e o titulo da folha. */
          sugestao={{
            colunas: ["codigo", "nome", "idade", "sexo", "situacao"],
            orientacao: "paisagem",
            agruparPor: "instituicao",
            ordenarPor: "codigo",
            caixinha: true,
          }}
          agrupamentos={[{ id: "instituicao", rotulo: "Instituição", de: (k) => k.instituicao }]}
          ordenacoes={[
            { id: "codigo", rotulo: "Código", de: (k) => k.crianca_codigo },
            { id: "nome", rotulo: "Nome", de: (k) => k.crianca_nome },
            { id: "idade", rotulo: "Idade", de: (k) => String(k.idade).padStart(3, "0") },
            { id: "sexo", rotulo: "Sexo", de: (k) => `${k.sexo} ${k.crianca_nome}` },
          ]}
        />
      )}

      {carregando ? (
        <Carregando tela>Carregando kits...</Carregando>
      ) : dados.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhuma criança nesta lista"
          corpo="Importe as listas das instituições para os kits aparecerem aqui."
        />
      ) : (
        <div className="tabela-rolagem">
          {/* `ancorada` = `table-layout: fixed`. Com as larguras no <colgroup>,
              trocar de aba nao move nenhuma coluna de lugar — o olho de quem
              confere fica no mesmo ponto da tela ao passar de escola em escola,
              como ja acontece na planilha de criancas. */}
          <table
            className={`tabela tabela--densa tabela--ancorada ${
              estreita ? "tabela--compacta" : ""
            }`}
          >
            <colgroup>
              <col style={{ width: estreita ? 74 : 92 }} />
              <col />
              {!estreita && (
                <>
                  <col style={{ width: 64 }} />
                  <col style={{ width: 58 }} />
                </>
              )}
              {!estreita && abaAtiva === TODAS && <col style={{ width: 220 }} />}
              {!estreita && <col style={{ width: 116 }} />}
              {!estreita && <col style={{ width: 78 }} />}
              {!estreita && <col style={{ width: 160 }} />}
              {!estreita && <col style={{ width: 160 }} />}
            </colgroup>
            <thead>
              <tr>
                {coluna("codigo", "Código")}
                {coluna("nome", "Criança")}
                {!estreita && coluna("idade", "Idade")}
                {!estreita && coluna("sexo", "Sexo")}
                {/* Dentro de uma aba de instituicao a coluna seria a mesma
                    palavra em todas as linhas — a aba ja diz qual escola e. */}
                {!estreita && abaAtiva === TODAS && coluna("instituicao", "Instituição")}
                {!estreita && <th>Status</th>}
                {/* Se a crianca ja chegou ao evento: no dia, e o que diz se o
                    kit montado saiu da pilha ou ainda espera alguem. */}
                {!estreita && <th>Check-in</th>}
                {/* Ordenar por "montado por" e ordenar por montado: os a
                    montar juntos, que e o grupo que a equipe procura. */}
                {!estreita && coluna("montado", "Montado por")}
                {!estreita && <th>Conferido por</th>}
              </tr>
            </thead>
            <tbody>
              {dados.itens.map((k) => (
                <tr
                  key={k.crianca_id}
                  className={k.desistiu_em ? "tabela__linha--desistiu" : ""}
                  title={k.desistiu_em ? `${k.crianca_nome} desistiu do evento` : undefined}
                >
                  <td>{k.crianca_codigo}</td>
                  <td>
                    {k.crianca_nome}
                    {estreita && (
                      <>
                        <br />
                        <span className="campo__dica">
                          {k.idade} anos · {k.sexo}
                          {abaAtiva === TODAS && ` · ${k.instituicao}`}
                        </span>
                        {/* No celular nao ha coluna de status: "Confirmada"
                            repetida em toda linha so empurraria o nome. Fica
                            a excecao, que e o que muda o trabalho. */}
                        {k.desistiu_em && (
                          <>
                            <br />
                            <EtiquetaStatus desistiu />
                          </>
                        )}
                        {(k.checkin_em || k.falta_em) && (
                          <>
                            <br />
                            <EtiquetaCheckin quando={k.checkin_em} faltou={Boolean(k.falta_em)} />
                          </>
                        )}
                        {/* Sem colunas no celular: montagem e conferencia
                            descem para baixo do nome. */}
                        {k.montado_por && (
                          <>
                            <br />
                            <span className="campo__dica">Montado por {k.montado_por}</span>
                          </>
                        )}
                        {k.conferido_por && (
                          <>
                            <br />
                            <span className="campo__dica">Conferido por {k.conferido_por}</span>
                          </>
                        )}
                      </>
                    )}
                  </td>
                  {!estreita && <td>{k.idade}</td>}
                  {!estreita && <td>{k.sexo}</td>}
                  {!estreita && abaAtiva === TODAS && <td>{k.instituicao}</td>}
                  {!estreita && (
                    <td className="tabela__status">
                      <EtiquetaStatus desistiu={Boolean(k.desistiu_em)} />
                    </td>
                  )}
                  {!estreita && (
                    <td className="tabela__status">
                      <EtiquetaCheckin quando={k.checkin_em} faltou={Boolean(k.falta_em)} />
                    </td>
                  )}
                  {!estreita && <td>{celulaNome(k.montado_por)}</td>}
                  {!estreita && <td>{celulaNome(k.conferido_por)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </div>
  );
}

/** Confirmada ou desistente: se o kit desta crianca ainda deve ser montado. */
function EtiquetaStatus({ desistiu }) {
  return desistiu ? (
    <EtiquetaDesistente />
  ) : (
    <span className="etiqueta etiqueta--ok">Confirmada</span>
  );
}

/** Se a crianca ja chegou ao evento. A hora fica na dica do mouse: na coluna,
 *  o que se procura e so "veio ou nao veio". */
function EtiquetaCheckin({ quando, faltou }) {
  if (faltou) return <span className="etiqueta etiqueta--parado">Faltou</span>;
  return quando ? (
    <span className="etiqueta etiqueta--ok" title={`Check-in em ${formatarDataHora(quando)}`}>
      Presente
    </span>
  ) : (
    <span className="celula--vazia">—</span>
  );
}
