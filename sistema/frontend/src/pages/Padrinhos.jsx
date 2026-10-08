import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import MenuAcoes from "../components/core/MenuAcoes.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import CelulaEditavel from "../components/dados/CelulaEditavel.jsx";
import FichaPadrinho from "../components/dados/FichaPadrinho.jsx";
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
  editarPadrinho,
  listarPadrinhos,
} from "../services/padrinhos.js";
import { dinheiro } from "../utils/dinheiro.js";

const POR_PAGINA = 100;
/* As duas perguntas da captacao nascem VAZIAS, e vazio nao e "nao": e "ainda
   nao perguntei". Quem cadastra o padrinho as vezes so tem o nome e o zap na
   mao, e forcar uma resposta ali inventaria dado. */
const NOVO = {
  nome: "",
  whatsapp: "",
  email: "",
  observacoes: "",
  membro_ser_feliz: "",
  interesse_mensal: "",
};

// Duas coisas que a conta de dependencias nao diz sozinha, e que mudam a
// decisao de quem clica: a crianca NAO cai (e ela volta a ficar disponivel,
// que e justamente o motivo de apagar um padrinho criado por engano), e o
// pagamento CAI (sai do caixa da edicao, ao contrario do que acontece quando
// se desfaz um apadrinhamento sozinho, onde ele fica sem destino).
const NOTA_PADRINHO =
  "As crianças não são apagadas: elas voltam a ficar disponíveis para " +
  "apadrinhar. Já o pagamento sai do caixa junto com o padrinho — se o " +
  "dinheiro entrou de verdade, desfaça só o apadrinhamento, na ficha.";

/** "" -> null, "sim" -> true, "nao" -> false. */
function resposta(valor) {
  return valor === "" ? null : valor === "sim";
}

