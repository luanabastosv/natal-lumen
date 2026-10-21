import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Button from "../components/core/Button.jsx";
import EtiquetaDia from "../components/core/EtiquetaDia.jsx";
import { rotuloDoPerfil } from "../components/dados/perfis.js";
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
import useTelaEstreita from "../hooks/useTelaEstreita.js";
import FichaSimples from "../components/dados/FichaSimples.jsx";
import AtividadeEquipe from "../components/dados/AtividadeEquipe.jsx";
import PainelMonitoria from "../components/dados/PainelMonitoria.jsx";
import { buscarRelatorio } from "../services/painel.js";
import { listarCuidados } from "../services/cuidados.js";
import { buscarPainelMonitoria } from "../services/monitoria.js";
import NucleosDoEvento from "../components/dados/NucleosDoEvento.jsx";
import { eCoordenacaoGeral } from "../components/layout/menu.js";
import { rotuloDia } from "../utils/dinheiro.js";

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
function ledeDoComissario(r, festaFechada) {
  if (r.criancas === 0 && !r.festa_criancas) {
    return "Assim que a coordenação atribuir crianças a você, elas aparecem aqui.";
  }

  // Antes da campanha da festa, o trabalho e so a cesta.
  if (festaFechada) {
    const semCesta = r.criancas - r.cesta_feitos;
    if (semCesta === 0) return `Suas ${r.criancas} crianças já têm padrinho de cesta. Obrigada!`;
    return `Você ainda tem ${plural(semCesta, "criança", "crianças")} para apadrinhar.`;
  }

  // Com a festa aberta sao duas listas: a cesta das crianças dele e a festa
  // que a coordenacao passou para ele, que podem nao ser as mesmas crianças.
  const cestas = r.criancas - r.cesta_feitos;
  const festas = (r.festa_criancas ?? 0) - r.festa_feitos;
  if (cestas === 0 && festas === 0) {
    return "Todas as suas crianças já têm padrinho. Obrigada!";
  }
  const partes = [];
  if (cestas > 0) partes.push(plural(cestas, "cesta", "cestas"));
  if (festas > 0) partes.push(plural(festas, "festa", "festas"));
  return `Você ainda tem ${partes.join(" e ")} para apadrinhar.`;
}

