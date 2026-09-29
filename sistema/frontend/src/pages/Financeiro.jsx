import { useCallback, useEffect, useRef, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import BotaoIcone from "../components/core/BotaoIcone.jsx";
import Button from "../components/core/Button.jsx";
import MenuAcoes from "../components/core/MenuAcoes.jsx";
import { Baixar } from "../components/core/icones.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import Numero from "../components/feedback/Numero.jsx";
import NovoRecebimento from "../components/dados/NovoRecebimento.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import {
  ROTULO_CATEGORIA,
  apagarRecebimento,
  apagarSaida,
  baixarComprovanteDoRecebimento,
  criarSaida,
  editarRecebimento,
  listarRecebimentos,
  listarSaidas,
  subirComprovanteDoRecebimento,
} from "../services/financeiro.js";
import {
  apagarPagamento,
  baixarComprovante,
  editarPagamento,
  subirComprovante,
} from "../services/padrinhos.js";
import { dinheiro, formatarData } from "../utils/dinheiro.js";

const hoje = () => new Date().toISOString().slice(0, 10);

const NOVA_SAIDA = {
  descricao: "", categoria: "", quantidade: "1",
  valor_total: "", fornecedor: "", data: hoje(),
};

const SAIDAS = "saidas";
const RECEBIMENTOS = "recebimentos";

const SEM_SAIDAS = { itens: [], total: 0, total_gasto: "0.00", por_categoria: {} };
const SEM_RECEBIMENTOS = {
  itens: [], total: 0, total_recebido: "0.00", por_categoria: {},
  apadrinhamento: "0.00", pagamentos: 0, a_conferir: "0.00", sem_comprovante: 0,
};

const SEM_FILTRO = { categoria: "", conferido: "", comprovante: "" };

/** O caixa da edição: o que saiu e o que entrou.
 *
 * Duas abas porque são dois lançamentos diferentes, e duas permissões também:
 * a estrutura lança saídas, a coordenação lança e confere o que entra. Quem tem
 * só uma delas vê só a sua aba, e a faixa de abas nem aparece. O saldo só
 * existe para quem alcança as duas metades: com meia conta na mão, um saldo
 * seria um número errado com cara de certo.
 *
 * **Os pagamentos dos padrinhos são linhas da lista de recebimentos**, e não
 * uma tela à parte: quem fecha o caixa quer ver todo o dinheiro que entrou de
 * uma vez. A linha é o próprio pagamento, lido de lado — a categoria dela vem
 * do que ele quita, e as ações dela (conferir, comprovante, remover) batem em
 * `/pagamentos`. `fonte` é o que diz em qual endereço cada linha responde.
 */
