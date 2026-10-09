import { useCallback, useEffect, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import { Selecao } from "../components/core/Campo.jsx";
import EtiquetaDia from "../components/core/EtiquetaDia.jsx";
import FaixaDeAbas from "../components/core/FaixaDeAbas.jsx";
import Button from "../components/core/Button.jsx";
import { ChevronDireita, Imprimir } from "../components/core/icones.jsx";
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
  conferirKit,
  conferirKits,
  instituicoesDosKits,
  listarKits,
  mudarKits,
  perfilDosKits,
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
  const [marcando, definirMarcando] = useState([]);
  const [conferindo, definirConferindo] = useState([]);
  // As linhas escolhidas para uma acao em lote (ids de crianca).
  const [selecionadas, definirSelecionadas] = useState([]);
  const [aplicandoLote, definirAplicandoLote] = useState(false);
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

  // Trocar de aba limpa a selecao: as linhas escolhidas eram de outra escola,
  // e uma acao em lote nao pode alcancar o que nao esta na tela.
  const [ultimaAba, definirUltimaAba] = useState(abaAtiva);
  if (abaAtiva !== ultimaAba) {
    definirUltimaAba(abaAtiva);
    definirSelecionadas([]);
  }

  /** Marca UM kit como montado, na hora do clique.
   *
   *  A montagem acontece com a caixa na mao: a pessoa monta, marca, pega a
   *  proxima. Um "salvar" no fim da lista obrigaria a lembrar o que ja tinha
   *  feito, e um lote perdido no meio significaria remontar a conferencia
   *  inteira de cabeca. Desfazer e pela selecao, de proposito: e o gesto raro,
   *  e nao pode estar a um clique distraido de distancia.
   */
  async function montar(item) {
    const alvo = "montado";
    definirErro("");
    definirMarcando((a) => [...a, item.crianca_id]);
    try {
      const [atualizado] = await mudarKits([item.crianca_id], alvo);
      definirDados((atual) => ({
        ...atual,
        // Troca so a linha mexida: recarregar a lista inteira devolveria a
        // pessoa ao topo, e ela esta no meio de uma pilha de cinquenta.
        itens: atual.itens.map((i) => (i.crianca_id === atualizado.crianca_id ? atualizado : i)),
        resumo: {
          ...atual.resumo,
          montado: (atual.resumo.montado ?? 0) + (alvo === "montado" ? 1 : -1),
          // A desistente nao conta em "a montar" (o servidor ja a deixa de fora).
          pendente:
            (atual.resumo.pendente ?? 0) +
            (item.desistiu_em ? 0 : alvo === "montado" ? -1 : 1),
        },
      }));
      recarregarAbas();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirMarcando((a) => a.filter((x) => x !== item.crianca_id));
    }
  }

  /** Quem clica e quem conferiu: o nome vem do servidor, que sabe quem esta
   *  logado. Troca so a linha, pelo mesmo motivo do checkbox. */
  async function conferir(item) {
    definirErro("");
    definirConferindo((a) => [...a, item.crianca_id]);
    try {
      const atualizado = await conferirKit(item.crianca_id);
      definirDados((atual) => ({
        ...atual,
        itens: atual.itens.map((i) => (i.crianca_id === atualizado.crianca_id ? atualizado : i)),
      }));
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirConferindo((a) => a.filter((x) => x !== item.crianca_id));
    }
  }

  /* A selecao vale para o que esta NA TELA. A desistente nunca entra: o kit
     dela nao se marca, nem sozinho nem em lote. */
  const selecionaveis = dados.itens.filter((k) => !k.desistiu_em);
  const escolhidas = dados.itens.filter((k) => selecionadas.includes(k.crianca_id));
  const todasSelecionadas =
    selecionaveis.length > 0 && selecionaveis.every((k) => selecionadas.includes(k.crianca_id));

  function alternarSelecao(id) {
    definirSelecionadas((atual) =>
      atual.includes(id) ? atual.filter((x) => x !== id) : [...atual, id],
    );
  }

  /** O seletor da barra: escolhe um grupo inteiro de uma vez. */
  function selecionar(qual) {
    const grupos = {
      todas: selecionaveis,
      a_montar: selecionaveis.filter((k) => k.status !== "montado"),
      sem_conferencia: selecionaveis.filter((k) => k.status === "montado" && !k.conferido_por),
      nenhuma: [],
    };
    definirSelecionadas((grupos[qual] ?? []).map((k) => k.crianca_id));
  }

  /* Cada acao so aparece se valer para TODAS as selecionadas: misturar
     montados e a montar nao oferece nem conferir nem desmontar, porque metade
     das linhas nao teria como receber a acao. */
  const acoesDoLote = escolhidas.length
    ? [
        escolhidas.every((k) => k.status !== "montado") && {
          id: "montar",
          rotulo: "Montados",
        },
        escolhidas.every((k) => k.status === "montado" && !k.conferido_por) && {
          id: "conferir",
          rotulo: "Conferidos",
        },
        escolhidas.every((k) => k.status === "montado") && {
          id: "desfazer",
          rotulo: "A montar (desfazer montagem)",
        },
      ].filter(Boolean)
    : [];

  async function aplicarLote(acao) {
    if (!acao) return;
    definirErro("");
    definirAplicandoLote(true);
    try {
      if (acao === "montar") {
        const ids = escolhidas.filter((k) => k.status !== "montado").map((k) => k.crianca_id);
        if (ids.length) await mudarKits(ids, "montado");
      } else if (acao === "conferir") {
        await conferirKits(escolhidas.map((k) => k.crianca_id));
      } else if (acao === "desfazer") {
        const ids = escolhidas.filter((k) => k.status === "montado").map((k) => k.crianca_id);
        if (ids.length) await mudarKits(ids, "pendente");
      }
      definirSelecionadas([]);
      await Promise.all([buscar(), recarregarAbas()]);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirAplicandoLote(false);
    }
  }

  /** A celula de "montado por": o nome de quem montou, ou o link de montar. */
  function celulaMontado(k) {
    if (k.montado_por) return <span title={`Montado por ${k.montado_por}`}>{k.montado_por}</span>;
    if (k.desistiu_em) return <span className="celula--vazia">—</span>;
    const ocupado = marcando.includes(k.crianca_id);
    return (
      <button type="button" className="link-conferir" disabled={ocupado} onClick={() => montar(k)}>
        {ocupado ? "Marcando..." : "Marcar como montado"}
        {!ocupado && <ChevronDireita t={12} />}
      </button>
    );
  }

  /** A celula de "conferido por": o nome de quem conferiu, ou o botao. Kit
   *  ainda nao montado nao tem o que conferir. */
  function celulaConferido(k) {
    if (k.conferido_por) return <span title={`Conferido por ${k.conferido_por}`}>{k.conferido_por}</span>;
    if (k.status !== "montado" || k.desistiu_em) return <span className="celula--vazia">—</span>;
    /* Um link, e nao o <Button>: o botao de 32px esticava a linha e nao
       cabia na coluna fixa. Este tem a altura do texto, e a linha da tabela
       continua com a mesma regua das outras. */
    const ocupado = conferindo.includes(k.crianca_id);
    return (
      <button
        type="button"
        className="link-conferir"
        disabled={ocupado}
        onClick={() => conferir(k)}
      >
        {ocupado ? "Conferindo..." : "Marcar como conferido"}
        {!ocupado && <ChevronDireita t={12} />}
      </button>
    );
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
            Uma criança, um kit. Cada marca vale na hora; riscada é quem desistiu.
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
        {/* No lugar do antigo filtro: em vez de esconder linhas, escolhe as
            linhas de uma vez, e a acao sai da barra de baixo. */}
        <Selecao
          value=""
          onChange={(e) => selecionar(e.target.value)}
          aria-label="Selecionar linhas"
        >
          <option value="" disabled>
            Selecionar...
          </option>
          <option value="todas">Todas</option>
          <option value="a_montar">As a montar</option>
          <option value="sem_conferencia">As montadas sem conferência</option>
          <option value="nenhuma">Nenhuma</option>
        </Selecao>
        <span className="etiqueta etiqueta--ok">{montados} montados</span>
        <span className="etiqueta etiqueta--espera">{pendentes} a montar</span>
        {abaDaVez?.dia_evento && (
          <EtiquetaDia data={abaDaVez.dia_evento} descricao={abaDaVez.dia_evento_descricao} />
        )}

        <div className="barra-acoes__ponta">
          {/* So dentro de uma instituicao: a conta e da compra de UMA escola. */}
          {abaAtiva !== TODAS && (
            <Button size="sm" variant="ghost" onClick={abrirEstatisticas}>
              Ver estatísticas
            </Button>
          )}
        </div>
      </div>

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
              <col style={{ width: estreita ? 44 : 48 }} />
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
              {!estreita && <col style={{ width: 96 }} />}
              {!estreita && <col style={{ width: 180 }} />}
              {!estreita && <col style={{ width: 190 }} />}
            </colgroup>
            <thead>
              <tr>
                <th className="tabela__marcar">
                  <input
                    type="checkbox"
                    checked={todasSelecionadas}
                    disabled={selecionaveis.length === 0}
                    onChange={() => selecionar(todasSelecionadas ? "nenhuma" : "todas")}
                    aria-label="Selecionar todas as linhas"
                  />
                </th>
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
                  className={[
                    k.desistiu_em ? "tabela__linha--desistiu" : "",
                    selecionadas.includes(k.crianca_id) ? "tabela__linha--selecionada" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  title={k.desistiu_em ? `${k.crianca_nome} desistiu do evento` : undefined}
                >
                  <td className="tabela__marcar">
                    <input
                      type="checkbox"
                      checked={selecionadas.includes(k.crianca_id)}
                      /* Desistente nao se seleciona: o kit dela nao se marca. */
                      disabled={Boolean(k.desistiu_em)}
                      onChange={() => alternarSelecao(k.crianca_id)}
                      aria-label={`Selecionar ${k.crianca_nome}`}
                      title={k.desistiu_em ? "Criança desistente: o kit não se marca" : undefined}
                    />
                  </td>
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
                        {k.checkin_em && (
                          <>
                            <br />
                            <EtiquetaCheckin quando={k.checkin_em} />
                          </>
                        )}
                        {/* Sem colunas no celular: montagem e conferencia
                            descem para baixo do nome. */}
                        {!k.desistiu_em && (
                          <>
                            <br />
                            {k.montado_por ? (
                              <span className="campo__dica">Montado por {k.montado_por}</span>
                            ) : (
                              celulaMontado(k)
                            )}
                          </>
                        )}
                        {k.status === "montado" && !k.desistiu_em && (
                          <>
                            <br />
                            {k.conferido_por ? (
                              <span className="campo__dica">Conferido por {k.conferido_por}</span>
                            ) : (
                              celulaConferido(k)
                            )}
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
                      <EtiquetaCheckin quando={k.checkin_em} />
                    </td>
                  )}
                  {!estreita && <td className="tabela__status">{celulaMontado(k)}</td>}
                  {!estreita && <td className="tabela__status">{celulaConferido(k)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selecionadas.length > 0 && (
        <div className="lote">
          <span className="lote__texto">
            {selecionadas.length} {selecionadas.length === 1 ? "selecionada" : "selecionadas"}
          </span>
          {acoesDoLote.length > 0 ? (
            <Selecao
              value=""
              disabled={aplicandoLote}
              onChange={(e) => aplicarLote(e.target.value)}
              aria-label="O que fazer com as selecionadas"
            >
              <option value="" disabled>
                {aplicandoLote ? "Aplicando..." : "Marcar como..."}
              </option>
              {acoesDoLote.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.rotulo}
                </option>
              ))}
            </Selecao>
          ) : (
            /* Diz por que nao ha acao, em vez de deixar a barra muda. */
            <span className="lote__aviso">
              Nenhuma ação vale para todas: a seleção mistura kits em situações diferentes.
            </span>
          )}
          <Button size="sm" variant="ghost" onClick={() => definirSelecionadas([])}>
            Desmarcar
          </Button>
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
function EtiquetaCheckin({ quando }) {
  return quando ? (
    <span className="etiqueta etiqueta--ok" title={`Check-in em ${formatarDataHora(quando)}`}>
      Chegou
    </span>
  ) : (
    <span className="celula--vazia">—</span>
  );
}
