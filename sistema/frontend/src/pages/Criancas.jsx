import { useCallback, useEffect, useState } from "react";
import BotaoIcone from "../components/core/BotaoIcone.jsx";
import Button from "../components/core/Button.jsx";
import { Olho, Xis } from "../components/core/icones.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import CelulaEditavel from "../components/dados/CelulaEditavel.jsx";
import FichaCrianca from "../components/dados/FichaCrianca.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { listarEdicoes, listarInstituicoes } from "../services/cadastros.js";
import {
  apagarCrianca,
  criarCrianca,
  editarCrianca,
  editarEmLote,
  listarComissarios,
  listarCriancas,
  resumoInstituicoes,
} from "../services/criancas.js";
import { formatarData } from "../utils/dinheiro.js";
import ImportarLista from "./ImportarLista.jsx";

const POR_PAGINA = 100;
const TODAS = "todas";
const SEM_RESPONSAVEL = "sem";
const NOVA = { instituicao_id: "", codigo: "", nome: "", idade: "", sexo: "F" };

const SEXOS = [
  { valor: "F", rotulo: "F" },
  { valor: "M", rotulo: "M" },
];

export default function Criancas() {
  const { pode, edicaoAtiva } = useSessao();

  const [edicoes, definirEdicoes] = useState([]);
  const [edicaoId, definirEdicaoId] = useState(edicaoAtiva ?? "");
  const [instituicoes, definirInstituicoes] = useState([]);
  const [abas, definirAbas] = useState([]);
  const [abaAtiva, definirAbaAtiva] = useState(TODAS);

  const [criancas, definirCriancas] = useState({ itens: [], total: 0 });
  const [busca, definirBusca] = useState("");
  const [codigo, definirCodigo] = useState("");
  const [pagina, definirPagina] = useState(1);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");

  const [marcadas, definirMarcadas] = useState([]);

  // O time de comissarios da edicao. Uma instituicao e atendida por varios
  // deles, e a coluna do responsavel diz qual atende cada crianca.
  const [comissarios, definirComissarios] = useState([]);
  const [filtroComissario, definirFiltroComissario] = useState("");
  const [atribuindo, definirAtribuindo] = useState(false);

  const [formAberto, definirFormAberto] = useState(false);
  const [campos, definirCampos] = useState(NOVA);
  const [salvando, definirSalvando] = useState(false);
  const [importando, definirImportando] = useState(false);
  const [fichaAberta, definirFichaAberta] = useState(null);

  const podeEditar = pode("editar_criancas");

  useEffect(() => {
    let vivo = true;
    Promise.all([listarEdicoes(), listarInstituicoes()])
      .then(([eds, insts]) => {
        if (!vivo) return;
        definirEdicoes(eds);
        definirInstituicoes(insts);
        if (!edicaoId && eds.length) definirEdicaoId(eds[0].id);
      })
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // As abas mudam quando a edicao muda.
  useEffect(() => {
    if (!edicaoId) return;
    let vivo = true;
    resumoInstituicoes(edicaoId)
      .then((resumo) => {
        if (!vivo) return;
        definirAbas(resumo);
      })
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, [edicaoId]);

  // O time tambem muda com a edicao: comissario e vinculo por edicao.
  useEffect(() => {
    if (!edicaoId) return;
    let vivo = true;
    listarComissarios(edicaoId)
      .then((time) => vivo && definirComissarios(time))
      .catch(() => vivo && definirComissarios([]));
    return () => {
      vivo = false;
    };
  }, [edicaoId]);

  const buscar = useCallback(async () => {
    try {
      definirCriancas(
        await listarCriancas({
          edicao_id: edicaoId,
          instituicao_id: abaAtiva === TODAS ? "" : abaAtiva,
          comissario_id: filtroComissario === SEM_RESPONSAVEL ? "" : filtroComissario,
          sem_comissario: filtroComissario === SEM_RESPONSAVEL ? true : "",
          busca,
          codigo,
          pagina,
          por_pagina: POR_PAGINA,
        }),
      );
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoId, abaAtiva, filtroComissario, busca, codigo, pagina]);

  useEffect(() => {
    if (edicaoId) buscar();
  }, [edicaoId, abaAtiva, pagina, buscar]);

  async function recarregarAbas() {
    try {
      definirAbas(await resumoInstituicoes(edicaoId));
    } catch {
      // A planilha e o que importa; as abas atualizam na proxima troca.
    }
  }

  /** Salva uma celula e atualiza só aquela linha, sem recarregar a tabela. */
  async function salvarCampo(crianca, campo, valor) {
    const atualizada = await editarCrianca(crianca.id, { [campo]: valor });
    definirCriancas((atual) => ({
      ...atual,
      itens: atual.itens.map((c) => (c.id === crianca.id ? atualizada : c)),
    }));
    if (campo === "dia_evento_id") recarregarAbas();
  }

  /** O time da instituicao, como opcoes do seletor da coluna. */
  function opcoesComissario(instituicaoId) {
    return [
      // O mesmo texto da celula so-leitura: a coluna diz a mesma coisa para
      // quem edita e para quem so olha.
      { valor: "", rotulo: "sem responsável" },
      ...comissarios
        .filter((c) => c.instituicoes.includes(instituicaoId))
        .map((c) => ({ valor: c.id, rotulo: c.nome })),
    ];
  }

  /** Poe (ou tira) o responsavel das criancas marcadas, de uma vez. */
  async function atribuirMarcadas(comissarioId) {
    definirErro("");
    definirAtribuindo(true);
    try {
      const atualizadas = await editarEmLote({
        criancas: marcadas,
        comissario_id: comissarioId === SEM_RESPONSAVEL ? null : Number(comissarioId),
      });
      const porId = new Map(atualizadas.map((c) => [c.id, c]));
      definirCriancas((atual) => ({
        ...atual,
        itens: atual.itens.map((c) => porId.get(c.id) ?? c),
      }));
      const nome = comissarios.find((c) => String(c.id) === String(comissarioId))?.nome;
      definirSucesso(
        nome
          ? `${marcadas.length} criança(s) agora com ${nome}.`
          : `${marcadas.length} criança(s) sem responsável.`,
      );
      definirMarcadas([]);
      recarregarAbas();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirAtribuindo(false);
    }
  }

  async function remover(crianca) {
    definirErro("");
    try {
      await apagarCrianca(crianca.id);
      definirSucesso(`${crianca.nome} removida.`);
      buscar();
      recarregarAbas();
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function salvarNova(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      await criarCrianca({
        edicao_id: Number(edicaoId),
        instituicao_id: Number(campos.instituicao_id),
        codigo: campos.codigo.trim(),
        nome: campos.nome.trim(),
        idade: Number(campos.idade),
        sexo: campos.sexo,
      });
      definirSucesso(`${campos.nome.trim()} cadastrada.`);
      definirCampos(NOVA);
      definirFormAberto(false);
      buscar();
      recarregarAbas();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  const edicao = edicoes.find((e) => String(e.id) === String(edicaoId));
  const instituicoesDaCidade = instituicoes.filter((i) => i.cidade_id === edicao?.cidade_id);

  const totalGeral = abas.reduce((soma, a) => soma + a.criancas, 0);
  const totalPaginas = Math.max(1, Math.ceil(criancas.total / POR_PAGINA));

  function alternar(id) {
    definirMarcadas((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));
  }

  // Num lote de escolas diferentes so cabe quem atende TODAS elas: o seletor
  // do lote nao pode oferecer um nome que a conferencia do servidor vai negar.
  const escolasMarcadas = [
    ...new Set(
      criancas.itens.filter((c) => marcadas.includes(c.id)).map((c) => c.instituicao_id),
    ),
  ];
  const comissariosDoLote = comissarios.filter((c) =>
    escolasMarcadas.every((i) => c.instituicoes.includes(i)),
  );

  function marcarTodas() {
    definirMarcadas(
      marcadas.length === criancas.itens.length ? [] : criancas.itens.map((c) => c.id),
    );
  }

  if (importando) {
    return (
      <ImportarLista
        edicao={edicao}
        instituicoes={instituicoesDaCidade}
        aoTerminar={(quantas) => {
          definirImportando(false);
          if (quantas) definirSucesso(`${quantas} criança(s) importada(s).`);
          buscar();
          recarregarAbas();
        }}
      />
    );
  }

  return (
    <div>
      <div className="pagina__eyebrow">Dados sensíveis</div>
      <h1 className="pagina__titulo">Crianças</h1>
      <p className="pagina__lede">
        Uma aba por instituição. Clique em qualquer célula para editar — Enter salva e
        desce, Esc desfaz.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      <div className="barra-acoes">
        <Selecao
          value={edicaoId}
          onChange={(e) => {
            definirEdicaoId(e.target.value);
            definirAbaAtiva(TODAS);
            definirPagina(1);
            definirMarcadas([]);
          }}
        >
          {edicoes.map((e) => (
            <option key={e.id} value={e.id}>{e.nome}</option>
          ))}
        </Selecao>

        {pode("importar_listas") && (
          <Button size="sm" variant="ghost" onClick={() => definirImportando(true)} disabled={!edicao}>
            Importar lista
          </Button>
        )}
      </div>

      {/* Abas: uma por instituição, com o que falta em cada uma. */}
      {abas.length > 0 && (
        <div className="abas" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={abaAtiva === TODAS}
            className={`aba ${abaAtiva === TODAS ? "aba--ativa" : ""}`}
            onClick={() => {
              definirAbaAtiva(TODAS);
              definirPagina(1);
              definirMarcadas([]);
            }}
          >
            <span>Todas</span>
            <span className="aba__contagem">{totalGeral} crianças</span>
          </button>

          {abas.map((a) => (
            <button
              key={a.instituicao_id}
              type="button"
              role="tab"
              aria-selected={String(abaAtiva) === String(a.instituicao_id)}
              className={`aba ${String(abaAtiva) === String(a.instituicao_id) ? "aba--ativa" : ""}`}
              onClick={() => {
                definirAbaAtiva(a.instituicao_id);
                definirPagina(1);
                definirMarcadas([]);
              }}
              title={`${a.sem_padrinho} sem padrinho · ${a.sem_cartao} sem cartão`}
            >
              <span>
                {a.instituicao}
                {(a.sem_padrinho > 0 || !a.dia_evento) && <span className="aba__alerta" />}
              </span>
              <span className="aba__contagem">
                {a.criancas} ·{" "}
                {a.dia_evento ? formatarData(a.dia_evento) : "sem dia"}
              </span>
            </button>
          ))}
        </div>
      )}

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
          placeholder="Buscar por nome"
        />
        <Entrada
          value={codigo}
          onChange={(e) => definirCodigo(e.target.value)}
          placeholder="Código exato"
        />
        {comissarios.length > 0 && (
          <Selecao
            value={filtroComissario}
            onChange={(e) => {
              definirFiltroComissario(e.target.value);
              definirPagina(1);
              definirMarcadas([]);
            }}
            aria-label="Filtrar por comissário responsável"
          >
            <option value="">Todos os comissários</option>
            <option value={SEM_RESPONSAVEL}>Sem responsável</option>
            {comissarios.map((c) => (
              <option key={c.id} value={c.id}>{c.nome}</option>
            ))}
          </Selecao>
        )}
        <Button type="submit" size="sm" variant="ghost">Buscar</Button>
        {(busca || codigo) && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              definirBusca("");
              definirCodigo("");
              definirFiltroComissario("");
              definirPagina(1);
            }}
          >
            Limpar
          </Button>
        )}
        <span className="campo__dica">{criancas.total} nesta aba</span>

        {/* Na ponta oposta da linha: o CTA da pagina fica longe dos campos de
            busca, sem roubar uma linha so para ele. */}
        {podeEditar && (
          <div className="barra-acoes__ponta">
            <Button
              size="sm"
              onClick={() => {
                definirCampos({
                  ...NOVA,
                  instituicao_id:
                    abaAtiva !== TODAS ? abaAtiva : (instituicoesDaCidade[0]?.id ?? ""),
                });
                definirFormAberto(true);
              }}
              disabled={instituicoesDaCidade.length === 0}
            >
              Nova criança
            </Button>
          </div>
        )}
      </form>

      {formAberto && (
        <Modal titulo="Nova criança" aoFechar={() => !salvando && definirFormAberto(false)}>
          <form onSubmit={salvarNova}>
            <div className="linha-campos">
              <Selecao
                rotulo="Instituição"
                value={campos.instituicao_id}
                onChange={(e) => definirCampos({ ...campos, instituicao_id: e.target.value })}
                required
              >
                {instituicoesDaCidade.map((i) => (
                  <option key={i.id} value={i.id}>{i.nome}</option>
                ))}
              </Selecao>
              <Entrada rotulo="Código" value={campos.codigo}
                onChange={(e) => definirCampos({ ...campos, codigo: e.target.value })} required />
              <Entrada rotulo="Nome" value={campos.nome}
                onChange={(e) => definirCampos({ ...campos, nome: e.target.value })} required />
              <Entrada rotulo="Idade" tipo="number" min="0" max="21" value={campos.idade}
                onChange={(e) => definirCampos({ ...campos, idade: e.target.value })} required />
              <Selecao rotulo="Sexo" value={campos.sexo}
                onChange={(e) => definirCampos({ ...campos, sexo: e.target.value })}>
                <option value="F">Feminino</option>
                <option value="M">Masculino</option>
              </Selecao>
            </div>
            <div className="barra-acoes barra-acoes--fim">
              <Button variant="secondary" type="submit" carregando={salvando}>Salvar</Button>
              <Button variant="ghost" onClick={() => definirFormAberto(false)} disabled={salvando}>
                Cancelar
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {fichaAberta && (
        <FichaCrianca
          criancaId={fichaAberta}
          aoFechar={() => definirFichaAberta(null)}
          podeEditar={podeEditar}
          /* Troca so a linha mexida: recarregar a tabela inteira perderia a
             posicao de quem estava no meio da planilha. */
          aoMudar={(atualizada) =>
            definirCriancas((atual) => ({
              ...atual,
              itens: atual.itens.map((c) => (c.id === atualizada.id ? atualizada : c)),
            }))
          }
        />
      )}

      {carregando ? (
        <Carregando>Carregando crianças...</Carregando>
      ) : criancas.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhuma criança aqui"
          corpo={
            busca || codigo
              ? "Nenhum resultado para esta busca."
              : "Importe a lista que a instituição enviou."
          }
        />
      ) : (
        <>
          <div className="tabela-rolagem">
            <table className="planilha">
              {/* As larguras ficam aqui, e nao no conteudo: trocar de aba nao
                  move nenhuma coluna de lugar. */}
              <colgroup>
                {podeEditar && <col style={{ width: 34 }} />}
                <col style={{ width: 92 }} />
                <col />
                <col style={{ width: 64 }} />
                <col style={{ width: 58 }} />
                <col style={{ width: 112 }} />
                <col style={{ width: 190 }} />
                <col style={{ width: 150 }} />
                <col style={{ width: 84 }} />
                <col style={{ width: 72 }} />
                <col style={{ width: 72 }} />
                <col style={{ width: 82 }} />
                {podeEditar && <col style={{ width: 66 }} />}
              </colgroup>
              <thead>
                <tr>
                  {podeEditar && (
                    <th className="planilha__marcar">
                      <input
                        type="checkbox"
                        checked={marcadas.length === criancas.itens.length}
                        onChange={marcarTodas}
                        aria-label="Marcar todas"
                      />
                    </th>
                  )}
                  <th>Código</th>
                  <th>Nome</th>
                  <th>Idade</th>
                  <th>Sexo</th>
                  <th>Dia</th>
                  <th>Instituição</th>
                  <th title="Comissário responsável por esta criança. A instituição é atendida pelo time todo; aqui fica quem responde por ela.">
                    Comissário
                  </th>
                  <th title="Padrinho de cesta e de festa">Padrinhos</th>
                  <th title="Cartões digitalizados, de 2">Cartões</th>
                  <th>Kit</th>
                  <th>Check-in</th>
                  {podeEditar && <th className="planilha__acoes" />}
                </tr>
              </thead>
              <tbody>
                {criancas.itens.map((c) => (
                  <tr
                    key={c.id}
                    className={[
                      marcadas.includes(c.id) ? "planilha__linha--marcada" : "",
                      c.desistiu_em ? "planilha__linha--desistiu" : "",
                    ].filter(Boolean).join(" ")}
                    title={c.desistiu_em ? `${c.nome} desistiu de ir ao evento` : undefined}
                  >
                    {podeEditar && (
                      <td className="planilha__marcar">
                        <input
                          type="checkbox"
                          checked={marcadas.includes(c.id)}
                          onChange={() => alternar(c.id)}
                          aria-label={`Marcar ${c.nome}`}
                        />
                      </td>
                    )}
                    <td>
                      {podeEditar ? (
                        <CelulaEditavel
                          valor={c.codigo}
                          aoSalvar={(v) => salvarCampo(c, "codigo", v)}
                        />
                      ) : (
                        <span className="celula">{c.codigo}</span>
                      )}
                    </td>
                    <td>
                      {podeEditar ? (
                        <CelulaEditavel
                          valor={c.nome}
                          aoSalvar={(v) => salvarCampo(c, "nome", v)}
                        />
                      ) : (
                        <span className="celula">{c.nome}</span>
                      )}
                    </td>
                    <td>
                      {podeEditar ? (
                        <CelulaEditavel
                          valor={c.idade}
                          tipo="number"
                          aoSalvar={(v) => salvarCampo(c, "idade", Number(v))}
                        />
                      ) : (
                        <span className="celula">{c.idade}</span>
                      )}
                    </td>
                    <td>
                      {podeEditar ? (
                        <CelulaEditavel
                          valor={c.sexo}
                          opcoes={SEXOS}
                          aoSalvar={(v) => salvarCampo(c, "sexo", v)}
                        />
                      ) : (
                        <span className="celula">{c.sexo}</span>
                      )}
                    </td>
                    <td>
                      {/* Somente leitura: o dia e da instituicao, e se muda na
                          aba dela. Editar por crianca deixaria duas da mesma
                          escola em dias diferentes. */}
                      <span
                        className={`celula ${c.dia_evento ? "" : "celula--vazia"}`}
                        style={{ cursor: "default" }}
                        title="O dia vem da instituição"
                      >
                        {c.dia_evento ? formatarData(c.dia_evento) : "sem dia"}
                      </span>
                    </td>
                    <td>
                      <span className="celula" title={c.instituicao}>
                        {c.instituicao}
                      </span>
                    </td>
                    <td>
                      {/* Responsavel por ESTA crianca. Nao muda quem alcanca o
                          que: o time inteiro da instituicao continua vendo e
                          trabalhando a lista toda dela. */}
                      {podeEditar ? (
                        <CelulaEditavel
                          valor={c.comissario_id}
                          opcoes={opcoesComissario(c.instituicao_id)}
                          aoSalvar={(v) =>
                            salvarCampo(c, "comissario_id", v === "" ? null : Number(v))
                          }
                        />
                      ) : (
                        <span
                          className={`celula ${c.comissario ? "" : "celula--vazia"}`}
                          style={{ cursor: "default" }}
                          title={c.comissario ?? "Nenhum comissário responsável"}
                        >
                          {c.comissario ?? "sem responsável"}
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="celula" style={{ cursor: "default" }}>
                        <span
                          className={`marcador ${c.tem_padrinho_cesta ? "marcador--feito" : ""}`}
                          title={c.tem_padrinho_cesta ? "Tem padrinho de cesta" : "Sem padrinho de cesta"}
                        >
                          C
                        </span>
                        <span
                          className={`marcador ${c.tem_padrinho_festa ? "marcador--feito" : ""}`}
                          title={c.tem_padrinho_festa ? "Tem padrinho de festa" : "Sem padrinho de festa"}
                        >
                          F
                        </span>
                      </span>
                    </td>
                    <td>
                      <span className="celula" style={{ cursor: "default" }}>
                        <span
                          className={`marcador ${
                            c.cartoes >= 2 ? "marcador--feito" : c.cartoes > 0 ? "marcador--parcial" : ""
                          }`}
                        >
                          {c.cartoes}/2
                        </span>
                      </span>
                    </td>
                    <td>
                      <span className="celula" style={{ cursor: "default" }}>
                        <span
                          className={`marcador ${
                            c.kit_status === "entregue"
                              ? "marcador--feito"
                              : c.kit_status === "montado"
                                ? "marcador--parcial"
                                : ""
                          }`}
                        >
                          {c.kit_status.slice(0, 4)}
                        </span>
                      </span>
                    </td>
                    <td>
                      <span className="celula" style={{ cursor: "default" }}>
                        <span className={`marcador ${c.checkin_em ? "marcador--feito" : ""}`}>
                          {c.checkin_em ? "sim" : "não"}
                        </span>
                      </span>
                    </td>
                    {podeEditar && (
                      <td className="planilha__acoes">
                        <span className="acoes-icone">
                          <BotaoIcone
                            tamanho="sm"
                            titulo={`Ver ficha de ${c.nome}`}
                            onClick={() => definirFichaAberta(c.id)}
                          >
                            <Olho />
                          </BotaoIcone>
                          <BotaoIcone
                            tamanho="sm"
                            perigo
                            titulo={`Remover ${c.nome}`}
                            onClick={() => remover(c)}
                          >
                            <Xis />
                          </BotaoIcone>
                        </span>
                      </td>
                    )}
                  </tr>
                ))}
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

          {podeEditar && marcadas.length > 0 && (
            <div className="lote">
              <span className="lote__texto">{marcadas.length} marcada(s)</span>
              <Selecao
                value=""
                disabled={atribuindo}
                onChange={(e) => atribuirMarcadas(e.target.value)}
                aria-label="Atribuir as marcadas a um comissário"
              >
                <option value="" disabled>
                  {atribuindo ? "Atribuindo..." : "Atribuir a..."}
                </option>
                {comissariosDoLote.length === 0 && (
                  <option value="" disabled>
                    (nenhum comissário atende todas as escolas marcadas)
                  </option>
                )}
                {comissariosDoLote.map((c) => (
                  <option key={c.id} value={c.id}>{c.nome}</option>
                ))}
                <option value={SEM_RESPONSAVEL}>Sem responsável</option>
              </Selecao>
              <Button size="sm" variant="ghost" onClick={() => definirMarcadas([])}>
                Desmarcar
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