export default function Financeiro() {
  // A edicao vem da lateral: e a mesma para o sistema inteiro.
  const { edicaoAtiva, pode } = useSessao();

  const podeSaidas = pode("gerenciar_compras");
  const podeRecebimentos = pode("registrar_pagamentos");

  const [aba, definirAba] = useState(podeSaidas ? SAIDAS : RECEBIMENTOS);
  const [saidas, definirSaidas] = useState(SEM_SAIDAS);
  const [recebimentos, definirRecebimentos] = useState(SEM_RECEBIMENTOS);
  const [filtros, definirFiltros] = useState(SEM_FILTRO);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const notificar = useNotificar();

  const [modal, definirModal] = useState(null);
  const [saida, definirSaida] = useState(NOVA_SAIDA);
  const [salvando, definirSalvando] = useState(false);

  // Um seletor de arquivo para a tela inteira, e nao um por linha: qual linha
  // recebe o arquivo e uma escolha de antes de abrir a janela do sistema.
  const seletorArquivo = useRef(null);
  const [alvo, definirAlvo] = useState(null);
  const [subindo, definirSubindo] = useState("");

  const chave = (linha) => `${linha.fonte}-${linha.id}`;

  const buscar = useCallback(async () => {
    try {
      // Cada metade so e pedida por quem a alcanca: pedir a outra voltaria 403
      // e a tela inteira viraria um erro por causa de uma aba que nem existe
      // para esta pessoa.
      const [s, r] = await Promise.all([
        podeSaidas ? listarSaidas({ edicao_id: edicaoAtiva }) : SEM_SAIDAS,
        podeRecebimentos
          ? listarRecebimentos({ edicao_id: edicaoAtiva, ...filtros })
          : SEM_RECEBIMENTOS,
      ]);
      definirSaidas(s);
      definirRecebimentos(r);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoAtiva, podeSaidas, podeRecebimentos, filtros]);

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer: os
    // lancamentos so chegam depois do await, e nao daria para derivar no render.
    // eslint-disable-next-line react/set-state-in-effect
    if (edicaoAtiva) buscar();
  }, [edicaoAtiva, buscar]);

  function trocarAba(nova) {
    definirAba(nova);
    definirModal(null);
    definirErro("");
  }

  const saldo = Number(recebimentos.total_recebido) - Number(saidas.total_gasto);
  const filtrando = Object.values(filtros).some(Boolean);

  /** Onde cada acao da linha bate. A linha de apadrinhamento e um pagamento;
   *  a de doacao, um recebimento. Mesma acao, endereco diferente. */
  function rotas(linha) {
    const dePagamento = linha.fonte === "pagamento";
    return {
      conferir: dePagamento ? editarPagamento : editarRecebimento,
      baixar: dePagamento ? baixarComprovante : baixarComprovanteDoRecebimento,
      subir: dePagamento ? subirComprovante : subirComprovanteDoRecebimento,
      apagar: dePagamento ? apagarPagamento : apagarRecebimento,
    };
  }

  async function salvarSaida(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      await criarSaida({
        edicao_id: Number(edicaoAtiva),
        descricao: saida.descricao.trim(),
        categoria: saida.categoria.trim() || null,
        quantidade: Number(saida.quantidade),
        valor_total: saida.valor_total,
        fornecedor: saida.fornecedor.trim() || null,
        data: saida.data,
      });
      notificar("Saída registrada.");
      definirSaida(NOVA_SAIDA);
      definirModal(null);
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function removerSaida(item) {
    definirErro("");
    try {
      await apagarSaida(item.id);
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function alternarConferido(linha) {
    definirErro("");
    try {
      await rotas(linha).conferir(linha.id, { conferido: !linha.conferido });
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function removerLinha(linha) {
    definirErro("");
    try {
      await rotas(linha).apagar(linha.id);
      notificar(
        linha.fonte === "pagamento"
          ? "Pagamento removido. Os apadrinhamentos voltaram a ficar em aberto."
          : "Recebimento removido.",
      );
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function baixarArquivo(linha) {
    definirErro("");
    try {
      await rotas(linha).baixar(linha.id);
    } catch (e) {
      definirErro(e.message);
    }
  }

  function pedirArquivo(linha) {
    definirAlvo(linha);
    // Zera antes de abrir: sem isso, escolher o MESMO arquivo de novo (depois
    // de um erro, por exemplo) nao dispara onChange.
    seletorArquivo.current.value = "";
    seletorArquivo.current.click();
  }

  async function aoEscolherArquivo(evento) {
    const arquivo = evento.target.files?.[0];
    if (!arquivo || !alvo) return;

    definirErro("");
    definirSubindo(chave(alvo));
    try {
      await rotas(alvo).subir(alvo.id, arquivo);
      notificar("Comprovante guardado.");
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSubindo("");
      definirAlvo(null);
    }
  }

  return (
    <div>
      <div className="pagina__cabecalho">
        <div className="pagina__texto">
          <div className="pagina__eyebrow">Edição</div>
          <h1 className="pagina__titulo">Financeiro</h1>
          <Rabisco className="pagina__onda" />
          <p className="pagina__lede">
            Todo o dinheiro da edição num lugar: o que a equipe gastou, o que os
            padrinhos pagaram e as doações que chegam soltas.
          </p>
        </div>

        <div className="pagina__acoes">
          {/* Um botao cheio por tela. Os dois nunca aparecem juntos: qual
              existe depende da aba aberta. */}
          <Button
            onClick={() => definirModal(aba)}
            disabled={!edicaoAtiva || carregando}
          >
            {aba === SAIDAS ? "Nova saída" : "Novo recebimento"}
          </Button>
        </div>
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {/* Fora da tabela e escondido: e o mesmo seletor para todas as linhas. */}
      <input
        ref={seletorArquivo}
        type="file"
        accept="image/jpeg,image/png,application/pdf"
        onChange={aoEscolherArquivo}
        hidden
      />

      {modal === SAIDAS && (
        <Modal titulo="Nova saída" aoFechar={() => !salvando && definirModal(null)}>
          <form onSubmit={salvarSaida}>
            <Entrada rotulo="Descrição" value={saida.descricao}
              onChange={(e) => definirSaida({ ...saida, descricao: e.target.value })} required />
            <Entrada rotulo="Categoria" value={saida.categoria}
              onChange={(e) => definirSaida({ ...saida, categoria: e.target.value })}
              dica="Ex.: cesta, presente, higiene, estrutura, transporte" />
            <div className="linha-campos">
              <Entrada rotulo="Quantidade" tipo="number" min="1" value={saida.quantidade}
                onChange={(e) => definirSaida({ ...saida, quantidade: e.target.value })}
                dica="1 no gasto que não se conta por unidade." required />
              <Entrada rotulo="Valor total" tipo="number" step="0.01" value={saida.valor_total}
                onChange={(e) => definirSaida({ ...saida, valor_total: e.target.value })} required />
            </div>
            <div className="linha-campos">
              <Entrada rotulo="Fornecedor" value={saida.fornecedor}
                onChange={(e) => definirSaida({ ...saida, fornecedor: e.target.value })} />
              <Entrada rotulo="Data" tipo="date" value={saida.data}
                onChange={(e) => definirSaida({ ...saida, data: e.target.value })} required />
            </div>
            <div className="barra-acoes barra-acoes--fim">
              <Button variant="secondary" type="submit" carregando={salvando}>Salvar</Button>
              <Button variant="ghost" onClick={() => definirModal(null)} disabled={salvando}>
                Cancelar
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {modal === RECEBIMENTOS && (
        // `grande`: a lista do que o dinheiro quita cresce com o padrinho
        // escolhido, e uma janela que muda de altura pula embaixo do ponteiro.
        <Modal titulo="Novo recebimento" tamanho="grande" aoFechar={() => definirModal(null)}>
          <NovoRecebimento
            edicaoId={edicaoAtiva}
            aoFechar={() => definirModal(null)}
            aoRegistrar={buscar}
          />
        </Modal>
      )}

      {carregando ? (
        <Carregando tela>Somando o caixa da edição...</Carregando>
      ) : (
        <>
          {/* A conta da edicao, antes das abas: e a resposta que a coordenacao
              vem buscar aqui, e ela nao muda quando se troca de aba. */}
          <div className="numeros">
            {podeRecebimentos && (
              <Numero
                rotulo="Recebido"
                valor={dinheiro(recebimentos.total_recebido)}
                moeda
                nota={`${dinheiro(recebimentos.apadrinhamento)} de apadrinhamento em ${recebimentos.pagamentos} pagamento(s)`}
              />
            )}
            {podeSaidas && (
              <Numero
                rotulo="Saídas"
                valor={dinheiro(saidas.total_gasto)}
                moeda
                nota={`${saidas.total} lançamento(s)`}
              />
            )}
            {podeSaidas && podeRecebimentos && (
              <Numero
                rotulo="Saldo"
                valor={dinheiro(saldo)}
                moeda
                negativo={saldo < 0}
                nota={saldo < 0 ? "a edição gastou mais do que recebeu" : "recebido menos saídas"}
              />
            )}
          </div>

          {/* Com uma aba so, a faixa nao aparece: quem tem uma permissao das
              duas nao precisa saber que existe uma metade que ele nao alcanca. */}
          {podeSaidas && podeRecebimentos && (
            <div className="abas" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={aba === SAIDAS}
                className={`aba ${aba === SAIDAS ? "aba--ativa" : ""}`}
                onClick={() => trocarAba(SAIDAS)}
              >
                <span>Saídas</span>
                <span className="aba__contagem">{dinheiro(saidas.total_gasto)}</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={aba === RECEBIMENTOS}
                className={`aba ${aba === RECEBIMENTOS ? "aba--ativa" : ""}`}
                onClick={() => trocarAba(RECEBIMENTOS)}
              >
                <span>Recebimentos</span>
                <span className="aba__contagem">{dinheiro(recebimentos.total_recebido)}</span>
              </button>
            </div>
          )}

          <div role="tabpanel" aria-label={aba === SAIDAS ? "Saídas" : "Recebimentos"}>
            {aba === SAIDAS ? (
              <>
                {Object.keys(saidas.por_categoria).length > 0 && (
                  <div className="painel">
                    <h2 className="painel__titulo">Gasto por categoria</h2>
                    <div className="marcaveis">
                      {Object.entries(saidas.por_categoria).map(([categoria, valor]) => (
                        <span key={categoria} className="marcavel">
                          {categoria}: <strong>{dinheiro(valor)}</strong>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {saidas.itens.length === 0 ? (
                  <EmptyState
                    titulo="Nenhuma saída registrada"
                    corpo="Registre aqui o que a edição gasta: cestas, presentes, estrutura, transporte."
                  />
                ) : (
                  <div className="tabela-rolagem">
                    <table className="tabela">
                      <thead>
                        <tr>
                          <th>Descrição</th><th>Categoria</th><th>Qtd</th>
                          <th>Valor</th><th>Fornecedor</th><th>Data</th><th>Por</th>
                          <th className="tabela__acoes" />
                        </tr>
                      </thead>
                      <tbody>
                        {saidas.itens.map((c) => (
                          <tr key={c.id}>
                            <td>{c.descricao}</td>
                            <td>{c.categoria ?? "—"}</td>
                            <td>{c.quantidade}</td>
                            <td>{dinheiro(c.valor_total)}</td>
                            <td>{c.fornecedor ?? "—"}</td>
                            <td>{formatarData(c.data)}</td>
                            <td>{c.responsavel ?? "—"}</td>
                            <td className="tabela__acoes">
                              <MenuAcoes
                                titulo={`Ações de ${c.descricao}`}
                                itens={[
                                  { rotulo: "Remover", perigo: true, aoEscolher: () => removerSaida(c) },
                                ]}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : (
              <>
                <div className="painel">
                  <h2 className="painel__titulo">De onde vem o que entrou</h2>
                  <div className="marcaveis">
                    {Object.entries(recebimentos.por_categoria).map(([categoria, valor]) => (
                      <span key={categoria} className="marcavel">
                        {ROTULO_CATEGORIA[categoria] ?? categoria}:{" "}
                        <strong>{dinheiro(valor)}</strong>
                      </span>
                    ))}
                  </div>
                  {/* Os dois numeros que pedem acao, e nao so somam. */}
                  <p className="campo__dica">
                    {Number(recebimentos.a_conferir) > 0
                      ? `${dinheiro(recebimentos.a_conferir)} ainda não conferido`
                      : "Tudo conferido"}
                    {" · "}
                    {recebimentos.sem_comprovante > 0
                      ? `${recebimentos.sem_comprovante} linha(s) sem comprovante`
                      : "todas as linhas com comprovante"}
                  </p>
                </div>

                <div className="barra-acoes">
                  <Selecao
                    aria-label="Filtrar por categoria"
                    value={filtros.categoria}
                    onChange={(e) => definirFiltros({ ...filtros, categoria: e.target.value })}
                  >
                    <option value="">Todas as categorias</option>
                    {/* As derivadas tambem filtram: sao elas que aparecem na
                        lista, e "Apadrinhamento" sozinho e o pagamento que
                        quita cesta e festa juntas. */}
                    {Object.entries(ROTULO_CATEGORIA).map(([valor, rotulo]) => (
                      <option key={valor} value={valor}>{rotulo}</option>
                    ))}
                  </Selecao>
                  <Selecao
                    aria-label="Filtrar por conferência"
                    value={filtros.conferido}
                    onChange={(e) => definirFiltros({ ...filtros, conferido: e.target.value })}
                  >
                    <option value="">Conferidos e não conferidos</option>
                    <option value="false">A conferir</option>
                    <option value="true">Conferidos</option>
                  </Selecao>
                  <Selecao
                    aria-label="Filtrar por comprovante"
                    value={filtros.comprovante}
                    onChange={(e) => definirFiltros({ ...filtros, comprovante: e.target.value })}
                  >
                    <option value="">Com e sem comprovante</option>
                    <option value="false">Falta o comprovante</option>
                    <option value="true">Comprovante guardado</option>
                  </Selecao>
                  {filtrando && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => definirFiltros(SEM_FILTRO)}
                    >
                      Limpar filtros
                    </Button>
                  )}
                  <span className="campo__dica" style={{ marginTop: 0 }}>
                    {recebimentos.total} linha(s)
                    {recebimentos.itens.length < recebimentos.total &&
                      ` · mostrando as ${recebimentos.itens.length} mais recentes`}
                  </span>
                </div>

                {recebimentos.itens.length === 0 ? (
                  <EmptyState
                    titulo={filtrando ? "Nada com esses filtros" : "Nada recebido ainda"}
                    corpo={
                      filtrando
                        ? "Limpe os filtros para ver a lista inteira."
                        : "O pagamento de um padrinho aparece aqui sozinho, assim que for registrado. Doação e patrocínio entram pelo botão acima."
                    }
                  />
                ) : (
                  <div className="tabela-rolagem">
                    <table className="tabela tabela--larga">
                      <caption className="tabela-dica">
                        Arraste a lista para o lado para ver todas as colunas.
                      </caption>
                      <thead>
                        <tr>
                          <th>O que entrou</th>
                          <th>De quem</th>
                          <th>Categoria</th>
                          <th>Valor</th>
                          <th>Forma</th>
                          <th>Data</th>
                          <th>Comprovante</th>
                          <th>Situação</th>
                          <th>Por</th>
                          <th className="tabela__acoes" />
                        </tr>
                      </thead>
                      <tbody>
                        {recebimentos.itens.map((l) => (
                          <tr key={chave(l)}>
                            <td title={l.observacoes ?? undefined}>{l.descricao}</td>
                            <td>{l.quem ?? "—"}</td>
                            <td>{ROTULO_CATEGORIA[l.categoria] ?? l.categoria}</td>
                            <td>{dinheiro(l.valor)}</td>
                            <td>{l.forma ?? "—"}</td>
                            <td>{formatarData(l.data)}</td>
                            <td>
                              {l.tem_comprovante ? (
                                <span className="acoes-icone">
                                  <BotaoIcone
                                    tamanho="sm"
                                    titulo={`Baixar o comprovante de ${l.quem ?? l.descricao}`}
                                    onClick={() => baixarArquivo(l)}
                                    carregando={subindo === chave(l)}
                                  >
                                    <Baixar />
                                  </BotaoIcone>
                                  {/* O Drive e copia, nao substituto: aparece
                                      so quando existe. */}
                                  {l.comprovante_drive_link && (
                                    <a
                                      href={l.comprovante_drive_link}
                                      target="_blank"
                                      rel="noreferrer"
                                    >
                                      Drive
                                    </a>
                                  )}
                                </span>
                              ) : (
                                <span className="etiqueta etiqueta--espera">
                                  {subindo === chave(l) ? "Subindo..." : "Falta"}
                                </span>
                              )}
                            </td>
                            <td>
                              <span
                                className={`etiqueta ${l.conferido ? "etiqueta--ok" : "etiqueta--espera"}`}
                              >
                                {l.conferido ? "Conferido" : "A conferir"}
                              </span>
                            </td>
                            {/* Quem lancou. A linha de apadrinhamento traz quem
                                registrou o pagamento — pode ter sido pela ficha
                                do padrinho, e nao por esta tela. */}
                            <td>{l.responsavel ?? "—"}</td>
                            <td className="tabela__acoes">
                              <MenuAcoes
                                titulo={`Ações de ${l.descricao}`}
                                itens={[
                                  {
                                    rotulo: l.tem_comprovante
                                      ? "Trocar comprovante"
                                      : "Subir comprovante",
                                    disabled: subindo === chave(l),
                                    aoEscolher: () => pedirArquivo(l),
                                  },
                                  {
                                    rotulo: l.conferido ? "Desmarcar" : "Conferir",
                                    aoEscolher: () => alternarConferido(l),
                                  },
                                  {
                                    rotulo: "Remover",
                                    perigo: true,
                                    aoEscolher: () => removerLinha(l),
                                  },
                                ]}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