export default function Painel() {
  const { usuario, pode, vinculoAtivo, edicao, edicaoAtiva } = useSessao();

  // A unica lista do painel tem sete colunas de numero. No celular ficam de pe
  // o nome, quantas criancas e quanto ja esta feito — a pergunta que a secao
  // responde — e a quebra inteira vai para uma janela, a um toque.
  const estreita = useTelaEstreita();
  const navegar = useNavigate();
  // Cuidados especiais por dia: so a coordenacao geral e a administracao,
  // as mesmas que abrem a lista inteira na pagina de cuidados.
  const veCuidados = eCoordenacaoGeral(usuario, vinculoAtivo);
  const [cuidados, definirCuidados] = useState(null);
  useEffect(() => {
    if (!veCuidados || !edicaoAtiva) return undefined;
    let vivo = true;
    listarCuidados(edicaoAtiva)
      .then((r) => vivo && definirCuidados(r))
      // O cartao e um resumo: se a consulta falhar, ele so nao aparece.
      .catch(() => vivo && definirCuidados(null));
    return () => {
      vivo = false;
    };
  }, [veCuidados, edicaoAtiva]);

  // A divisao em nucleos que a coordenacao da monitoria fez: a coordenacao
  // geral acompanha daqui, so leitura. Falha aqui nao derruba o painel.
  const [nucleos, definirNucleos] = useState(null);
  useEffect(() => {
    if (!veCuidados || !edicaoAtiva) return undefined;
    let vivo = true;
    buscarPainelMonitoria(edicaoAtiva)
      .then((r) => vivo && definirNucleos(r.por_instituicao))
      .catch(() => vivo && definirNucleos(null));
    return () => {
      vivo = false;
    };
  }, [veCuidados, edicaoAtiva]);

  /* Quantas criancas com necessidade especial e com alergia ou restricao, em
     cada dia. Sem as desistentes: e a conta de quem vai estar la. */
  const cuidadosPorDia = (() => {
    const porDia = new Map();
    for (const c of cuidados ?? []) {
      if (c.desistiu_em) continue;
      const chave = c.dia_evento_id ?? "sem-dia";
      if (!porDia.has(chave)) {
        porDia.set(chave, { chave, data: c.dia_evento, descricao: c.dia_evento_descricao, necessidade: 0, restricao: 0 });
      }
      const d = porDia.get(chave);
      if (c.necessidade_especial) d.necessidade += 1;
      if (c.restricao_alimentar) d.restricao += 1;
    }
    return [...porDia.values()]
      .filter((d) => d.necessidade || d.restricao)
      .sort((a, b) => (!a.data ? 1 : !b.data ? -1 : a.data.localeCompare(b.data)));
  })();
  // O comissario e a coordenacao da captacao entram no sistema para uma
  // coisa: apadrinhar. O banner leva direto ao cadastro do padrinho, de onde
  // o passo a passo segue sozinho.
  const deComissarios = Boolean(vinculoAtivo?.perfil?.startsWith("Comissarios"));
  const captacao = deComissarios && pode("editar_padrinhos");
  const [detalhe, definirDetalhe] = useState(null);
  // "Ver atividade": so a coordenacao geral e a administracao geral, como os
  // cuidados especiais.
  const [vendoAtividade, definirVendoAtividade] = useState(false);

  const [relatorio, definirRelatorio] = useState(null);
  const [carregando, definirCarregando] = useState(false);
  const [erro, definirErro] = useState("");

  // A estrutura tem um painel proprio, mais estreito: quem decide o que vem
  // nele e o backend (`so_logistica`), e a tela so esconde o que veio vazio.
  const podeVerNumeros = pode("ver_painel") || pode("ver_painel_logistica");
  // A coordenacao da monitoria tem o painel dela: o papel, os cuidados e os
  // nucleos de cada dia. Ver components/dados/PainelMonitoria.jsx.
  const coordMonitoria = vinculoAtivo?.perfil === "Monitoria - coordenacao";
  // O monitor de base ve o mesmo painel, so com as instituicoes dele.
  const monitor = vinculoAtivo?.perfil === "Monitoria - monitores";
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
  // Antes da campanha da festa, tudo o que fala dela aparece apagado. Vem da
  // edicao da sessao, e nao do relatorio: o botao da lateral recarrega as
  // edicoes, e o painel acompanha sem buscar os numeros de novo.
  const festaFechada = Boolean(edicao && !edicao.festa_liberada);

  // Quem responde por criancas atribuidas a ele — o comissario — ve o painel
  // DELE. Quem diz isso e o backend, junto com os numeros que ja vieram
  // filtrados; a tela nao olha o nome do perfil.
  const soMinhas = Boolean(relatorio?.so_minhas_criancas);
  // Comissario sem nenhuma crianca atribuida: tres zeros nao explicam nada,
  // uma frase sim. A edicao vazia da coordenacao continua mostrando os zeros —
  // la eles sao a noticia.
  const semCriancas = soMinhas && r?.criancas === 0 && !r?.festa_criancas;
  // O painel da estrutura: por dia, por idade e por instituicao, e mais nada.
  // O resumo de padrinhos e o anel sao a cobranca da captacao.
  const soLogistica = Boolean(relatorio?.so_logistica);

  // O cartao de cada instituicao: no painel da coordenacao fica ao lado do
  // "Por idade"; no do comissario, ao lado do anel de progresso — quando a
  // linha do anel nao tem o dia do evento (o comissario de base nao tem).
  // O comissario de base nao ve a quebra por dia: o dia do evento nao e
  // assunto dele.
  const mostraPorDia = !soMinhas && relatorio?.por_dia?.length > 0;
  const instAoLadoDoAnel = deComissarios && !mostraPorDia;
  const cartaoPorInstituicao = relatorio?.por_instituicao?.length > 0 && (

                  <section className="cartao">
                    <div className="cartao__topo">
                      <h3 className="cartao__titulo">Por instituição</h3>
                      <span className="legenda">
                        <span className="legenda__item legenda__item--cesta">apadrinhamento de cesta</span>
                        <span className={`legenda__item legenda__item--festa ${festaFechada ? "festa-fechada" : ""}`}>apadrinhamento de festa</span>
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
                              {/* Com a festa do comissario, a cesta e a festa
                                  sao listas diferentes: o total de uma so
                                  enganaria. Fica o que falta das duas. */}
                              {l.festa_criancas == null && l.criancas}
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
                          {/* Instituicao em que o comissario so tem a festa:
                              sem barra de cesta. */}
                          {(l.criancas > 0 || l.festa_criancas == null) && (
                            <Progresso rotulo="Apadr. cesta" valor={l.cesta} de={l.criancas} tom="cesta" />
                          )}
                          {(l.festa_criancas == null || l.festa_criancas > 0) && (
                            <Progresso
                              rotulo="Apadr. festa"
                              valor={l.festa}
                              de={l.festa_criancas ?? l.criancas}
                              tom="festa"
                              apagada={festaFechada}
                            />
                          )}
                          {/* O transporte fecha a linha. A etiqueta do dia saiu
                              daqui: o dia de cada instituicao ja e a leitura do
                              cartao ao lado, e repetido aqui ele competia com o
                              nome e com as duas barras. */}
                          {/* O transporte e assunto da coordenacao e da
                              logistica; o comissario cuida de padrinho. */}
                          {l.onibus > 0 && !deComissarios && (
                            <div className="lista-progresso__rodape">
                              <span>{l.onibus} ônibus</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
  );

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
                ? ledeDoComissario(r, festaFechada)
                : soLogistica
                  ? "Quantas crianças vêm em cada dia, de cada instituição e de cada idade."
                  : coordMonitoria
                    ? "Os cartões e as autorizações de cada instituição, os cuidados especiais e os núcleos de cada dia."
                    : monitor
                      ? "Os cartões e as autorizações das suas crianças, e quem precisa de cuidado especial."
                      : "Acompanhe o panorama da edição e siga para o que precisa da sua mão."}
            </p>
            {captacao && !estreita && (
              <div className="abertura__cta">
                <Button onClick={() => navegar("/padrinhos?novo=1")}>Realizar apadrinhamento</Button>
              </div>
            )}
          </div>
          <div className="abertura__contexto">
          {/* Qual edicao esta sendo vista. Trocar de edicao e na lateral: e
              uma escolha do sistema inteiro, nao deste card. No celular a
              edicao e o perfil ja estao na barra de cima, e somem daqui (ver
              .abertura__chip-contexto). */}
            <span className="chip abertura__chip-contexto">
              {edicao
                ? edicao.nome
                : usuario?.admin_geral
                  ? "Administração geral"
                  : "Sem edição vinculada"}
            </span>
            {vinculoAtivo && (
              <span className="chip chip--discreto abertura__chip-contexto">
                {rotuloDoPerfil(vinculoAtivo.perfil)}
              </span>
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
        {/* No celular o botao de apadrinhar ocupa a largura do banner: e a
            unica coisa que o comissario vem fazer aqui. No computador ele fica
            embaixo da saudacao, como sempre. */}
        {captacao && estreita && (
          <div className="abertura__cta">
            <Button larguraTotal onClick={() => navegar("/padrinhos/novo")}>
              Realizar apadrinhamento
            </Button>
          </div>
        )}
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
              <div className="painel__cabeca">
                <h2 className="painel__titulo">{soMinhas ? "Suas crianças" : r.edicao}</h2>
                {veCuidados && edicaoAtiva && (
                  <Button size="sm" variant="ghost" onClick={() => definirVendoAtividade(true)}>
                    Ver atividade
                  </Button>
                )}
              </div>

              {semCriancas && (
                <EmptyState
                  titulo="Nenhuma criança na sua mão ainda"
                  corpo="A coordenação é quem distribui as crianças entre os comissários. Assim que alguma for sua, ela aparece aqui e na tela de crianças."
                />
              )}

              {/* Cada crianca precisa de um padrinho de cesta e um de festa.
                  Os dois se comparam ao total de criancas, nunca entre si. */}
              {!semCriancas && !soLogistica && (
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
                    rotulo="Apadrinhamento · cesta"
                    valor={r.cesta_feitos}
                    de={r.criancas}
                    tom="cesta"
                    nota={`faltam ${r.criancas - r.cesta_feitos}`}
                  />
                  <Metrica
                    rotulo="Apadrinhamento · festa"
                    valor={r.festa_feitos}
                    /* Para o comissario, a festa e a que a coordenacao passou
                       para ele — nao as criancas da lista de cesta. */
                    de={soMinhas ? r.festa_criancas : r.criancas}
                    tom="festa"
                    apagada={festaFechada}
                    nota={
                      !festaFechada
                        ? `faltam ${(soMinhas ? r.festa_criancas : r.criancas) - r.festa_feitos}`
                        : "ainda não liberada"
                    }
                  />
                  <Metrica
                    rotulo="Completas"
                    valor={r.completas}
                    de={r.criancas}
                    nota="com os dois padrinhos"
                  />
                </div>
              )}

              {/* Sem isto os numeros acima ficariam sem explicacao: uma criança
                  prometida some de "Cesta" e de "Completas" e nao reaparece em
                  lugar nenhum, e quem olha conclui que o padrinho se perdeu.
                  Ele esta aqui, e o que falta dele e o pagamento ser
                  registrado. So aparece quando ha o que cobrar. */}
              {podeVerNumeros && r.prometidos > 0 && (
                <p className="nota-prometidos">
                  <span className="nota-prometidos__ponto" aria-hidden="true" />
                  <span>
                    <strong>
                      {plural(r.prometidos, "prometido", "prometidos")}
                    </strong>{" "}
                    sem pagamento — não entram nos números acima.
                  </span>
                </p>
              )}

              {/* Linha larga: o dia do evento em barras, e o anel da edicao
                  ao lado. O anel repete o numero de "Completas" de proposito —
                  la ele e contagem, aqui e proporcao, e a coordenacao decide
                  olhando a proporcao. */}
              {/* Sem o anel, o dia do evento ocupa a linha inteira. */}
              <div
                className={`painel__grade${soLogistica ? "" : " painel__grade--larga"}`}
              >
                {mostraPorDia && (
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
                              {d.onibus > 0 && !deComissarios && (
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

                {/* Para o comissario, ao lado do anel: o dia do evento nao e
                    dele, e a linha fica com as instituicoes e o progresso. */}
                {instAoLadoDoAnel && cartaoPorInstituicao}

                {!semCriancas && !soLogistica && (
                  <section className="cartao cartao--anel">
                    {/* A cesta primeiro, numa cor; quando a festa comeca, o
                        arco dela entra por cima do da cesta. */}
                    <Anel
                      partes={[
                        { nome: "cesta", tom: "cesta", valor: r.cesta_feitos, de: r.criancas },
                        ...(festaFechada
                          ? []
                          : [
                              {
                                nome: "festa",
                                tom: "festa",
                                valor: r.festa_feitos,
                                de: soMinhas ? r.festa_criancas : r.criancas,
                              },
                            ]),
                      ]}
                      rotulo={soMinhas ? "das suas crianças" : "da edição"}
                      nota={
                        festaFechada
                          ? "crianças com padrinho de cesta"
                          : "apadrinhamento de cesta e de festa"
                      }
                    />
                  </section>
                )}
              </div>

              {/* Cuidados especiais por dia: a conta que a coordenacao leva para
                  quem acompanha e para a cozinha. O detalhe, na pagina. */}
              {veCuidados && cuidados !== null && (
                <section className="cartao cartao--cuidados">
                  <div className="cartao__topo">
                    <h3 className="cartao__titulo">Cuidados especiais</h3>
                    <button
                      type="button"
                      className="link-conferir"
                      onClick={() => navegar("/cuidados")}
                    >
                      Ver lista
                    </button>
                  </div>
                  {cuidadosPorDia.length === 0 ? (
                    <p className="cartao__lede">
                      Nenhuma autorização avisou necessidade especial ou alergia ainda.
                    </p>
                  ) : (
                    <table className="tabela tabela--densa">
                      <thead>
                        <tr>
                          <th>Dia</th>
                          <th>Necessidade especial</th>
                          <th>Alergia / restrição</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cuidadosPorDia.map((d) => (
                          <tr key={d.chave}>
                            <td>
                              {d.data ? (
                                <EtiquetaDia data={d.data} descricao={d.descricao} />
                              ) : (
                                <span className="dia-vazio">sem dia</span>
                              )}
                            </td>
                            <td className="cartao__numero" title={d.data ? rotuloDia(d.data, d.descricao) : undefined}>
                              {plural(d.necessidade, "criança", "crianças")}
                            </td>
                            <td className="cartao__numero">
                              {plural(d.restricao, "criança", "crianças")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </section>
              )}

              {veCuidados && nucleos && <NucleosDoEvento instituicoes={nucleos} />}

              {/* Sem o "Por idade" (comissarios), a instituicao ocupa a linha. */}
              <div className={`painel__grade${deComissarios ? "" : " painel__grade--meio"}`}>
                {!instAoLadoDoAnel && cartaoPorInstituicao}

                {/* O perfil por idade e para quem compra presente; o comissario
                    cuida de padrinho. */}
                {!deComissarios && relatorio.por_idade.length > 0 && (
                  <section className="cartao">
                    <div className="cartao__topo">
                      <h3 className="cartao__titulo">Por idade</h3>
                      <span className="legenda">
                        <span className="legenda__item legenda__item--meninos">meninos</span>
                        <span className="legenda__item legenda__item--meninas">meninas</span>
                      </span>
                    </div>
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
                    {festaFechada
                      ? "Quanto da cesta de cada comissário já tem padrinho."
                      : "A cesta e a festa de cada comissário: a festa conta as crianças que a coordenação passou para ele."}
                  </p>
                  <div className="tabela-rolagem">
                    {/* Sem `tabela--larga` no celular: e a largura minima dela
                        que fazia a lista rolar de lado. */}
                    <table
                      className={`tabela tabela--densa ${
                        estreita ? "tabela--compacta" : "tabela--larga"
                      }`}
                    >
                      {!estreita && (
                        <caption className="tabela-dica">
                          Arraste a lista para o lado para ver todas as colunas.
                        </caption>
                      )}
                      <thead>
                        <tr>
                          <th>Comissário</th>
                          {!estreita && <th>Apadr. cesta</th>}
                          <th>% cesta</th>
                          {!festaFechada && (
                            <>
                              {!estreita && <th>Apadr. festa</th>}
                              <th>% festa</th>
                            </>
                          )}
                          {!estreita && <th>Faltam</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {relatorio.por_comissario.map((l) => (
                          <tr
                            key={l.comissario_id ?? "sem-comissario"}
                            /* Sem menu de acoes nesta lista: a linha inteira e
                               o unico caminho para a quebra completa, entao ela
                               e tambem o que o dedo procura. */
                            onClick={estreita ? () => definirDetalhe(l) : undefined}
                          >
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
                            {/* Feitas de quantas, como na festa: o total de
                                criancas sozinho nao dizia de qual lista era. */}
                            {!estreita && (
                              <td>{l.criancas ? `${l.cesta}/${l.criancas}` : "—"}</td>
                            )}
                            {/* A planilha antiga media o que FALTAVA. Aqui a
                                coluna mede o que esta feito: e o mesmo dado,
                                e ler "80%" como boa noticia cansa menos o
                                time do que ler "20%" como ma. */}
                            <td>{percentual(l.cesta, l.criancas)}</td>
                            {!festaFechada && (
                              <>
                                {!estreita && (
                                  <td>
                                    {l.festa_criancas ? `${l.festa}/${l.festa_criancas}` : "—"}
                                  </td>
                                )}
                                <td>{percentual(l.festa, l.festa_criancas ?? 0)}</td>
                              </>
                            )}
                            {!estreita && (
                              <td className={l.faltam > 0 ? "tabela__pendente" : undefined}>
                                {l.faltam}
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {detalhe && (
                    <FichaSimples
                      rotulo="Comissário:"
                      titulo={detalhe.comissario}
                      aoFechar={() => definirDetalhe(null)}
                      campos={[
                        { rotulo: "Grupo", valor: detalhe.grupo },
                        {
                          rotulo: "Cesta",
                          valor: detalhe.criancas
                            ? `${detalhe.cesta}/${detalhe.criancas} · ${percentual(detalhe.cesta, detalhe.criancas)}`
                            : "—",
                        },
                        ...(festaFechada
                          ? []
                          : [
                              {
                                rotulo: "Festa",
                                valor: detalhe.festa_criancas
                                  ? `${detalhe.festa}/${detalhe.festa_criancas} · ${percentual(detalhe.festa, detalhe.festa_criancas)}`
                                  : "—",
                              },
                            ]),
                        {
                          rotulo: "Faltam",
                          valor: (
                            <span className={detalhe.faltam > 0 ? "tabela__pendente" : undefined}>
                              {detalhe.faltam}
                            </span>
                          ),
                        },
                      ]}
                    />
                  )}
                </section>
              )}
            </>
          )}

          {/* Sem ver_painel nao ha o que mostrar aqui, e a pagina ficaria so
              com a saudacao. O caminho e o menu — que ja lista o que o perfil
              alcanca — entao o que falta dizer e so isso. */}
          {!podeVerNumeros && (coordMonitoria || monitor) && edicaoAtiva && (
            <PainelMonitoria edicaoId={edicaoAtiva} monitor={monitor} />
          )}

          {!podeVerNumeros && !coordMonitoria && !monitor && (
            <EmptyState
              titulo="Escolha por onde começar"
              corpo="Seu perfil não acompanha os números da edição. Use o menu ao lado: ele mostra tudo o que você alcança."
            />
          )}
        </>
      )}
      {vendoAtividade && (
        <AtividadeEquipe
          edicaoId={edicaoAtiva}
          aoFechar={() => definirVendoAtividade(false)}
        />
      )}
    </div>
  );
}
