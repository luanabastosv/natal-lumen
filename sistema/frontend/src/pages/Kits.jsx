import { useCallback, useEffect, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import { Selecao } from "../components/core/Campo.jsx";
import FaixaDeAbas from "../components/core/FaixaDeAbas.jsx";
import Button from "../components/core/Button.jsx";
import ImprimirLista from "../components/dados/ImprimirLista.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";
import { instituicoesDosKits, listarKits, mudarKits } from "../services/logistica.js";

const TODAS = "todas";

/* A tela toda parte das criancas, e nao dos kits: a crianca existe desde a
   importacao e o kit so ganha registro quando alguem mexe nele. Uma crianca
   cadastrada hoje aparece aqui hoje, pendente — e por isso a lista nunca
   diverge da de criancas. */
export default function Kits() {
  const { edicaoAtiva } = useSessao();

  const [situacao, definirSituacao] = useState("");
  const [dados, definirDados] = useState({ itens: [], total: 0, resumo: {} });
  const [abas, definirAbas] = useState([]);
  const [abaAtiva, definirAbaAtiva] = useState(TODAS);
  const [marcando, definirMarcando] = useState([]);
  const [imprimindo, definirImprimindo] = useState(false);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");

  const estreita = useTelaEstreita();

  const buscar = useCallback(async () => {
    try {
      definirDados(
        await listarKits({
          edicao_id: edicaoAtiva,
          situacao,
          instituicao_id: abaAtiva === TODAS ? "" : abaAtiva,
        }),
      );
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoAtiva, situacao, abaAtiva]);

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
  }, [edicaoAtiva, situacao, abaAtiva, buscar]);

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

  /** Marca ou desmarca UM kit, na hora do clique.
   *
   *  A montagem acontece com a caixa na mao: a pessoa monta, marca, pega a
   *  proxima. Um "salvar" no fim da lista obrigaria a lembrar o que ja tinha
   *  feito, e um lote perdido no meio significaria remontar a conferencia
   *  inteira de cabeca.
   */
  async function alternarKit(item) {
    const alvo = item.status === "montado" ? "pendente" : "montado";
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
          pendente: (atual.resumo.pendente ?? 0) + (alvo === "montado" ? -1 : 1),
        },
      }));
      recarregarAbas();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirMarcando((a) => a.filter((x) => x !== item.crianca_id));
    }
  }

  /* O papel sai com a lista INTEIRA do filtro, e nao com a pagina que esta na
     tela: a equipe leva a folha para a mesa de montagem, e uma lista cortada na
     centesima crianca faria faltar caixa sem ninguem entender por que. */
  async function todosOsItens() {
    const tudo = await listarKits({
      edicao_id: edicaoAtiva,
      situacao,
      instituicao_id: abaAtiva === TODAS ? "" : abaAtiva,
      por_pagina: 2000,
    });
    return tudo.itens;
  }

  const montados = dados.resumo.montado ?? 0;
  const pendentes = dados.resumo.pendente ?? 0;

  return (
    <div>
      <div className="pagina__eyebrow">Estrutura</div>
      <h1 className="pagina__titulo">Kits</h1>
      <Rabisco className="pagina__onda" />
      <p className="pagina__lede">
        Uma criança, um kit. Marque a caixinha conforme for montando — cada marca
        vale na hora, não precisa salvar no fim. Quem desistiu do evento aparece
        riscado: não monte kit para essas.
      </p>

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
            {abas.reduce((s, a) => s + a.total, 0)} crianças
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
            {/* O numero que se procura e o que FALTA montar, nao o que ja foi:
                a pilha de caixas ainda por fazer e o trabalho de hoje. */}
            <span className="aba__contagem">
              {a.total - a.montados} de {a.total} a montar
            </span>
          </button>
        ))}
      </FaixaDeAbas>

      <div className="barra-acoes">
        <Selecao value={situacao} onChange={(e) => definirSituacao(e.target.value)}>
          <option value="">Todos</option>
          <option value="pendente">A montar</option>
          <option value="montado">Montados</option>
        </Selecao>
        <span className="etiqueta etiqueta--ok">{montados} montados</span>
        <span className="etiqueta etiqueta--espera">{pendentes} a montar</span>

        <div className="barra-acoes__ponta">
          <Button size="sm" variant="secondary" onClick={() => definirImprimindo(true)}>
            Imprimir lista
          </Button>
        </div>
      </div>

      {imprimindo && (
        <ImprimirLista
          titulo="Kits"
          subtitulo="Montagem"
          aoFechar={() => definirImprimindo(false)}
          buscarTudo={todosOsItens}
          colunas={[
            { id: "codigo", rotulo: "Código", valor: (k) => k.crianca_codigo },
            { id: "nome", rotulo: "Criança", valor: (k) => k.crianca_nome },
            { id: "idade", rotulo: "Idade", valor: (k) => k.idade },
            { id: "sexo", rotulo: "Sexo", valor: (k) => k.sexo },
            { id: "instituicao", rotulo: "Instituição", valor: (k) => k.instituicao },
            {
              id: "situacao",
              rotulo: "No sistema",
              valor: (k) =>
                k.desistiu_em ? "DESISTIU" : k.status === "montado" ? "montado" : "a montar",
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
          corpo={
            situacao
              ? "Nenhuma criança com esse filtro."
              : "Importe as listas das instituições para os kits aparecerem aqui."
          }
        />
      ) : (
        <div className="tabela-rolagem">
          <table className={`tabela ${estreita ? "tabela--compacta" : ""}`}>
            <thead>
              <tr>
                <th className="tabela__marcar">Montado</th>
                <th>Código</th>
                <th>Criança</th>
                {!estreita && <th>Idade</th>}
                {!estreita && <th>Sexo</th>}
                {/* Dentro de uma aba de instituicao a coluna seria a mesma
                    palavra em todas as linhas — a aba ja diz qual escola e. */}
                {!estreita && abaAtiva === TODAS && <th>Instituição</th>}
              </tr>
            </thead>
            <tbody>
              {dados.itens.map((k) => (
                <tr
                  key={k.crianca_id}
                  className={k.desistiu_em ? "tabela__linha--desistiu" : ""}
                  title={k.desistiu_em ? `${k.crianca_nome} desistiu do evento` : undefined}
                >
                  <td className="tabela__marcar">
                    <input
                      type="checkbox"
                      checked={k.status === "montado"}
                      disabled={marcando.includes(k.crianca_id)}
                      onChange={() => alternarKit(k)}
                      aria-label={`Kit de ${k.crianca_nome} montado`}
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
                      </>
                    )}
                  </td>
                  {!estreita && <td>{k.idade}</td>}
                  {!estreita && <td>{k.sexo}</td>}
                  {!estreita && abaAtiva === TODAS && <td>{k.instituicao}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
