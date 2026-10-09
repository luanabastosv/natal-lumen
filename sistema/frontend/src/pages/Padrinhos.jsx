import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import MenuAcoes from "../components/core/MenuAcoes.jsx";
import { Enviar, Imprimir } from "../components/core/icones.jsx";
import { Entrada } from "../components/core/Campo.jsx";
import CelulaEditavel from "../components/dados/CelulaEditavel.jsx";
import { AvisoParecidos, CamposPadrinho } from "../components/dados/CamposPadrinho.jsx";
import {
  PADRINHO_NOVO,
  dadosDoPadrinho,
  padrinhoCompleto,
  paraOFormulario,
} from "../components/dados/padrinho.js";
import ApadrinharCriancas from "../components/dados/ApadrinharCriancas.jsx";
import FichaPadrinho from "../components/dados/FichaPadrinho.jsx";
import ImprimirLista from "../components/dados/ImprimirLista.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import ConfirmarExclusao from "../components/feedback/ConfirmarExclusao.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";
import {
  apagarPadrinho,
  criarPadrinho,
  dependenciasDoPadrinho,
  detalharPadrinho,
  editarPadrinho,
  listarPadrinhos,
} from "../services/padrinhos.js";
import { dinheiro } from "../utils/dinheiro.js";

const POR_PAGINA = 100;
// O nome do perfil na base. Se for renomeado la, mude aqui e em
// PERFIL_COORDENACAO (backend/app/seeds/perfis_permissoes.py).
const PERFIL_COORDENACAO = "Coordenacao";
// Duas coisas que a conta de dependencias nao diz sozinha, e que mudam a
// decisao de quem clica: a crianca NAO cai (e ela volta a ficar disponivel,
// que e justamente o motivo de apagar um padrinho criado por engano), e o
// pagamento CAI (sai do caixa da edicao, ao contrario do que acontece quando
// se desfaz um apadrinhamento sozinho, onde ele fica sem destino).
const NOTA_PADRINHO =
  "As crianças não são apagadas: elas voltam a ficar disponíveis para " +
  "apadrinhar. Já o pagamento sai do caixa junto com o padrinho — se o " +
  "dinheiro entrou de verdade, desfaça só o apadrinhamento, na ficha.";