export default function Padrinhos() {
  // A edicao vem da lateral: e a mesma para o sistema inteiro.
  const { pode, edicaoAtiva, usuario, vinculoAtivo } = useSessao();
  const navegar = useNavigate();

  const [padrinhos, definirPadrinhos] = useState({ itens: [], total: 0 });
  const [busca, definirBusca] = useState("");
  const [pagina, definirPagina] = useState(1);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const notificar = useNotificar();

  const [formAberto, definirFormAberto] = useState(false);
  const [campos, definirCampos] = useState(NOVO);
  const [salvando, definirSalvando] = useState(false);

  // Guarda o id, nao o objeto: a ficha le sempre a linha que esta na lista,
  // entao uma mudanca feita dentro da janela aparece nos dois lugares de uma
  // vez, sem duas copias do mesmo padrinho podendo divergir.
  const [fichaAbertaId, definirFichaAbertaId] = useState(null);
  // O icone de apadrinhar na linha abre a mesma ficha, ja com o formulario de
  // ligacao aberto: e um atalho para a acao, nao um segundo caminho para ela.
  const [abrirLigando, definirAbrirLigando] = useState(false);
  const fichaAberta = padrinhos.itens.find((p) => p.id === fichaAbertaId) ?? null;

  function abrirFicha(id, ligando = false) {
    definirAbrirLigando(ligando);
    definirFichaAbertaId(id);
  }

  const podeEditar = pode("editar_padrinhos");
  // A permissao ESTREITA: registrar o pagamento dos padrinhos que alcanca.
  // Nao e a do financeiro da edicao — o comissario tem esta e nao aquela, e e
  // por ela que o apadrinhamento dele se confirma.
  const podePagar = pode("registrar_pagamentos_padrinho");
  // Desfazer engano de captacao: apagar o cadastro, e desfazer apadrinhamento
  // JA PAGO. Coordenacao e administracao geral — quem capta corrige o que
  // acabou de digitar, mas nao desfaz o que ja virou numero e dinheiro.
  const podeExcluir = pode("excluir_padrinhos");
  // O envio dos lembretes e da coordenacao: o comissario, que so enxerga as
  // proprias criancas, veria um padrinho "pronto" com metade dos cartoes. Quem
  // responde por instituicoes recebe `instituicoes` preenchido — e esse o
  // sinal, e nao o nome do perfil. O backend confere de novo.
  const podeEnviarCartoes =
    pode("enviar_cartoes") && (usuario?.admin_geral || (vinculoAtivo && !vinculoAtivo.instituicoes));

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
    try {
      await criarPadrinho({
        edicao_id: Number(edicaoAtiva),
        nome: campos.nome.trim(),
        whatsapp: campos.whatsapp.trim() || null,
        email: campos.email.trim() || null,
        observacoes: campos.observacoes.trim() || null,
        membro_ser_feliz: resposta(campos.membro_ser_feliz),
        interesse_mensal: resposta(campos.interesse_mensal),
      });
      notificar(`${campos.nome.trim()} cadastrado.`);
      definirCampos(NOVO);
      definirFormAberto(false);
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
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
    <div>
      <div className="pagina__eyebrow">Captação</div>
      <h1 className="pagina__titulo">Padrinhos</h1>
      <Rabisco className="pagina__onda" />
      <p className="pagina__lede">
        {estreita
          ? "Toque na linha para a ficha com todos os dados e as ações de cada criança."
          : " Clique em qualquer célula para editar; o menu abre a ficha com todas as crianças e as ações de cada uma."}
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>

      <form
        className="barra-acoes"
        onSubmit={(e) => {
          e.preventDefault();
          definirPagina(1);
          buscar();
        }}
      >
        <Entrada
          value={busca}
          onChange={(e) => definirBusca(e.target.value)}
          placeholder="Nome, WhatsApp ou email"
        />
        <Button type="submit" size="sm" variant="ghost">Buscar</Button>
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
        <span className="campo__dica">{padrinhos.total} padrinho(s)</span>

        {/* Na ponta oposta da linha: o CTA da pagina fica longe dos campos de
            busca, sem roubar uma linha so para ele. */}
        {(podeEditar || podeEnviarCartoes) && (
          <div className="barra-acoes__ponta">
            {podeEnviarCartoes && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => navegar("/padrinhos/envio-de-cartoes")}
                disabled={!edicaoAtiva}
              >
                Ir para envio de cartões
              </Button>
            )}
            {podeEditar && (
              <Button size="sm" onClick={() => definirFormAberto(true)} disabled={!edicaoAtiva}>
                Novo padrinho
              </Button>
            )}
          </div>
        )}
      </form>

      {formAberto && (
        <Modal titulo="Novo padrinho" aoFechar={() => !salvando && definirFormAberto(false)}>
          <form onSubmit={salvar}>
            <div className="linha-campos">
              <Entrada rotulo="Nome" value={campos.nome}
                onChange={(e) => definirCampos({ ...campos, nome: e.target.value })} required />
              <Entrada rotulo="WhatsApp" value={campos.whatsapp}
                onChange={(e) => definirCampos({ ...campos, whatsapp: e.target.value })} />
              <Entrada rotulo="Email" tipo="email" value={campos.email}
                onChange={(e) => definirCampos({ ...campos, email: e.target.value })} />
              <Entrada rotulo="Observações" value={campos.observacoes}
                onChange={(e) => definirCampos({ ...campos, observacoes: e.target.value })} />
              <Selecao
                rotulo="Já é membro Ser Feliz?"
                value={campos.membro_ser_feliz}
                onChange={(e) => definirCampos({ ...campos, membro_ser_feliz: e.target.value })}
              >
                <option value="">A perguntar</option>
                <option value="sim">Sim</option>
                <option value="nao">Não</option>
              </Selecao>
              <Selecao
                rotulo="Tem interesse em contribuir mensalmente?"
                value={campos.interesse_mensal}
                onChange={(e) => definirCampos({ ...campos, interesse_mensal: e.target.value })}
              >
                <option value="">A perguntar</option>
                <option value="sim">Sim</option>
                <option value="nao">Não</option>
              </Selecao>
            </div>
            <div className="barra-acoes barra-acoes--fim">
              <Button variant="secondary" type="submit" carregando={salvando}
                disabled={!campos.nome.trim()}>
                Salvar
              </Button>
              <Button variant="ghost" onClick={() => definirFormAberto(false)} disabled={salvando}>
                Cancelar
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

      {fichaAberta && (
        <FichaPadrinho
          padrinho={fichaAberta}
          aoFechar={() => definirFichaAbertaId(null)}
          podeEditar={podeEditar}
          podePagar={podePagar}
          podeExcluir={podeExcluir}
          iniciarLigando={abrirLigando}
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
            <table className={`planilha ${estreita ? "planilha--compacta" : ""}`}>
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
                    <tr
                      key={p.id}
                      /* No celular a linha inteira abre a ficha: o alvo vira a
                         faixa por toda a largura da tela, e nao so os tres
                         pontinhos do canto. So no celular — no desktop o clique
                         na celula e o que abre a edicao dela, e os dois nao
                         cabem no mesmo lugar.

                         O menu fica: e ele quem anuncia as acoes para quem
                         navega por teclado ou leitor de tela. A linha e atalho
                         de dedo, e por isso nao ganha `role` nem foco proprio
                         — seria um segundo caminho dizendo o mesmo na frente de
                         quem usa Tab. */
                      onClick={estreita ? () => abrirFicha(p.id) : undefined}
                    >
                      {/* No celular o nome vira texto, mesmo para quem pode
                          editar: a celula que vira campo ao toque abriria o
                          teclado em quem so queria rolar a lista. Edicao e no
                          computador. */}
                      <td>
                        {podeEditar && !estreita ? (
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
                              {podeEditar ? (
                                <CelulaEditavel
                                  valor={p.whatsapp}
                                  aoSalvar={(v) => salvarCampo(p, "whatsapp", v)}
                                />
                              ) : (
                                <span className="celula">{p.whatsapp ?? "—"}</span>
                              )}
                            </td>
                            <td>
                              {podeEditar ? (
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
                            podeEditar && {
                              rotulo: "Apadrinhar uma criança",
                              aoEscolher: () => abrirFicha(p.id, true),
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
    </div>
  );
}
