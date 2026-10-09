import { useEffect, useMemo, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Selecao } from "../components/core/Campo.jsx";
import EtiquetaDesistente from "../components/core/EtiquetaDesistente.jsx";
import FaixaDeAbas from "../components/core/FaixaDeAbas.jsx";
import Rabisco from "../components/core/Rabisco.jsx";
import BotaoIcone from "../components/core/BotaoIcone.jsx";
import { Cuidado, Imprimir, Olho } from "../components/core/icones.jsx";
import FichaCrianca from "../components/dados/FichaCrianca.jsx";
import FichaSimples from "../components/dados/FichaSimples.jsx";
import ImprimirLista from "../components/dados/ImprimirLista.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";
import { listarCuidados } from "../services/cuidados.js";
import { formatarData, rotuloDia } from "../utils/dinheiro.js";
import { tomDoDia } from "../utils/dias.js";

const SEM_DIA = "sem-dia";

/* As listas de dentro do dia. Cada uma e uma lista de trabalho diferente: a
   de necessidade especial vai para quem acompanha, a de alergia para a
   cozinha. A observacao aparece nas duas. "So observacao" pega quem nao cai
   em nenhuma das duas, para nenhuma crianca sumir. */
const NECESSIDADE = { campo: "necessidade_especial", rotulo: "Necessidade especial" };
const RESTRICAO = { campo: "restricao_alimentar", rotulo: "Alergia / restrição" };

const VISOES = [
  // Todas as criancas do dia, com as duas colunas: o panorama, antes de
  // separar as listas de trabalho.
  { id: "todos", rotulo: "Todos", colunas: [NECESSIDADE, RESTRICAO], de: () => true },
  {
    id: "necessidade",
    rotulo: "Necessidade especial",
    colunas: [NECESSIDADE],
    de: (c) => Boolean(c.necessidade_especial),
  },
  {
    id: "restricao",
    rotulo: "Alergia / restrição",
    colunas: [RESTRICAO],
    de: (c) => Boolean(c.restricao_alimentar),
  },
  {
    id: "observacao",
    rotulo: "Só observação",
    colunas: [],
    de: (c) => Boolean(c.observacao) && !c.necessidade_especial && !c.restricao_alimentar,
  },
];

/** Cuidados especiais: as criancas cuja autorizacao avisa alguma coisa.
 *
 * Uma aba por dia do evento, porque e assim que a lista e usada: na vespera
 * de cada dia a coordenacao separa quem precisa de acompanhamento, de comida
 * diferente, de atencao a uma alergia. Dentro do dia, uma linha por crianca,
 * com as tres respostas lado a lado.
 *
 * So a coordenacao geral do evento e a administracao geral — e dado de saude
 * de crianca, todo junto. Quem recebe a crianca no dia ve o aviso dela na
 * propria lista (o asterisco).
 */
