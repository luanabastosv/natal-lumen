import { useState } from "react";
import { createPortal } from "react-dom";
import Button from "../core/Button.jsx";
import { Selecao } from "../core/Campo.jsx";
import Modal from "../feedback/Modal.jsx";
import Mensagem from "../feedback/Mensagem.jsx";

/** A janela que configura a impressao de uma lista, e imprime.
 *
 * Existe uma so para o sistema inteiro, e cada tela entrega a SUGESTAO dela —
 * quais colunas, deitado ou em pe, agrupado por que, em que ordem. A sugestao
 * e o ponto: quem vai imprimir a lista de kits nao deveria ter de montar do
 * zero o formato que a equipe de estrutura usa toda semana. As opcoes existem
 * para o caso que foge, nao para o caso comum.
 *
 * Imprime pelo NAVEGADOR (`window.print()`), e nao por PDF gerado no servidor:
 * o dialogo do navegador ja resolve impressora, papel e margem, funciona sem
 * internet no dia do evento, e nao acrescenta dependencia nenhuma ao backend.
 * O que este arquivo faz e montar o HTML certo e dizer o tamanho da folha.
 *
 * `colunas`: [{ id, rotulo, valor: (item) => texto, riscar?: (item) => bool }]
 *   `riscar` risca a celula daquela linha — o nome de quem desistiu, como a
 *   tela ja faz.
 * `sugestao`: { colunas: [id], orientacao, agruparPor, ordenarPor, caixinha }
 * `agrupamentos` e `ordenacoes`: [{ id, rotulo, de: (item) => valor }]
 * `buscarTudo`: devolve TODOS os itens do filtro atual — a tela mostra uma
 *   pagina, mas o papel tem de sair com a lista inteira.
 */
