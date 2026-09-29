import { useEffect, useState } from "react";
import EtiquetaDia from "../components/core/EtiquetaDia.jsx";
import Rabisco from "../components/core/Rabisco.jsx";
import ArtePainel from "../components/layout/ArtePainel.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Metrica from "../components/feedback/Metrica.jsx";
import Anel from "../components/feedback/Anel.jsx";
import BarraDupla from "../components/feedback/BarraDupla.jsx";
import Progresso from "../components/feedback/Progresso.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { buscarRelatorio } from "../services/painel.js";

function primeiroNome(nome) {
  return nome?.trim().split(" ")[0] ?? "";
}

function plural(n, um, muitos) {
  return `${n} ${n === 1 ? um : muitos}`;
}

/** Quantos dias faltam para o primeiro dia de evento que ainda nao passou.
 *
 * `null` quando a edicao nao tem dia cadastrado ou quando todos ja passaram —
 * e nesses casos a contagem some do banner em vez de mostrar numero negativo
 * ou "faltam 0 dias" para uma festa que foi em dezembro passado.
 *
 * A conta e feita em datas locais, nao em UTC: `new Date("2026-12-05")` e
 * meia-noite UTC, que no horario de Brasilia ainda e dia 4 — a contagem sairia
 * um dia maior o tempo todo.
 */
