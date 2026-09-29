import { useEffect, useState } from "react";
import EtiquetaDia from "../components/core/EtiquetaDia.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Numero from "../components/feedback/Numero.jsx";
import Progresso from "../components/feedback/Progresso.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { buscarRelatorio } from "../services/painel.js";

function primeiroNome(nome) {
  return nome?.trim().split(" ")[0] ?? "";
}

function plural(n, um, muitos) {
  return `${n} ${n === 1 ? um : muitos}`;
}

/** Quanto de `de` ja esta feito, em porcento inteiro.
 *
 * Sem criancas a pergunta nao tem resposta — e a planilha antiga respondia
 * #DIV/0! justamente aqui. Um travessao diz a mesma coisa sem assustar.
 */
function percentual(valor, de) {
  return de > 0 ? `${Math.round((valor / de) * 100)}%` : "—";
}

/** A soma de uma coluna da tabela de idades. */
function totalIdade(faixas, coluna) {
  return faixas.reduce((soma, f) => soma + f[coluna], 0);
}

/** A frase de abertura do comissario: o trabalho dele, em uma linha.
 *
 * A coordenacao abre com um panorama porque decide olhando o conjunto. O
 * comissario nao: ele abre o sistema para saber quantas criancas ainda
 * dependem dele hoje, e essa e a unica coisa que a frase precisa dizer.
 */
function ledeDoComissario(r) {
  if (r.criancas === 0) {
    return "Assim que a coordenação atribuir crianças a você, elas aparecem aqui.";
  }

  const faltam = r.criancas - r.completas;
  if (faltam === 0) {
    return `Suas ${r.criancas} crianças já têm padrinho de cesta e de festa. Obrigada!`;
  }

  return `Você ainda tem ${plural(faltam, "criança", "crianças")} para apadrinhar.`;
}

