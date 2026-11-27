import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import { Atencao, Baixar, Conversa } from "../components/core/icones.jsx";
import EnvioDoLote from "../components/dados/EnvioDoLote.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";
import {
  baixarAgradecimentosDoLote,
  detalharLote,
  gravarLote,
  instituicoesComVagas,
  lerPlanilhaDoLote,
  listarLotes,
  vagasDoLote,
} from "../services/lotes.js";
import { dinheiro, formatarDataHora } from "../utils/dinheiro.js";
import "./ApadrinharEmLote.css";

/* Apadrinhamento em lote: um grupo que juntou o dinheiro e apadrinhou junto.
 *
 * Tres etapas, como a importacao de listas: montar (grupo, planilha,
 * comprovante, instituicoes), conferir (uma crianca por pessoa, sugerida e
 * trocavel) e pronto (o ZIP dos agradecimentos). Nada e gravado antes do
 * "Confirmar". So a administracao geral chega aqui — a rota e o backend
 * conferem, cada um por si. */

const FORMAS = ["Pix", "Dinheiro"];

function hoje() {
  const d = new Date();
  const dois = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${dois(d.getMonth() + 1)}-${dois(d.getDate())}`;
}

function novaChave() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

// A vaga e a crianca num tipo: "12:cesta".
const chaveDaVaga = (criancaId, tipo) => `${criancaId}:${tipo}`;

/** Todas as vagas, na ordem da sugestao: primeiro as cestas, depois as festas.
 *  Assim cada pessoa ganha uma crianca diferente enquanto houver, e a festa
 *  so entra quando as cestas das instituicoes escolhidas acabam. */
function listarVagas(criancas) {
  const cestas = criancas.filter((c) => c.cesta_livre).map((c) => ({ ...c, tipo: "cesta" }));
  const festas = criancas.filter((c) => c.festa_livre).map((c) => ({ ...c, tipo: "festa" }));
  return [...cestas, ...festas].map((v) => ({ ...v, chave: chaveDaVaga(v.id, v.tipo) }));
}

function rotuloDaVaga(v) {
  return `${v.codigo} · ${v.nome} · ${v.idade} anos · ${v.instituicao} · ${v.tipo}`;
}

export default function ApadrinharEmLote() {
  const { edicaoAtiva, edicao } = useSessao();
  const navegar = useNavigate();
  const notificar = useNotificar();
  const estreita = useTelaEstreita();

  const [etapa, definirEtapa] = useState("montar");
  const [erro, definirErro] = useState("");

  // Etapa 1
  const [nomeGrupo, definirNomeGrupo] = useState("");
  const [planilha, definirPlanilha] = useState(null);
  const [comprovante, definirComprovante] = useState(null);
  const [data, definirData] = useState(hoje);
  const [forma, definirForma] = useState(FORMAS[0]);
  const [escolhidas, definirEscolhidas] = useState([]);
  const [resumo, definirResumo] = useState(null);
  const [lendo, definirLendo] = useState(false);

  // Etapa 2
  const [linhas, definirLinhas] = useState([]);
  const [vagas, definirVagas] = useState([]);
  // linha da planilha -> chave da vaga ("" = sem crianca)
  const [escolha, definirEscolha] = useState({});
  const [chaveEnvio, definirChaveEnvio] = useState(novaChave);
  const [gravando, definirGravando] = useState(false);

  // Etapa 3
  const [lote, definirLote] = useState(null);
  const [lotes, definirLotes] = useState([]);
  const [baixando, definirBaixando] = useState(null);
  const [abrindo, definirAbrindo] = useState(null);

  const carregarResumo = useCallback(async () => {
    if (!edicaoAtiva) return;
    try {
      const [r, l] = await Promise.all([
        instituicoesComVagas(edicaoAtiva),
        listarLotes(edicaoAtiva),
      ]);
      definirResumo(r);
      definirLotes(l);
    } catch (e) {
      definirErro(e.message);
    }
  }, [edicaoAtiva]);

  useEffect(() => {
    carregarResumo();
  }, [carregarResumo]);

  const validas = linhas.filter((l) => !l.erros.length);
  const porChave = useMemo(() => Object.fromEntries(vagas.map((v) => [v.chave, v])), [vagas]);
  const usadas = useMemo(() => new Set(Object.values(escolha).filter(Boolean)), [escolha]);
  const semCrianca = validas.filter((l) => !escolha[l.linha]).length;
  const total = validas.reduce((s, l) => {
    const v = porChave[escolha[l.linha]];
    if (!v) return s;
    return s + Number(v.tipo === "cesta" ? resumo?.valor_cesta : resumo?.valor_festa);
  }, 0);

  const livres = (resumo?.instituicoes ?? [])
    .filter((i) => escolhidas.includes(i.id))
    .reduce((s, i) => s + i.cesta_livres + i.festa_livres, 0);

  function alternarInstituicao(id) {
    definirEscolhidas((atual) =>
      atual.includes(id) ? atual.filter((i) => i !== id) : [...atual, id],
    );
  }

  /** Sugere uma vaga por linha valida, na ordem, sem repetir. Mantem o que ja
   *  foi escolhido e ainda esta livre. */
  function sugerir(linhasLidas, todasVagas, anterior = {}) {
    const existe = new Set(todasVagas.map((v) => v.chave));
    const nova = {};
    const tomadas = new Set();
    for (const l of linhasLidas) {
      const antes = anterior[l.linha];
      if (antes && existe.has(antes) && !tomadas.has(antes)) {
        nova[l.linha] = antes;
        tomadas.add(antes);
      }
    }
    let i = 0;
    for (const l of linhasLidas) {
      if (l.erros.length || nova[l.linha]) continue;
      while (i < todasVagas.length && tomadas.has(todasVagas[i].chave)) i += 1;
      if (i < todasVagas.length) {
        nova[l.linha] = todasVagas[i].chave;
        tomadas.add(todasVagas[i].chave);
      } else {
        nova[l.linha] = "";
      }
    }
    return nova;
  }

  async function ler(evento) {
    evento.preventDefault();
    definirErro("");
    definirLendo(true);
    try {
      const [lidas, { criancas }] = await Promise.all([
        lerPlanilhaDoLote(edicaoAtiva, planilha),
        vagasDoLote(edicaoAtiva, escolhidas),
      ]);
      const todas = listarVagas(criancas);
      definirLinhas(lidas.linhas);
      definirVagas(todas);
      definirEscolha(sugerir(lidas.linhas, todas));
      definirChaveEnvio(novaChave());
      definirEtapa("conferir");
      window.scrollTo(0, 0);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirLendo(false);
    }
  }

  async function confirmar() {
    definirErro("");
    definirGravando(true);
    try {
      const itens = validas.map((l) => {
        const v = porChave[escolha[l.linha]];
        return {
          linha: l.linha,
          nome: l.padrinho_existente?.nome ?? l.nome,
          whatsapp: l.whatsapp,
          padrinho_id: l.padrinho_existente?.id ?? null,
          crianca_id: v.id,
          tipo: v.tipo,
        };
      });
      const gravado = await gravarLote(
        {
          edicao_id: edicaoAtiva,
          nome: nomeGrupo.trim(),
          data,
          forma,
          chave_envio: chaveEnvio,
          itens,
        },
        comprovante,
      );
      definirLote(gravado);
      definirEtapa("pronto");
      notificar(`${gravado.apadrinhamentos} apadrinhamento(s) gravado(s).`);
      carregarResumo();
      window.scrollTo(0, 0);
    } catch (e) {
      definirErro(e.message);
      // Alguem pode ter apadrinhado uma das criancas enquanto a tela estava
      // aberta: as vagas voltam do servidor, e so as linhas que perderam a
      // crianca ganham outra sugestao.
      if (e.status === 409) {
        try {
          const { criancas } = await vagasDoLote(edicaoAtiva, escolhidas);
          const todas = listarVagas(criancas);
          definirVagas(todas);
          definirEscolha((atual) => sugerir(linhas, todas, atual));
        } catch {
          /* fica o erro de cima */
        }
      }
    } finally {
      definirGravando(false);
    }
  }

  async function baixar(id) {
    definirBaixando(id);
    try {
      await baixarAgradecimentosDoLote(id);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirBaixando(null);
    }
  }

  /** Volta a um lote ja gravado: a lista de envio e o ZIP dele. */
  async function abrir(id) {
    definirErro("");
    definirAbrindo(id);
    try {
      definirLote(await detalharLote(id));
      definirEtapa("pronto");
      window.scrollTo(0, 0);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirAbrindo(null);
    }
  }

  function recomecar() {
    definirEtapa("montar");
    definirLote(null);
    definirLinhas([]);
    definirEscolha({});
    definirPlanilha(null);
    definirComprovante(null);
    definirNomeGrupo("");
    definirEscolhidas([]);
    definirErro("");
  }

  if (!edicaoAtiva) {
    return <Mensagem tipo="erro">Escolha uma edição na lateral.</Mensagem>;
  }

  return (
    <div className="emlote">
      <div className="pagina__eyebrow">Padrinhos</div>
      <h1 className="pagina__titulo">Apadrinhar em lote</h1>
      <Rabisco className="pagina__onda" />
      <p className="pagina__lede">
        Para um grupo que juntou o dinheiro e apadrinhou junto. Cada pessoa vira um padrinho
        com a sua criança e o seu agradecimento. Nada é gravado antes de você confirmar.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {etapa === "montar" && (
        <>
          <form className="painel" onSubmit={ler}>
            <h2 className="painel__titulo">{edicao?.nome}</h2>

            <Entrada
              rotulo="Nome do grupo"
              obrigatorio
              value={nomeGrupo}
              onChange={(e) => definirNomeGrupo(e.target.value)}
              maxLength={160}
              dica="Entra na observação de cada pagamento e no nome do ZIP."
            />

            <div className="linha-campos">
              <label className="campo">
                <span className="campo__rotulo">
                  Planilha do grupo<span className="campo__obrigatorio" aria-hidden="true">*</span>
                </span>
                <input
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  className="campo__controle"
                  onChange={(e) => definirPlanilha(e.target.files?.[0] ?? null)}
                  required
                />
                <span className="campo__dica">.xlsx ou .csv, com as colunas Nome e Telefone.</span>
              </label>

              <label className="campo">
                <span className="campo__rotulo">
                  Comprovante<span className="campo__obrigatorio" aria-hidden="true">*</span>
                </span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,application/pdf"
                  className="campo__controle"
                  onChange={(e) => definirComprovante(e.target.files?.[0] ?? null)}
                  required
                />
                <span className="campo__dica">Um só, que vale para todos do lote. JPG, PNG ou PDF.</span>
              </label>
            </div>

            <div className="linha-campos">
              <Entrada
                rotulo="Data do pagamento"
                tipo="date"
                obrigatorio
                value={data}
                onChange={(e) => definirData(e.target.value)}
              />
              <Selecao rotulo="Forma" value={forma} onChange={(e) => definirForma(e.target.value)}>
                {FORMAS.map((f) => (
                  <option key={f}>{f}</option>
                ))}
              </Selecao>
            </div>

            <fieldset className="emlote__instituicoes">
              <legend className="campo__rotulo">
                De quais instituições vêm as crianças
                <span className="campo__obrigatorio" aria-hidden="true">*</span>
              </legend>
              {!resumo ? (
                <Carregando>Contando as vagas...</Carregando>
              ) : (
                <div className="emlote__opcoes">
                  {resumo.instituicoes.map((i) => {
                    const vagasDela = i.cesta_livres + i.festa_livres;
                    return (
                      <label
                        key={i.id}
                        className={`emlote__opcao ${escolhidas.includes(i.id) ? "emlote__opcao--marcada" : ""}`}
                      >
                        <input
                          type="checkbox"
                          checked={escolhidas.includes(i.id)}
                          onChange={() => alternarInstituicao(i.id)}
                          disabled={vagasDela === 0}
                        />
                        <span className="emlote__opcao-nome">{i.nome}</span>
                        <span className="emlote__opcao-vagas">
                          {i.cesta_livres} cesta(s)
                          {resumo.festa_liberada ? ` · ${i.festa_livres} festa(s)` : ""} livre(s)
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
              <span className="campo__dica">
                O sistema sugere uma criança para cada pessoa, na ordem do código: primeiro as
                cestas e, quando elas acabam, as festas. Na conferência você troca o que quiser.
                {escolhidas.length > 0 && ` Vagas nas escolhidas: ${livres}.`}
              </span>
            </fieldset>

            <div className="barra-acoes barra-acoes--fim">
              <Button
                type="submit"
                carregando={lendo}
                disabled={!planilha || !comprovante || !nomeGrupo.trim() || !escolhidas.length}
              >
                {lendo ? "Lendo a planilha..." : "Ler a planilha"}
              </Button>
              <Button variant="ghost" onClick={() => navegar("/padrinhos")} disabled={lendo}>
                Voltar para padrinhos
              </Button>
            </div>
          </form>

          {lotes.length > 0 && (
            <section className="painel">
              <h2 className="painel__titulo">Lotes já gravados</h2>
              <ul className="emlote__lista">
                {lotes.map((l) => (
                  <li key={l.id} className="emlote__item">
                    <div className="emlote__item-texto">
                      <strong>{l.nome}</strong>
                      <span className="campo__dica">
                        {l.padrinhos} padrinho(s) · {l.apadrinhamentos} criança(s) ·{" "}
                        {dinheiro(l.total)} · {formatarDataHora(l.criado_em)}
                      </span>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      iconLeft={<Conversa t={14} />}
                      carregando={abrindo === l.id}
                      onClick={() => abrir(l.id)}
                    >
                      Abrir e enviar
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      {etapa === "conferir" && (
        <>
          <div className="painel">
            <h2 className="painel__titulo">Conferência: {nomeGrupo}</h2>
            <p className="emlote__numeros">
              <strong>{validas.length}</strong> pessoa(s) ·{" "}
              <strong>{validas.length - semCrianca}</strong> com criança ·{" "}
              <strong>{dinheiro(total)}</strong> no total
              {linhas.length > validas.length && (
                <>
                  {" "}
                  · <strong>{linhas.length - validas.length}</strong> linha(s) com erro ficam de fora
                </>
              )}
            </p>

            {semCrianca > 0 && (
              <div className="emlote__alerta" role="status">
                <Atencao t={18} />
                <span>
                  Faltam crianças para <strong>{semCrianca}</strong> pessoa(s) nas instituições
                  escolhidas. Volte e marque mais uma instituição, ou escolha na tabela.
                </span>
              </div>
            )}

            <div className="barra-acoes barra-acoes--fim">
              <Button
                onClick={confirmar}
                carregando={gravando}
                disabled={semCrianca > 0 || validas.length === 0}
              >
                {gravando
                  ? "Gravando..."
                  : `Confirmar ${validas.length} apadrinhamento(s)`}
              </Button>
              <Button variant="ghost" onClick={() => definirEtapa("montar")} disabled={gravando}>
                Voltar
              </Button>
            </div>
          </div>

          <table className={`tabela emlote__tabela ${estreita ? "emlote__tabela--estreita" : ""}`}>
            <thead>
              <tr>
                {!estreita && <th className="emlote__col-linha">Linha</th>}
                <th className="emlote__col-padrinho">Padrinho</th>
                <th>Criança</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l) => {
                const atual = escolha[l.linha] ?? "";
                const fora = l.erros.length > 0;
                return (
                  <tr key={l.linha} className={fora ? "emlote__linha--fora" : ""}>
                    {!estreita && <td className="emlote__col-linha">{l.linha}</td>}
                    <td className="emlote__col-padrinho">
                      <div className="emlote__nome">{l.padrinho_existente?.nome ?? (l.nome || "(sem nome)")}</div>
                      <div className="campo__dica">{l.whatsapp || "sem telefone"}</div>
                      <div className="emlote__etiquetas">
                        {l.erros.map((e) => (
                          <span key={e} className="etiqueta etiqueta--parado">{e}</span>
                        ))}
                        {l.avisos
                          .filter((a) => a !== "sem telefone")
                          .map((a) => (
                            <span key={a} className="etiqueta etiqueta--neutra">{a}</span>
                          ))}
                      </div>
                    </td>
                    <td>
                      {fora ? (
                        <span className="campo__dica">Fica de fora: corrija a planilha.</span>
                      ) : (
                        <select
                          className="campo__controle campo__controle--selecao emlote__escolha"
                          aria-label={`Criança de ${l.nome}`}
                          value={atual}
                          onChange={(e) =>
                            definirEscolha((x) => ({ ...x, [l.linha]: e.target.value }))
                          }
                        >
                          <option value="">Escolha a criança</option>
                          {vagas
                            .filter((v) => v.chave === atual || !usadas.has(v.chave))
                            .map((v) => (
                              <option key={v.chave} value={v.chave}>
                                {rotuloDaVaga(v)}
                              </option>
                            ))}
                        </select>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}

      {etapa === "pronto" && lote && (
        <>
          <div className="painel">
            <h2 className="painel__titulo">Lote: {lote.nome}</h2>
            <p className="emlote__numeros">
              <strong>{lote.padrinhos}</strong> padrinho(s) ·{" "}
              <strong>{lote.apadrinhamentos}</strong> criança(s) ·{" "}
              <strong>{dinheiro(lote.total)}</strong>
            </p>
            <p className="campo__dica">
              Para mandar tudo de uma vez no grupo, baixe o ZIP: cada arquivo começa pelo nome
              completo do padrinho. Para mandar a cada um, use a lista abaixo.
            </p>
            <div className="barra-acoes barra-acoes--fim">
              <Button
                iconLeft={<Baixar t={16} />}
                carregando={baixando === lote.id}
                onClick={() => baixar(lote.id)}
              >
                Baixar os agradecimentos
              </Button>
              <Button variant="ghost" onClick={recomecar}>
                Voltar aos lotes
              </Button>
            </div>
          </div>

          <EnvioDoLote lote={lote} aoAtualizar={definirLote} />
        </>
      )}
    </div>
  );
}