function diasParaAFesta(porDia) {
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);

  const proximas = (porDia ?? [])
    .map((linha) => linha.data)
    .filter(Boolean)
    .map((texto) => {
      const [ano, mes, dia] = texto.split("-").map(Number);
      return new Date(ano, mes - 1, dia);
    })
    .filter((data) => data >= hoje)
    .sort((a, b) => a - b);

  if (proximas.length === 0) return null;
  return Math.round((proximas[0] - hoje) / 86400000);
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
  const faltamDias = diasParaAFesta(relatorio?.por_dia);
  const maxPorDia = Math.max(1, ...(relatorio?.por_dia ?? []).map((d) => d.criancas));
  const maxPorIdade = Math.max(
    1,
    ...(relatorio?.por_idade ?? []).map((f) => f.masculino + f.feminino),
  );

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
      <div className="abertura abertura--arte">
        {/* O ceu fica preso ao raio do card; os adesivos, que moram fora desta
            camada, passam por cima da borda.

            Sem fita aqui, de proposito: sobre o fundo escuro ela era a
            primeira coisa que se via, na frente da propria saudacao. Card e
            modal continuam com a delas, onde corre sobre fundo claro e marca
            o topo sem disputar com nada. */}
        <div className="abertura__recorte" aria-hidden="true">
          <ArtePainel />
        </div>
        {/* Dois adesivos, de tamanhos diferentes e girando para lados
            opostos: assim eles leem como cenario. Uma Estrela grande e
            sozinha e SINAL — e o que o banner de conclusao usa para dizer
            que alguem terminou alguma coisa. */}
        <img
          className="abertura__mascote abertura__mascote--principal"
          src="/acesso/images/adesivo-festa.png"
          alt=""
        />
        <img
          className="abertura__mascote abertura__mascote--apoio"
          src="/acesso/images/adesivo-oracao.png"
          alt=""
        />
        {/* Saudacao a esquerda, contexto a direita, na MESMA linha: assim o
            banner ocupa largura em vez de altura, e a regua que separava os
            dois deixa de existir.

            A lede entra no bloco da ESQUERDA, junto da saudacao, e nao solta
            embaixo da linha. E o que deixa os chips centrados na altura do
            banner: com o texto todo de um lado, o `align-items: center` da
            linha tem contra o que centrar. Soltos, eles se alinhavam so ao
            titulo e ficavam boiando no alto do card. */}
        <div className="abertura__linha">
          <div className="abertura__texto">
            <div className="abertura__saudacao">
              <h1 className="abertura__titulo">
                Olá, <span className="abertura__nome">{primeiroNome(usuario?.nome)}</span>!
              </h1>
              <Rabisco tamanho={40} className="abertura__onda" />
            </div>
            <p className="abertura__lede">
              {soMinhas && r
                ? ledeDoComissario(r)
                : "Acompanhe o panorama da edição e siga para o que precisa da sua mão."}
            </p>
          </div>
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
            {vinculoAtivo && (
              <span className="chip chip--discreto">{vinculoAtivo.perfil}</span>
            )}
            {faltamDias !== null && (
              <span className="chip chip--contagem">
                {faltamDias === 0
                  ? "A festa é hoje!"
                  : `${plural(faltamDias, "dia", "dias")} para a festa`}
              </span>
            )}
          </div>
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
                <div className="metricas">
                  <Metrica
                    rotulo="Crianças"
                    valor={r.criancas}
                    destaque
                    nota={
                      /* Para o comissario a instituicao nao e a informacao:
                         ele quer saber quantas ja estao resolvidas. */
                      soMinhas
                        ? plural(r.criancas - r.completas, "a completar", "a completar")
                        : plural(r.instituicoes, "instituição", "instituições")
                    }
                  />
                  <Metrica
                    rotulo="Cesta"
                    valor={r.cesta_feitos}
                    de={r.criancas}
                    tom="cesta"
                    nota={`faltam ${r.criancas - r.cesta_feitos}`}
                  />
                  <Metrica
                    rotulo="Festa"
                    valor={r.festa_feitos}
                    de={r.criancas}
                    tom="festa"
                    nota={`faltam ${r.criancas - r.festa_feitos}`}
                  />
                  <Metrica
                    rotulo="Completas"
                    valor={r.completas}
                    de={r.criancas}
                    nota="com os dois padrinhos"
                  />
                </div>
              )}

              {/* Linha larga: o dia do evento em barras, e o anel da edicao
                  ao lado. O anel repete o numero de "Completas" de proposito —
                  la ele e contagem, aqui e proporcao, e a coordenacao decide
                  olhando a proporcao. */}
              <div className="painel__grade painel__grade--larga">
                {relatorio.por_dia.length > 0 && (
                  <section className="cartao">
                    <div className="cartao__topo">
                      <h3 className="cartao__titulo">Por dia do evento</h3>
                      <span className="legenda">
                        <span className="legenda__item legenda__item--feito">completas</span>
                        <span className="legenda__item legenda__item--falta">faltam</span>
                      </span>
                    </div>
                    <p className="cartao__lede">
                      O comprimento da barra é o tamanho do dia; o preenchimento, o
                      quanto dele já está resolvido.
                    </p>
                    <div className="barras">
                      {relatorio.por_dia.map((d) => (
                        <BarraDupla
                          key={d.dia_evento_id ?? "sem-dia"}
                          rotulo={
                            d.data ? (
                              <EtiquetaDia data={d.data} descricao={d.descricao} />
                            ) : (
                              // A pendencia da coordenacao: instituicoes que
                              // ninguem marcou ainda, e que por isso nao
                              // entram em nenhum onibus.
                              <span className="dia-vazio">sem dia</span>
                            )
                          }
                          partes={[
                            { nome: "completas", valor: d.completas, tom: "feito" },
                            { nome: "faltam", valor: d.faltam, tom: "falta" },
                          ]}
                          total={d.criancas}
                          max={maxPorDia}
                          valorTexto={
                            <>
                              {d.completas}
                              <span className="barra-dupla__de">/{d.criancas}</span>
                              {d.onibus > 0 && (
                                <span className="barra-dupla__meta">
                                  {" "}
                                  · {d.onibus} ônibus
                                </span>
                              )}
                            </>
                          }
                          aria={`${d.descricao ?? "Sem dia"}: ${d.completas} de ${
                            d.criancas
                          } crianças completas, ${d.instituicoes} instituições`}
                        />
                      ))}
                    </div>
                  </section>
                )}

                {!semCriancas && (
                  <section className="cartao cartao--anel">
                    <Anel
                      valor={r.completas}
                      de={r.criancas}
                      rotulo={soMinhas ? "das suas crianças" : "da edição"}
                      nota="crianças com padrinho de cesta e de festa"
                    />
                  </section>
                )}
              </div>

              <div className="painel__grade painel__grade--meio">
                {relatorio.por_instituicao.length > 0 && (
                  <section className="cartao">
                    <div className="cartao__topo">
                      <h3 className="cartao__titulo">Por instituição</h3>
                      <span className="legenda">
                        <span className="legenda__item legenda__item--cesta">cesta</span>
                        <span className="legenda__item legenda__item--festa">festa</span>
                      </span>
                    </div>
                    <div className="lista-progresso lista-progresso--densa">
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
                              {l.criancas}
                              {/* Completa e a crianca com os dois padrinhos; o
                                  que falta dela e o trabalho que sobra aqui. */}
                              {l.faltam > 0 && (
                                <span className="lista-progresso__falta">
                                  {" "}
                                  · faltam {l.faltam}
                                </span>
                              )}
                            </span>
                          </div>
                          <Progresso rotulo="Cesta" valor={l.cesta} de={l.criancas} tom="cesta" />
                          <Progresso rotulo="Festa" valor={l.festa} de={l.criancas} tom="festa" />
                          {/* O transporte fecha a linha. A etiqueta do dia saiu
                              daqui: o dia de cada instituicao ja e a leitura do
                              cartao ao lado, e repetido aqui ele competia com o
                              nome e com as duas barras. */}
                          {l.onibus > 0 && (
                            <div className="lista-progresso__rodape">
                              <span>{l.onibus} ônibus</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {relatorio.por_idade.length > 0 && (
                  <section className="cartao">
                    <div className="cartao__topo">
                      <h3 className="cartao__titulo">Por idade</h3>
                      <span className="legenda">
                        <span className="legenda__item legenda__item--meninos">meninos</span>
                        <span className="legenda__item legenda__item--meninas">meninas</span>
                      </span>
                    </div>
                    <p className="cartao__lede">
                      O perfil das crianças — é por ele que se decide o que comprar e
                      quantos presentes de cada tipo separar.
                    </p>
                    <div className="barras">
                      {relatorio.por_idade.map((f) => (
                        <BarraDupla
                          key={f.idade}
                          rotulo={<span className="barras__idade">{f.idade} anos</span>}
                          partes={[
                            {
                              nome: "meninos",
                              valor: f.masculino,
                              tom: "meninos",
                              rotulo: f.masculino,
                            },
                            {
                              nome: "meninas",
                              valor: f.feminino,
                              tom: "meninas",
                              rotulo: f.feminino,
                            },
                          ]}
                          total={f.masculino + f.feminino}
                          max={maxPorIdade}
                          valorTexto={f.masculino + f.feminino}
                          aria={`${f.idade} anos: ${f.masculino} meninos e ${f.feminino} meninas`}
                        />
                      ))}
                    </div>
                    {/* O numero que se procura primeiro, e que a planilha
                        antiga tinha embaixo das colunas. */}
                    <div className="barras__rodape">
                      <span>
                        {totalIdade(relatorio.por_idade, "masculino")} meninos
                      </span>
                      <span>
                        {totalIdade(relatorio.por_idade, "feminino")} meninas
                      </span>
                    </div>
                  </section>
                )}
              </div>

              {relatorio.por_comissario.length > 0 && (
                <section className="cartao">
                  <div className="cartao__topo">
                    <h3 className="cartao__titulo">Por comissário</h3>
                  </div>
                  <p className="cartao__lede">
                    Completa é a criança que já tem os dois padrinhos, de cesta e de
                    festa. São muitos nomes: aqui a tabela lê melhor que um gráfico.
                  </p>
                  <div className="tabela-rolagem">
                    <table className="tabela tabela--larga tabela--densa">
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
                              <span className="comissario__nome">{l.comissario}</span>
                              {/* O grupo e dado de apoio do nome, e fica na MESMA
                                  linha: numa lista de vinte comissarios, uma
                                  segunda linha por pessoa dobra a altura da
                                  secao sem acrescentar nada. */}
                              {l.grupo && (
                                <span className="comissario__grupo"> · {l.grupo}</span>
                              )}
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
                </section>
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