export default function Painel() {
  const { usuario, pode, vinculoAtivo, edicao, edicaoAtiva } = useSessao();

  const [relatorio, definirRelatorio] = useState(null);
  const [carregando, definirCarregando] = useState(false);
  const [erro, definirErro] = useState("");

  const podeVerNumeros = pode("ver_painel");

  useEffect(() => {
    if (!podeVerNumeros || !edicaoAtiva) return;

    let vivo = true;
    // Mostrar o carregando e justamente o efeito colateral que queremos aqui.
    // eslint-disable-next-line react/set-state-in-effect
    definirCarregando(true);
    buscarRelatorio(edicaoAtiva)
      .then((dados) => vivo && definirRelatorio(dados))
      .catch((e) => vivo && definirErro(e.message))
      .finally(() => vivo && definirCarregando(false));

    return () => {
      vivo = false;
    };
  }, [podeVerNumeros, edicaoAtiva]);

  const r = relatorio?.resumo;
  // Quem responde por criancas atribuidas a ele — o comissario — ve o painel
  // DELE. Quem diz isso e o backend, junto com os numeros que ja vieram
  // filtrados; a tela nao olha o nome do perfil.
  const soMinhas = Boolean(relatorio?.so_minhas_criancas);
  // Comissario sem nenhuma crianca atribuida: tres zeros nao explicam nada,
  // uma frase sim. A edicao vazia da coordenacao continua mostrando os zeros —
  // la eles sao a noticia.
  const semCriancas = soMinhas && r?.criancas === 0;

  return (
    <div>
      {/* Card de abertura: no layout Sidebar e ele que faz o papel do
          cabecalho, carregando saudacao e contexto. So existe na home. */}
      <div className="abertura">
        <h1 className="abertura__titulo">
          Olá, <span className="abertura__nome">{primeiroNome(usuario?.nome)}</span>!
        </h1>
        <p className="abertura__lede">
          {soMinhas && r
            ? ledeDoComissario(r)
            : "Acompanhe o panorama da edição e siga para o que precisa da sua mão."}
        </p>
        <div className="abertura__contexto">
          {/* Qual edicao esta sendo vista. Trocar de edicao e na lateral: e
              uma escolha do sistema inteiro, nao deste card. */}
          <span className="chip">
            {edicao
              ? `${edicao.cidade} ${edicao.ano}`
              : usuario?.admin_geral
                ? "Administração geral"
                : "Sem edição vinculada"}
          </span>
          {vinculoAtivo && <span className="chip chip--discreto">{vinculoAtivo.perfil}</span>}
        </div>
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {!vinculoAtivo && !usuario?.admin_geral ? (
        <EmptyState
          titulo="Você ainda não está numa edição"
          corpo="Sua conta existe, mas a coordenação ainda não a vinculou a uma edição. Assim que isso acontecer, o menu aparece aqui."
        />
      ) : (
        <>
          {podeVerNumeros && carregando && <Carregando tela>Somando os números...</Carregando>}

          {podeVerNumeros && r && (
            <>
              <h2 className="painel__titulo">{soMinhas ? "Suas crianças" : r.edicao}</h2>

              {semCriancas && (
                <EmptyState
                  titulo="Nenhuma criança na sua mão ainda"
                  corpo="A coordenação é quem distribui as crianças entre os comissários. Assim que alguma for sua, ela aparece aqui e na tela de crianças."
                />
              )}

              {/* Cada crianca precisa de um padrinho de cesta e um de festa.
                  Os dois se comparam ao total de criancas, nunca entre si. */}
              {!semCriancas && (
                <div className="numeros">
                  <Numero
                    rotulo="Crianças"
                    valor={r.criancas}
                    nota={
                      /* Para o comissario a instituicao nao e a informacao:
                         ele quer saber quantas ja estao resolvidas. */
                      soMinhas
                        ? `${plural(r.completas, "completa", "completas")}, ${
                            r.criancas - r.completas
                          } a completar`
                        : plural(r.instituicoes, "instituição", "instituições")
                    }
                  />
                  <Numero
                    rotulo="Cesta apadrinhada"
                    valor={r.cesta_feitos}
                    de={r.criancas}
                    tom="cesta"
                    nota={`faltam ${r.criancas - r.cesta_feitos}`}
                  />
                  <Numero
                    rotulo="Festa apadrinhada"
                    valor={r.festa_feitos}
                    de={r.criancas}
                    tom="festa"
                    nota={`faltam ${r.criancas - r.festa_feitos}`}
                  />
                </div>
              )}

              {relatorio.por_instituicao.length > 0 && (
                <>
                  <h2 className="painel__titulo">Por instituição</h2>
                  <div className="lista-progresso">
                    {relatorio.por_instituicao.map((l) => (
                      <div key={l.instituicao_id} className="lista-progresso__item">
                        <div className="lista-progresso__topo">
                          <span className="lista-progresso__nome">
                            {l.instituicao}
                            {/* A sigla e como a equipe chama a instituicao no
                                dia a dia ("faltam tres da KN"), e e o prefixo
                                do codigo de cada crianca dela. */}
                            {l.sigla && (
                              <span className="etiqueta etiqueta--neutra lista-progresso__sigla">
                                {l.sigla}
                              </span>
                            )}
                          </span>
                          <span className="lista-progresso__total">
                            {plural(l.criancas, "criança", "crianças")}
                            {/* Completa e a crianca com os dois padrinhos; o
                                que falta dela e o trabalho que sobra aqui. */}
                            {l.faltam > 0 && (
                              <span className="lista-progresso__falta">
                                {" "}
                                · faltam {l.faltam} ({percentual(l.faltam, l.criancas)})
                              </span>
                            )}
                          </span>
                        </div>
                        <Progresso rotulo="Cesta" valor={l.cesta} de={l.criancas} tom="cesta" />
                        <Progresso rotulo="Festa" valor={l.festa} de={l.criancas} tom="festa" />
                        {/* A logistica do dia fecha o card: quando ela vai, e
                            quantos onibus a buscam. Some enquanto a
                            coordenacao nao marcou nada. */}
                        {(l.dia_evento || l.onibus > 0) && (
                          <div className="lista-progresso__rodape">
                            {l.dia_evento && (
                              <EtiquetaDia
                                data={l.dia_evento}
                                descricao={l.dia_evento_descricao}
                              />
                            )}
                            {l.onibus > 0 && <span>{l.onibus} ônibus</span>}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}

              {relatorio.por_comissario.length > 0 && (
                <>
                  <h2 className="painel__titulo" style={{ marginTop: "var(--space-7)" }}>
                    Por comissário
                  </h2>
                  <p className="pagina__lede">
                    Completa é a criança que já tem os dois padrinhos, de cesta e de festa.
                  </p>
                  <div className="tabela-rolagem">
                    <table className="tabela tabela--larga">
                      <caption className="tabela-dica">
                        Arraste a lista para o lado para ver todas as colunas.
                      </caption>
                      <thead>
                        <tr>
                          <th>Comissário</th>
                          <th>Crianças</th>
                          <th>Cesta</th>
                          <th>Festa</th>
                          <th>Completas</th>
                          <th>Faltam</th>
                          <th>% feito</th>
                        </tr>
                      </thead>
                      <tbody>
                        {relatorio.por_comissario.map((l) => (
                          <tr key={l.comissario_id ?? "sem-comissario"}>
                            <td>
                              {l.comissario}
                              {/* O grupo e dado de apoio do nome logo acima:
                                  le-se depois dele, nao no lugar dele. */}
                              <div className="vinculo-linha__detalhe">{l.grupo ?? "—"}</div>
                            </td>
                            <td>{l.criancas}</td>
                            <td>{l.cesta}</td>
                            <td>{l.festa}</td>
                            <td>{l.completas}</td>
                            <td className={l.faltam > 0 ? "tabela__pendente" : undefined}>
                              {l.faltam}
                            </td>
                            {/* A planilha antiga media o que FALTAVA. Aqui a
                                coluna mede o que esta feito: e o mesmo dado,
                                e ler "80%" como boa noticia cansa menos o
                                time do que ler "20%" como ma. */}
                            <td>{percentual(l.completas, l.criancas)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}

              {relatorio.por_dia.length > 0 && (
                <>
                  <h2 className="painel__titulo" style={{ marginTop: "var(--space-7)" }}>
                    Por dia do evento
                  </h2>
                  <p className="pagina__lede">
                    Quantas crianças cada dia recebe, e o transporte já combinado para
                    buscá-las.
                  </p>
                  <div className="tabela-rolagem">
                    <table className="tabela tabela--larga">
                      <caption className="tabela-dica">
                        Arraste a lista para o lado para ver todas as colunas.
                      </caption>
                      <thead>
                        <tr>
                          <th>Dia</th>
                          <th>Instituições</th>
                          <th>Crianças</th>
                          <th>Ônibus</th>
                          <th>Completas</th>
                          <th>Faltam</th>
                          <th>% feito</th>
                        </tr>
                      </thead>
                      <tbody>
                        {relatorio.por_dia.map((d) => (
                          <tr key={d.dia_evento_id ?? "sem-dia"}>
                            <td>
                              {d.data ? (
                                <EtiquetaDia data={d.data} descricao={d.descricao} />
                              ) : (
                                // A pendencia da coordenacao: instituicoes que
                                // ninguem marcou ainda, e que por isso nao
                                // entram em nenhum onibus.
                                <span className="dia-vazio">sem dia</span>
                              )}
                            </td>
                            <td>{d.instituicoes}</td>
                            <td>{d.criancas}</td>
                            <td>{d.onibus || "—"}</td>
                            <td>{d.completas}</td>
                            <td className={d.faltam > 0 ? "tabela__pendente" : undefined}>
                              {d.faltam}
                            </td>
                            <td>{percentual(d.completas, d.criancas)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}

              {relatorio.por_idade.length > 0 && (
                <>
                  <h2 className="painel__titulo" style={{ marginTop: "var(--space-7)" }}>
                    Por idade
                  </h2>
                  <p className="pagina__lede">
                    O perfil das crianças da edição — é por ele que se decide o que
                    comprar e quantos presentes de cada tipo separar.
                  </p>
                  <div className="tabela-rolagem">
                    <table className="tabela">
                      <thead>
                        <tr>
                          <th>Idade</th>
                          <th>Meninos</th>
                          <th>Meninas</th>
                          <th>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {relatorio.por_idade.map((f) => (
                          <tr key={f.idade}>
                            <td>{f.idade} anos</td>
                            <td>{f.masculino}</td>
                            <td>{f.feminino}</td>
                            <td>{f.masculino + f.feminino}</td>
                          </tr>
                        ))}
                      </tbody>
                      {/* O rodape e o que a planilha tinha embaixo das colunas,
                          e e o numero que se procura primeiro: quantos meninos
                          e quantas meninas no total. */}
                      <tfoot>
                        <tr>
                          <th scope="row">Total</th>
                          <td>{totalIdade(relatorio.por_idade, "masculino")}</td>
                          <td>{totalIdade(relatorio.por_idade, "feminino")}</td>
                          <td>
                            {totalIdade(relatorio.por_idade, "masculino") +
                              totalIdade(relatorio.por_idade, "feminino")}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </>
              )}
            </>
          )}

          {/* Sem ver_painel nao ha o que mostrar aqui, e a pagina ficaria so
              com a saudacao. O caminho e o menu — que ja lista o que o perfil
              alcanca — entao o que falta dizer e so isso. */}
          {!podeVerNumeros && (
            <EmptyState
              titulo="Escolha por onde começar"
              corpo="Seu perfil não acompanha os números da edição. Use o menu ao lado: ele mostra tudo o que você alcança."
            />
          )}
        </>
      )}
    </div>
  );
}