export default function ImprimirLista({
  titulo,
  subtitulo,
  colunas,
  sugestao,
  agrupamentos = [],
  ordenacoes = [],
  buscarTudo,
  aoFechar,
}) {
  const [config, definirConfig] = useState({
    colunas: sugestao.colunas,
    orientacao: sugestao.orientacao ?? "retrato",
    agruparPor: sugestao.agruparPor ?? "",
    ordenarPor: sugestao.ordenarPor ?? "",
    caixinha: sugestao.caixinha ?? false,
  });
  const [preparando, definirPreparando] = useState(false);
  const [erro, definirErro] = useState("");
  const [paraImprimir, definirParaImprimir] = useState(null);

  function mudar(campo, valor) {
    definirConfig((c) => ({ ...c, [campo]: valor }));
  }

  function alternarColuna(id) {
    definirConfig((c) => ({
      ...c,
      colunas: c.colunas.includes(id)
        ? c.colunas.filter((x) => x !== id)
        : // Mantem a ordem original das colunas, e nao a ordem dos cliques: a
          // pessoa marca "idade" depois de "sexo" e espera ver o cabecalho do
          // jeito que a tela mostra.
          colunas.filter((col) => c.colunas.includes(col.id) || col.id === id).map((col) => col.id),
    }));
  }

  async function imprimir() {
    definirErro("");
    definirPreparando(true);
    try {
      const itens = await buscarTudo();
      const ordenacao = ordenacoes.find((o) => o.id === config.ordenarPor);
      const agrupamento = agrupamentos.find((a) => a.id === config.agruparPor);

      const ordenados = ordenacao
        ? [...itens].sort((a, b) => {
            const x = ordenacao.de(a);
            const y = ordenacao.de(b);
            // localeCompare com numeric: "EA2" vem antes de "EA10", que e o que
            // qualquer pessoa espera de um codigo.
            return String(x ?? "").localeCompare(String(y ?? ""), "pt-BR", { numeric: true });
          })
        : itens;

      const grupos = agrupamento
        ? [
            ...ordenados.reduce((mapa, item) => {
              const chave = agrupamento.de(item) ?? "Sem definição";
              if (!mapa.has(chave)) mapa.set(chave, []);
              mapa.get(chave).push(item);
              return mapa;
            }, new Map()),
          ].sort((a, b) => a[0].localeCompare(b[0], "pt-BR"))
        : [[null, ordenados]];

      definirParaImprimir({ grupos, quando: new Date() });

      // Espera o navegador pintar a area de impressao antes de abrir o
      // dialogo: chamar print() no mesmo quadro imprimiria a pagina sem ela.
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          window.print();
          definirPreparando(false);
        }),
      );
    } catch (e) {
      definirErro(e.message);
      definirPreparando(false);
    }
  }

  const escolhidas = colunas.filter((c) => config.colunas.includes(c.id));

  return (
    <>
      <Modal titulo={`Imprimir ${titulo.toLowerCase()}`} rotulo="Lista:" aoFechar={aoFechar}>
        <Mensagem tipo="erro">{erro}</Mensagem>

        <p className="campo__dica" style={{ marginTop: 0 }}>
          A sugestão abaixo já é o formato que esta lista costuma usar. Mude só se
          precisar de algo diferente desta vez.
        </p>

        <div className="linha-campos">
          <Selecao
            rotulo="Papel"
            value={config.orientacao}
            onChange={(e) => mudar("orientacao", e.target.value)}
          >
            <option value="retrato">Em pé (retrato)</option>
            <option value="paisagem">Deitado (paisagem)</option>
          </Selecao>

          {agrupamentos.length > 0 && (
            <Selecao
              rotulo="Uma lista para cada"
              value={config.agruparPor}
              onChange={(e) => mudar("agruparPor", e.target.value)}
              dica="Cada grupo começa numa folha nova."
            >
              <option value="">Tudo numa lista só</option>
              {agrupamentos.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.rotulo}
                </option>
              ))}
            </Selecao>
          )}

          {ordenacoes.length > 0 && (
            <Selecao
              rotulo="Organizar por"
              value={config.ordenarPor}
              onChange={(e) => mudar("ordenarPor", e.target.value)}
            >
              <option value="">Como está na tela</option>
              {ordenacoes.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.rotulo}
                </option>
              ))}
            </Selecao>
          )}
        </div>

        <fieldset className="campo" style={{ border: "none", padding: 0, margin: 0 }}>
          <legend className="campo__rotulo">Colunas</legend>
          <div className="marcaveis">
            {colunas.map((c) => (
              <label key={c.id} className="marcavel">
                <input
                  type="checkbox"
                  checked={config.colunas.includes(c.id)}
                  onChange={() => alternarColuna(c.id)}
                />
                {c.rotulo}
              </label>
            ))}
          </div>
        </fieldset>

        <label className="marcavel" style={{ marginTop: "var(--space-3)" }}>
          <input
            type="checkbox"
            checked={config.caixinha}
            onChange={(e) => mudar("caixinha", e.target.checked)}
          />
          Coluna vazia para marcar à mão no papel
        </label>

        <div className="barra-acoes barra-acoes--fim">
          <Button onClick={imprimir} carregando={preparando} disabled={escolhidas.length === 0}>
            Imprimir
          </Button>
          <Button variant="ghost" onClick={aoFechar} disabled={preparando}>
            Cancelar
          </Button>
        </div>
      </Modal>

      {/* A area que vai para o papel sai do #root por PORTAL, e vira filha
          direta do <body>.

          Nao e capricho: ela morava dentro da arvore da aplicacao, e a tela era
          escondida com `visibility: hidden` — que esconde mas NAO tira do
          fluxo. A pagina inteira continuava ocupando altura, e saiam duas
          folhas em branco no fim de toda impressao. Fora do #root, o CSS pode
          simplesmente `display: none` em tudo o que nao e o papel, e o que nao
          imprime deixa de ocupar folha.

          Fica fora do Modal pelo mesmo motivo de sempre: o modal e
          `position: fixed`, e o navegador imprime so o primeiro pedaco de um
          elemento fixo. */}
      {paraImprimir &&
        createPortal(
          <div className="impressao">
          {/* A regra da folha vai aqui, montada com a orientacao escolhida:
              `@page` nomeada nao e respeitada de forma confiavel, e sem isto o
              papel saia Letter retrato por mais que o CSS dissesse paisagem. */}
          <style>{`@page { size: A4 ${
            config.orientacao === "paisagem" ? "landscape" : "portrait"
          }; margin: ${config.orientacao === "paisagem" ? "10mm" : "12mm"}; }`}</style>
          {paraImprimir.grupos.map(([grupo, itens], indice) => (
            <section key={grupo ?? indice} className="impressao__folha">
              <header className="impressao__topo">
                <h1>{titulo}</h1>
                <p>
                  {grupo ? <strong>{grupo}</strong> : null}
                  {grupo && subtitulo ? " · " : null}
                  {subtitulo}
                  {" · "}
                  {itens.length} {itens.length === 1 ? "linha" : "linhas"}
                </p>
              </header>

              <table className="impressao__tabela">
                <thead>
                  <tr>
                    {config.caixinha && <th className="impressao__caixa">✓</th>}
                    {escolhidas.map((c) => (
                      <th key={c.id}>{c.rotulo}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {itens.map((item, i) => (
                    <tr key={i}>
                      {config.caixinha && (
                        <td className="impressao__caixa">
                          <span className="impressao__quadro" />
                        </td>
                      )}
                      {escolhidas.map((c) => (
                        <td
                          key={c.id}
                          className={c.riscar?.(item) ? "impressao__riscado" : undefined}
                        >
                          {c.valor(item)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>

              <footer className="impressao__rodape">
                Natal Lumen · impresso em{" "}
                {paraImprimir.quando.toLocaleDateString("pt-BR")} às{" "}
                {paraImprimir.quando.toLocaleTimeString("pt-BR", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </footer>
            </section>
          ))}
          </div>,
          document.body,
        )}
    </>
  );
}