export default function Padrinhos() {
  // A edicao vem da lateral: e a mesma para o sistema inteiro.
  const { pode, edicaoAtiva, usuario, vinculoAtivo } = useSessao();
  const navegar = useNavigate();

  const [padrinhos, definirPadrinhos] = useState({ itens: [], total: 0 });
  const [busca, definirBusca] = useState("");
  const [imprimindo, definirImprimindo] = useState(false);
  const [pagina, definirPagina] = useState(1);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const notificar = useNotificar();

  const [formAberto, definirFormAberto] = useState(false);
  // O padrinho sendo editado. null = o formulario e de um padrinho novo. A
  // mesma janela serve aos dois: os campos sao os mesmos, so muda o titulo e
  // para onde vai o salvar.
  const [emEdicao, definirEmEdicao] = useState(null);
  // O padrinho com o passo a passo de apadrinhar aberto, no computador (no
  // celular e a pagina propria). Abre SOZINHO, sem a ficha por baixo: vem do
  // "Salvar e apadrinhar" do cadastro ou do "Apadrinhar" do menu da linha.
  const [apadrinhandoDe, definirApadrinhandoDe] = useState(null);
  const [campos, definirCampos] = useState(PADRINHO_NOVO);
  const [salvando, definirSalvando] = useState(false);

  // Guarda o id, nao o objeto: a ficha le sempre a linha que esta na lista,
  // entao uma mudanca feita dentro da janela aparece nos dois lugares de uma
  // vez, sem duas copias do mesmo padrinho podendo divergir.
  const [fichaAbertaId, definirFichaAbertaId] = useState(null);
  const fichaAberta = padrinhos.itens.find((p) => p.id === fichaAbertaId) ?? null;

  function abrirFicha(id) {
    definirFichaAbertaId(id);
  }

  const podeEditar = pode("editar_padrinhos");
  // A permissao ESTREITA: registrar o pagamento dos padrinhos que alcanca.
  // Nao e a do financeiro da edicao — o comissario tem esta e nao aquela, e e
  // por ela que o apadrinhamento dele se confirma.
  const podePagar = pode("registrar_pagamentos_padrinho");
  // Cadastrar ja leva a apadrinhar: ninguem cadastra padrinho a toa, e o
  // proximo passo da conversa e sempre escolher as criancas dele.
  const salvarEApadrinhar = podeEditar && podePagar;
  // O cadastro do padrinho e de quem o trouxe: o comissario de base so muda
  // as informacoes dos padrinhos que ele mesmo cadastrou. Apadrinhar mais uma
  // crianca para o padrinho do colega continua liberado. Quem coordena muda
  // qualquer um. O servidor confere de novo (PATCH /padrinhos).
  const soMeusPadrinhos = Boolean(vinculoAtivo?.so_criancas_atribuidas) && !usuario?.admin_geral;
  const podeMudar = (p) => podeEditar && (!soMeusPadrinhos || p.criado_por_id === usuario?.id);
  // Desfazer engano de captacao: apagar o cadastro, e desfazer apadrinhamento
  // JA PAGO. Coordenacao e administracao geral — quem capta corrige o que
  // acabou de digitar, mas nao desfaz o que ja virou numero e dinheiro.
  const podeExcluir = pode("excluir_padrinhos");
  // O envio dos lembretes e so da coordenacao geral do evento (e da
  // administracao geral) — nem a coordenacao da captacao. O backend confere de
  // novo, pelo mesmo perfil: ver routers/lembretes.py.
  const podeEnviarCartoes =
    Boolean(usuario?.admin_geral) || vinculoAtivo?.perfil === PERFIL_COORDENACAO;

  // A exclusao em curso: { registro, dependencias, erro, apagando }. Fora dela,
  // null. Igual ao das outras telas que apagam cadastro — ver Instituicoes.
  const [exclusao, definirExclusao] = useState(null);

  // No celular a planilha inteira nao cabe: ficam de pe o nome e quantas
  // criancas ele apadrinhou — o que identifica o padrinho e diz se ele ja
  // cumpriu o combinado — e as outras cinco colunas vao para a ficha, que ja
  // existia e ja traz tudo.
  const estreita = useTelaEstreita();

  // Trocar de edicao na lateral recomeca a lista: a pagina 3 da edicao anterior
  // nao tem relacao com esta, e a ficha aberta era de outro padrinho. Ajustado
  // durante o render, e nao por efeito: evita uma busca jogada fora.
  const [ultimaEdicao, definirUltimaEdicao] = useState(edicaoAtiva);
  if (edicaoAtiva !== ultimaEdicao) {
    definirUltimaEdicao(edicaoAtiva);
    definirPagina(1);
    definirFichaAbertaId(null);
  }

  const buscar = useCallback(async () => {
    try {
      definirPadrinhos(
        await listarPadrinhos({ edicao_id: edicaoAtiva, busca, pagina, por_pagina: POR_PAGINA }),
      );
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoAtiva, busca, pagina]);

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer: a
    // lista so chega depois do await, e nao daria para derivar no render.
    // eslint-disable-next-line react/set-state-in-effect
    if (edicaoAtiva) buscar();
  }, [edicaoAtiva, pagina, buscar]);

  /** Troca so a linha mexida: recarregar a lista inteira perderia a posicao de
      quem estava no meio da planilha, e fecharia a ficha aberta. */
  function trocarLinha(atualizado) {
    definirPadrinhos((atual) => ({
      ...atual,
      itens: atual.itens.map((p) => (p.id === atualizado.id ? atualizado : p)),
    }));
  }

  /** Salva uma celula e atualiza aquela linha, sem recarregar a tabela. */
  async function salvarCampo(padrinho, campo, valor) {
    const limpo = typeof valor === "string" ? valor.trim() : valor;
    // Campo apagado vira null, nunca "": o schema aceita null, e o EmailStr
    // rejeitaria a string vazia com um 422 que a celula mostraria como erro.
    trocarLinha(await editarPadrinho(padrinho.id, { [campo]: limpo === "" ? null : limpo }));
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    const dados = dadosDoPadrinho(campos);
    try {
      if (emEdicao) {
        // Troca so a linha: a pessoa continua onde estava na planilha.
        trocarLinha(await editarPadrinho(emEdicao.id, dados));
        notificar(`${dados.nome} atualizado.`);
      } else {
        const novo = await criarPadrinho({ edicao_id: Number(edicaoAtiva), ...dados });
        notificar(`${dados.nome} cadastrado.`);
        fecharFormulario();
        if (salvarEApadrinhar) {
          if (estreita) {
            navegar(`/padrinhos/${novo.id}/apadrinhar`);
            return;
          }
          definirApadrinhandoDe(novo);
        }
        buscar();
        return;
      }
      fecharFormulario();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  // "?novo=1" chega do botao do painel: a tela abre ja no cadastro. O
  // parametro sai do endereco na hora, senao recarregar a pagina abriria a
  // janela de novo.
  const [parametros, definirParametros] = useSearchParams();
  useEffect(() => {
    if (parametros.get("novo") !== "1" || !podeEditar) return;
    definirParametros({}, { replace: true });
    abrirNovo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parametros]);

  /** O papel sai com a lista INTEIRA da busca, e nao com a pagina da tela.
   *  O servidor entrega no maximo 200 por vez, entao pede pagina a pagina. */
  async function todosOsPadrinhos() {
    const todos = [];
    for (let p = 1; ; p += 1) {
      const r = await listarPadrinhos({ edicao_id: edicaoAtiva, busca, pagina: p, por_pagina: 200 });
      todos.push(...r.itens);
      if (todos.length >= r.total || r.itens.length === 0) break;
    }
    return todos;
  }

  function abrirNovo() {
    // No celular o cadastro e uma pagina, como o passo a passo de apadrinhar.
    if (estreita) {
      navegar("/padrinhos/novo");
      return;
    }
    definirEmEdicao(null);
    definirCampos(PADRINHO_NOVO);
    definirFormAberto(true);
  }

  /** Reabre o formulario de cadastro com o que ja esta gravado. */
  function abrirEdicao(padrinho) {
    definirErro("");
    definirEmEdicao(padrinho);
    definirCampos(paraOFormulario(padrinho));
    definirFormAberto(true);
  }

  /** O nome digitado ja e de um padrinho: em vez de cadastrar de novo,
   *  apadrinha pelo cadastro que existe. */
  async function usarExistente(existente) {
    definirErro("");
    try {
      const padrinho = await detalharPadrinho(existente.id);
      fecharFormulario();
      definirApadrinhandoDe(padrinho);
    } catch (e) {
      definirErro(e.message);
    }
  }

  function fecharFormulario() {
    definirFormAberto(false);
    definirEmEdicao(null);
    definirCampos(PADRINHO_NOVO);
  }

  /** Abre a janela e ja pergunta ao servidor o que vai junto. */
  async function pedirExclusao(padrinho) {
    definirErro("");
    definirFichaAbertaId(null);
    definirExclusao({ registro: padrinho, dependencias: null, erro: "", apagando: false });
    try {
      const conta = await dependenciasDoPadrinho(padrinho.id);
      definirExclusao((atual) =>
        atual && atual.registro.id === padrinho.id ? { ...atual, dependencias: conta } : atual,
      );
    } catch (e) {
      definirExclusao((atual) => (atual ? { ...atual, erro: e.message } : atual));
    }
  }

  async function confirmarExclusao() {
    const padrinho = exclusao.registro;
    definirExclusao((atual) => ({ ...atual, apagando: true, erro: "" }));
    try {
      await apagarPadrinho(padrinho.id);
      // Tira da lista e desconta do total, em vez de recarregar: quem estava no
      // meio da planilha continua onde estava.
      definirPadrinhos((atual) => ({
        itens: atual.itens.filter((p) => p.id !== padrinho.id),
        total: Math.max(0, atual.total - 1),
      }));
      notificar(`${padrinho.nome} apagado.`);
      definirExclusao(null);
    } catch (e) {
      definirExclusao((atual) => (atual ? { ...atual, apagando: false, erro: e.message } : atual));
    }
  }

  const totalPaginas = Math.max(1, Math.ceil(padrinhos.total / POR_PAGINA));

  return (
    <div className={estreita && podeEditar ? "pagina--com-base" : undefined}>
      <div className="pagina__cabecalho">
        <div className="pagina__texto">
          <div className="pagina__eyebrow">Captação</div>
          <h1 className="pagina__titulo">Padrinhos</h1>
          <Rabisco className="pagina__onda" />
          <p className="pagina__lede">
            {estreita
              ? "Toque nos três pontos para abrir a ficha ou apadrinhar."
              : "Clique na célula para editar; o menu abre a ficha com as crianças."}
          </p>
        </div>
        {/* Imprimir no alto, ao lado do titulo, so o icone: o mesmo botao da
            lista de criancas e da de kits. */}
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

      {imprimindo && (
        <ImprimirLista
          titulo="Padrinhos"
          subtitulo={busca ? `Busca: ${busca}` : "Lista de padrinhos"}
          aoFechar={() => definirImprimindo(false)}
          buscarTudo={todosOsPadrinhos}
          colunas={[
            { id: "nome", rotulo: "Padrinho", valor: (p) => p.nome },
            { id: "whatsapp", rotulo: "WhatsApp", valor: (p) => p.whatsapp ?? "" },
            { id: "email", rotulo: "Email", valor: (p) => p.email ?? "" },
            {
              id: "criancas",
              rotulo: "Crianças",
              valor: (p) =>
                [...new Set(p.apadrinhamentos.map((a) => a.crianca_codigo))].join(", "),
            },
            { id: "pago", rotulo: "Pago", valor: (p) => dinheiro(p.total_pago) },
            {
              id: "membro",
              rotulo: "Ser Feliz",
              valor: (p) => (p.membro_ser_feliz ? "Sim" : p.membro_ser_feliz === false ? "Não" : ""),
            },
            {
              id: "mensal",
              rotulo: "Mensal",
              valor: (p) => (p.interesse_mensal ? "Sim" : p.interesse_mensal === false ? "Não" : ""),
            },
            { id: "observacoes", rotulo: "Observações", valor: (p) => p.observacoes ?? "" },
          ]}
          sugestao={{
            colunas: ["nome", "whatsapp", "criancas", "pago"],
            orientacao: "retrato",
            ordenarPor: "nome",
          }}
          ordenacoes={[
            { id: "nome", rotulo: "Nome", de: (p) => p.nome },
            { id: "pago", rotulo: "Valor pago", de: (p) => String(Math.round(Number(p.total_pago) * 100)).padStart(10, "0") },
          ]}
        />
      )}

      <Mensagem tipo="erro">{erro}</Mensagem>

      <form
        className="barra-acoes"
        onSubmit={(e) => {
          e.preventDefault();
          definirPagina(1);
          buscar();
        }}
      >
        {/* No celular a busca ocupa a linha inteira e o botao Buscar sai: a
            lista ja filtra enquanto se digita, e o "ir" do teclado tambem
            busca. No computador o botao fica, para quem espera ve-lo. */}
        <Entrada
          classe={estreita ? "barra-acoes__busca" : undefined}
          tipo={estreita ? "search" : "text"}
          enterKeyHint="search"
          value={busca}
          onChange={(e) => definirBusca(e.target.value)}
          placeholder="Nome, WhatsApp ou email"
        />
        {!estreita && (
          <Button type="submit" size="sm" variant="ghost">
            Buscar
          </Button>
        )}
        {busca && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              definirBusca("");
              definirPagina(1);
            }}
          >
            Limpar
          </Button>
        )}
        {/* No celular a contagem sai: a linha e da busca. */}
        {!estreita && <span className="campo__dica">{padrinhos.total} padrinho(s)</span>}

        {/* Na ponta oposta da linha: o CTA da pagina fica longe dos campos de
            busca, sem roubar uma linha so para ele. No celular ela nao existe:
            o envio e so no computador, e o Novo padrinho desce para a base. */}
        {!estreita && (podeEditar || podeEnviarCartoes) && (
          <div className="barra-acoes__ponta">
            {/* So no computador: o envio dos lembretes e trabalho de mesa,
                com a lista de padrinhos e cartoes inteira na frente. */}
            {podeEnviarCartoes && (
              /* Ghost, e nao cheio: o CTA da tela continua sendo "Novo
                 padrinho". Este e um caminho para outra tela. */
              <Button
                size="sm"
                variant="ghost"
                iconLeft={<Enviar t={14} />}
                onClick={() => navegar("/padrinhos/envio-de-cartoes")}
                disabled={!edicaoAtiva}
              >
                Ir para envio de cartões
              </Button>
            )}
            {podeEditar && (
              <Button size="sm" onClick={abrirNovo} disabled={!edicaoAtiva}>
                Novo padrinho
              </Button>
            )}
          </div>
        )}
      </form>

      {formAberto && (
        <Modal
          titulo={emEdicao ? "Editar informações" : "Novo padrinho"}
          rotulo={emEdicao ? "Padrinho:" : undefined}
          aoFechar={() => !salvando && fecharFormulario()}
        >
          <form onSubmit={salvar}>
            <CamposPadrinho
              campos={campos}
              definirCampos={definirCampos}
              avisoNome={
                !emEdicao && (
                  <AvisoParecidos
                    nome={campos.nome}
                    edicaoId={edicaoAtiva}
                    aoEscolher={usarExistente}
                  />
                )
              }
            />
            {/* Sozinho na barra, encostado a direita: e onde a janela termina
                e onde o olho chega depois do ultimo campo. */}
            <div className="barra-acoes barra-acoes--fim" style={{ justifyContent: "flex-end" }}>
              <Button variant="secondary" type="submit" carregando={salvando}
                /* As duas perguntas sao obrigatorias: Sim ou Nao, sem "a
                   perguntar". O cadastro so fecha quando a captacao perguntou. */
                disabled={!padrinhoCompleto(campos)}>
                {!emEdicao && salvarEApadrinhar ? "Salvar e apadrinhar" : "Salvar"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {exclusao && (
        <ConfirmarExclusao
          rotulo="Padrinho"
          nome={exclusao.registro.nome}
          dependencias={exclusao.dependencias}
          nota={NOTA_PADRINHO}
          erro={exclusao.erro}
          apagando={exclusao.apagando}
          aoConfirmar={confirmarExclusao}
          aoFechar={() => definirExclusao(null)}
        />
      )}

      {apadrinhandoDe && (
        <ApadrinharCriancas
          padrinho={apadrinhandoDe}
          aoMudar={(atualizado) => {
            definirApadrinhandoDe(atualizado);
            trocarLinha(atualizado);
          }}
          aoFechar={() => {
            definirApadrinhandoDe(null);
            buscar();
          }}
        />
      )}

      {fichaAberta && (
        <FichaPadrinho
          padrinho={fichaAberta}
          aoFechar={() => definirFichaAbertaId(null)}
          podeEditar={podeEditar}
          podePagar={podePagar}
          podeExcluir={podeExcluir}
          aoMudar={trocarLinha}
        />
      )}

      {carregando ? (
        <Carregando tela>Carregando padrinhos...</Carregando>
      ) : padrinhos.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhum padrinho ainda"
          corpo={
            busca
              ? "Nenhum resultado para esta busca."
              : "Cadastre os padrinhos captados e ligue cada um às crianças."
          }
        />
      ) : (
        <>
          <div className="tabela-rolagem">
            <table
              className={`planilha ${estreita ? "planilha--compacta planilha--linha-parada" : ""}`}
            >
              {/* So faz sentido onde a lista de fato rola. Na versao estreita
                  as tres colunas cabem na tela, e prometer arraste ali seria
                  mandar a pessoa procurar o que nao existe. */}
              {!estreita && (
                <caption className="tabela-dica">
                  Arraste a lista para o lado para ver todas as colunas.
                </caption>
              )}
              {/* As larguras ficam aqui, e nao no conteudo: trocar de edicao
                  nao move nenhuma coluna de lugar.

                  Duas especies de coluna, pelo motivo que esta em base.css, em
                  "Como a planilha cabe no monitor sem rolar": dado curto em px
                  — o minimo que o rotulo e o conteudo pedem, e nada alem — e
                  texto sem largura nenhuma, dividindo a sobra em partes iguais.
                  As de texto aqui sao o nome, o email e a lista de criancas:
                  sao as tres que crescem no monitor grande e as tres que
                  cortam com reticencias quando a janela aperta. */}
              <colgroup>
                <col />
                {!estreita && (
                  <>
                    <col style={{ width: 120 }} />
                    <col />
                  </>
                )}
                <col style={{ width: 36 }} />
                {!estreita && (
                  <>
                    <col />
                    <col style={{ width: 92 }} />
                    <col style={{ width: 92 }} />
                  </>
                )}
                {/* Os mesmos 40 do ponteiro viram 48 para o dedo — o botao
                    passa a medir 40px e precisa de folga ate a borda. */}
                <col style={{ width: estreita ? 48 : 40 }} />
              </colgroup>
              <thead>
                <tr>
                  <th>Nome</th>
                  {!estreita && (
                    <>
                      <th>WhatsApp</th>
                      <th>Email</th>
                    </>
                  )}
                  <th title="Quantas crianças este padrinho apadrinhou">Nº</th>
                  {!estreita && (
                    <>
                      <th>Crianças</th>
                      <th>Combinado</th>
                      <th>Pago</th>
                    </>
                  )}
                  <th className="planilha__acoes" />
                </tr>
              </thead>
              <tbody>
                {padrinhos.itens.map((p) => {
                  const quitado =
                    p.apadrinhamentos.length > 0 && p.apadrinhamentos.every((a) => a.pago);
                  return (
                    /* A linha NAO abre a ficha no celular. Abria, e o toque nos
                       tres pontinhos — que ficam dentro dela — chegava na linha
                       tambem: quem queria apadrinhar ou editar caia sempre na
                       ficha. O caminho e o menu, nos dois tamanhos de tela. */
                    <tr key={p.id}>
                      {/* No celular o nome vira texto, mesmo para quem pode
                          editar: a celula que vira campo ao toque abriria o
                          teclado em quem so queria rolar a lista. Edicao e no
                          computador. */}
                      <td>
                        {podeMudar(p) && !estreita ? (
                          <CelulaEditavel
                            valor={p.nome}
                            aoSalvar={(v) => salvarCampo(p, "nome", v)}
                          />
                        ) : (
                          <span className="celula">{p.nome}</span>
                        )}
                      </td>
                      {!estreita && (
                        <>
                            <td>
                              {podeMudar(p) ? (
                                <CelulaEditavel
                                  valor={p.whatsapp}
                                  aoSalvar={(v) => salvarCampo(p, "whatsapp", v)}
                                />
                              ) : (
                                <span className="celula">{p.whatsapp ?? "—"}</span>
                              )}
                            </td>
                            <td>
                              {podeMudar(p) ? (
                                <CelulaEditavel
                                  valor={p.email}
                                  aoSalvar={(v) => salvarCampo(p, "email", v)}
                                />
                              ) : (
                                <span className="celula">{p.email ?? "—"}</span>
                              )}
                            </td>
                          </>
                        )}
                        <td>
                          <span className="celula" style={{ cursor: "default" }}>
                            <span
                              className={`marcador ${quitado ? "marcador--feito" : ""}`}
                              title={
                                quitado
                                  ? "Todos os apadrinhamentos estão pagos"
                                  : "Há promessa sem pagamento — ainda não conta como apadrinhamento"
                              }
                            >
                              {p.apadrinhamentos.length}
                            </span>
                          </span>
                        </td>
                        {!estreita && (
                          <>
                        <td>
                          {/* Só os nomes, cortados em duas linhas. As ações de
                              cada criança estão na ficha — ver .vinculos. */}
                          {p.apadrinhamentos.length === 0 ? (
                            <span className="vinculos--vazia">sem criança</span>
                          ) : (
                            <div
                              className="vinculos"
                              title={p.apadrinhamentos
                                .map((a) => `${a.crianca_primeiro_nome}, ${a.crianca_idade}`)
                                .join(" · ")}
                            >
                              {p.apadrinhamentos.map((a) => (
                                <span key={a.id} className="vinculo">
                                  {a.crianca_primeiro_nome}
                                  <span
                                    className={`marcador ${a.pago ? "marcador--feito" : "marcador--parcial"}`}
                                    title={`${a.tipo} · ${a.pago ? "confirmado" : "promessa, falta pagar"}`}
                                  >
                                    {a.tipo === "cesta" ? "C" : "F"}
                                  </span>
                                </span>
                              ))}
                            </div>
                          )}
                        </td>
                        <td>
                          <span className="celula" style={{ cursor: "default" }}>
                            {dinheiro(p.total_combinado)}
                          </span>
                        </td>
                        <td>
                          <span className="celula" style={{ cursor: "default" }}>
                            {dinheiro(p.total_pago)}
                          </span>
                        </td>
                        </>
                      )}
                      <td className="planilha__acoes">
                        <MenuAcoes
                          titulo={`Ações de ${p.nome}`}
                          itens={[
                            { rotulo: "Ver ficha", aoEscolher: () => abrirFicha(p.id) },
                            podeMudar(p) && {
                              rotulo: "Editar informações",
                              aoEscolher: () => abrirEdicao(p),
                            },
                            podeEditar && {
                              rotulo: "Apadrinhar uma criança",
                              // No celular, a pagina do passo a passo; no
                              // computador, a janela por cima da ficha.
                              aoEscolher: () =>
                                estreita
                                  ? navegar(`/padrinhos/${p.id}/apadrinhar`)
                                  : definirApadrinhandoDe(p),
                            },
                            podeExcluir && {
                              rotulo: "Apagar padrinho",
                              perigo: true,
                              aoEscolher: () => pedirExclusao(p),
                            },
                          ]}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {totalPaginas > 1 && (
            <div className="barra-acoes" style={{ marginTop: "var(--space-5)" }}>
              <Button size="sm" variant="ghost" onClick={() => definirPagina((p) => p - 1)} disabled={pagina <= 1}>
                Anterior
              </Button>
              <span className="campo__dica" style={{ marginTop: 0 }}>
                Página {pagina} de {totalPaginas}
              </span>
              <Button size="sm" variant="ghost" onClick={() => definirPagina((p) => p + 1)} disabled={pagina >= totalPaginas}>
                Próxima
              </Button>
            </div>
          )}
        </>
      )}

      {/* No celular o CTA da tela fica na base, fixo e a mao do polegar: a
          lista rola por baixo dele, e cadastrar um padrinho nao exige voltar
          ao topo. */}
      {estreita && podeEditar && (
        <div className="barra-base">
          <Button onClick={abrirNovo} disabled={!edicaoAtiva}>
            Novo padrinho
          </Button>
        </div>
      )}
    </div>
  );
}