export default function Cuidados() {
  const { edicaoAtiva } = useSessao();
  const estreita = useTelaEstreita();

  const [linhas, definirLinhas] = useState(null);
  const [erro, definirErro] = useState("");
  const [abaAtiva, definirAbaAtiva] = useState(null);
  const [visaoAtiva, definirVisaoAtiva] = useState(VISOES[0].id);
  const [fichaAberta, definirFichaAberta] = useState(null);
  // A janela do celular com os cuidados de uma crianca.
  const [vendo, definirVendo] = useState(null);
  const [imprimindo, definirImprimindo] = useState(false);

  useEffect(() => {
    if (!edicaoAtiva) return undefined;
    let vivo = true;
    listarCuidados(edicaoAtiva)
      .then((r) => vivo && definirLinhas(r))
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, [edicaoAtiva]);

  // Os dias que tem alguma crianca com cuidado, em ordem de data; quem ainda
  // nao tem dia vai por ultimo.
  const dias = useMemo(() => {
    const porDia = new Map();
    for (const l of linhas ?? []) {
      const chave = l.dia_evento_id ?? SEM_DIA;
      if (!porDia.has(chave)) {
        porDia.set(chave, {
          chave,
          data: l.dia_evento,
          descricao: l.dia_evento_descricao,
          criancas: [],
        });
      }
      porDia.get(chave).criancas.push(l);
    }
    return [...porDia.values()].sort((a, b) =>
      a.chave === SEM_DIA ? 1 : b.chave === SEM_DIA ? -1 : a.data.localeCompare(b.data),
    );
  }, [linhas]);

  const dia = dias.find((d) => d.chave === abaAtiva) ?? dias[0];
  const visao = VISOES.find((v) => v.id === visaoAtiva) ?? VISOES[0];
  const criancas = useMemo(
    () =>
      (dia?.criancas ?? []).filter(visao.de).sort(
        (a, b) =>
          a.instituicao.localeCompare(b.instituicao, "pt-BR") ||
          a.codigo.localeCompare(b.codigo, "pt-BR", { numeric: true }),
      ),
    [dia, visao],
  );

  const nomeDoDia = (d) => (d.chave === SEM_DIA ? "Sem dia definido" : rotuloDia(d.data, d.descricao));

  /** Cada resposta "Sim" com o que o monitor escreveu; "—" quando foi "Nao". */
  function celula(texto) {
    return texto ? (
      <span className="cuidados__resposta">{texto}</span>
    ) : (
      <span className="celula--vazia">—</span>
    );
  }

  return (
    <div>
      <div className="pagina__cabecalho">
        <div className="pagina__texto">
          <div className="pagina__eyebrow">Coordenação</div>
          <h1 className="pagina__titulo">Cuidados especiais</h1>
          <Rabisco className="pagina__onda" />
          <p className="pagina__lede">
            Necessidade especial, alergia ou restrição alimentar e observações, por dia do evento.
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
            disabled={!linhas?.length}
          />
        </div>
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {imprimindo && (
        <ImprimirLista
          titulo={visao.id === "todos" ? "Cuidados especiais" : visao.rotulo}
          subtitulo={dia ? nomeDoDia(dia) : "Cuidados especiais"}
          aoFechar={() => definirImprimindo(false)}
          // O papel sai com a lista que esta na tela: o dia e a visao abertos.
          buscarTudo={async () => criancas}
          colunas={[
            { id: "codigo", rotulo: "Código", valor: (c) => c.codigo },
            {
              id: "nome",
              rotulo: "Criança",
              valor: (c) => c.nome,
              riscar: (c) => Boolean(c.desistiu_em),
            },
            { id: "idade", rotulo: "Idade", valor: (c) => c.idade },
            { id: "instituicao", rotulo: "Instituição", valor: (c) => c.instituicao },
            {
              id: "necessidade",
              rotulo: "Necessidade especial",
              valor: (c) => c.necessidade_especial ?? "",
            },
            {
              id: "restricao",
              rotulo: "Alergia / restrição",
              valor: (c) => c.restricao_alimentar ?? "",
            },
            { id: "observacao", rotulo: "Observação", valor: (c) => c.observacao ?? "" },
          ]}
          /* Uma folha por dia, deitada: as tres respostas sao texto e pedem
             largura. Quem prepara o dia leva a folha dele. */
          sugestao={{
            colunas: [
              "codigo",
              "nome",
              "idade",
              "instituicao",
              ...(visao.colunas.includes(NECESSIDADE) ? ["necessidade"] : []),
              ...(visao.colunas.includes(RESTRICAO) ? ["restricao"] : []),
              "observacao",
            ],
            orientacao: "paisagem",
            agruparPor: "",
            ordenarPor: "instituicao",
          }}
          agrupamentos={[
            {
              id: "dia",
              rotulo: "Dia do evento",
              de: (c) =>
                c.dia_evento
                  ? `${rotuloDia(c.dia_evento, c.dia_evento_descricao)} · ${formatarData(c.dia_evento)}`
                  : "Sem dia definido",
            },
            { id: "instituicao", rotulo: "Instituição", de: (c) => c.instituicao },
          ]}
          ordenacoes={[
            { id: "instituicao", rotulo: "Instituição", de: (c) => `${c.instituicao} ${c.codigo}` },
            { id: "codigo", rotulo: "Código", de: (c) => c.codigo },
            { id: "nome", rotulo: "Nome", de: (c) => c.nome },
          ]}
        />
      )}

      {linhas === null ? (
        erro ? null : <Carregando tela>Buscando as autorizações...</Carregando>
      ) : linhas.length === 0 ? (
        <EmptyState
          titulo="Nenhum cuidado especial avisado"
          corpo="Quando uma autorização responder Sim a necessidade especial, alergia ou observação, a criança aparece aqui, no dia dela."
        />
      ) : (
        <>
          <FaixaDeAbas reiniciarEm={edicaoAtiva}>
            {dias.map((d) => (
              <button
                key={d.chave}
                type="button"
                role="tab"
                aria-selected={d.chave === dia?.chave}
                className={`aba ${d.chave === dia?.chave ? "aba--ativa" : ""}`}
                onClick={() => definirAbaAtiva(d.chave)}
              >
                <span>
                  {nomeDoDia(d)}
                  {d.chave !== SEM_DIA && (
                    <span className={`aba__ponto dia--${tomDoDia(d.descricao)}`} />
                  )}
                </span>
                <span className="aba__contagem">
                  {d.criancas.length} {d.criancas.length === 1 ? "criança" : "crianças"}
                </span>
              </button>
            ))}
          </FaixaDeAbas>

          {/* Dentro do dia, uma lista por tipo de cuidado: o seletor diz qual,
              com quantas criancas cada uma tem. */}
          <div className="barra-acoes">
            <Selecao
              aria-label="Tipo de cuidado"
              value={visao.id}
              onChange={(e) => definirVisaoAtiva(e.target.value)}
            >
              {VISOES.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.rotulo} ({(dia?.criancas ?? []).filter(v.de).length})
                </option>
              ))}
            </Selecao>
          </div>

          <div className="tabela-rolagem">
            {/* No computador as colunas sao SEMPRE as mesmas, com largura
                fixa: trocar o tipo no seletor so filtra as linhas, e nada muda
                de lugar. A coluna do tipo que nao e o escolhido fica em
                branco ("—") para quem nao tem aquele cuidado. */}
            <table
              className={`tabela tabela--densa ${
                estreita ? "tabela--compacta" : "tabela--ancorada"
              }`}
            >
              {!estreita && (
                <colgroup>
                  <col style={{ width: 92 }} />
                  <col style={{ width: "20%" }} />
                  <col style={{ width: "15%" }} />
                  <col style={{ width: "21%" }} />
                  <col style={{ width: "21%" }} />
                  <col />
                </colgroup>
              )}
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Criança</th>
                  {/* No celular a linha fica com codigo, nome e o olho: as
                      respostas sao texto comprido e quebravam a tabela. Elas
                      abrem numa janela, a um toque. */}
                  {!estreita && (
                    <>
                      <th>Instituição</th>
                      <th>{NECESSIDADE.rotulo}</th>
                      <th>{RESTRICAO.rotulo}</th>
                      <th>Observação</th>
                    </>
                  )}
                  {estreita && <th className="tabela__acoes" />}
                </tr>
              </thead>
              <tbody>
                {criancas.map((c) => (
                  <tr key={c.crianca_id} className={c.desistiu_em ? "tabela__linha--desistiu" : ""}>
                    <td>{c.codigo}</td>
                    <td>
                      {/* O nome abre a ficha inteira da crianca, com a caixa
                          de cuidados e o resto do que se sabe dela. */}
                      <button
                        type="button"
                        className="cuidados__nome"
                        onClick={() => definirFichaAberta(c.crianca_id)}
                      >
                        <Cuidado t={13} />
                        {c.nome}
                      </button>
                      <span className="campo__dica">{c.idade} anos</span>
                      {c.desistiu_em && <EtiquetaDesistente />}
                    </td>
                    {!estreita && (
                      <>
                        <td title={c.instituicao}>{c.instituicao}</td>
                        <td>{celula(c.necessidade_especial)}</td>
                        <td>{celula(c.restricao_alimentar)}</td>
                        <td>{celula(c.observacao)}</td>
                      </>
                    )}
                    {estreita && (
                      <td className="tabela__acoes">
                        <BotaoIcone titulo={`Ver os cuidados de ${c.nome}`} onClick={() => definirVendo(c)}>
                          <Olho t={20} />
                        </BotaoIcone>
                      </td>
                    )}
                  </tr>
                ))}
                {criancas.length === 0 && (
                  <tr>
                    <td colSpan={estreita ? 3 : 6} className="campo__dica">
                      {visao.id === "todos"
                        ? "Nenhuma criança com cuidados neste dia."
                        : `Nenhuma criança com ${visao.rotulo.toLowerCase()} neste dia.`}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* No celular: o que a linha escondeu, numa janela — os cuidados da
          crianca, e o caminho para a ficha completa. */}
      {vendo && (
        <FichaSimples
          rotulo={`${vendo.codigo} · ${vendo.idade} anos`}
          titulo={vendo.nome}
          aoFechar={() => definirVendo(null)}
          campos={[
            { rotulo: "Instituição", valor: vendo.instituicao, largo: true },
            { rotulo: "Necessidade especial", valor: vendo.necessidade_especial, largo: true },
            { rotulo: "Alergia / restrição", valor: vendo.restricao_alimentar, largo: true },
            { rotulo: "Observação", valor: vendo.observacao, largo: true },
          ]}
          rodape={
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                definirFichaAberta(vendo.crianca_id);
                definirVendo(null);
              }}
            >
              Ver ficha completa
            </Button>
          }
        />
      )}

      {fichaAberta && (
        <FichaCrianca criancaId={fichaAberta} aoFechar={() => definirFichaAberta(null)} />
      )}
    </div>
  );
}
