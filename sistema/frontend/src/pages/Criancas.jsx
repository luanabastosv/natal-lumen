import { useCallback, useEffect, useMemo, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import CelulaEditavel from "../components/dados/CelulaEditavel.jsx";
import FichaCrianca from "../components/dados/FichaCrianca.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { listarDias, listarEdicoes, listarInstituicoes } from "../services/cadastros.js";
import {
  apagarCrianca,
  criarCrianca,
  editarCrianca,
  editarEmLote,
  listarCriancas,
  renumerar,
  resumoInstituicoes,
} from "../services/criancas.js";
import { formatarData } from "../utils/dinheiro.js";
import ImportarLista from "./ImportarLista.jsx";

const POR_PAGINA = 100;
const TODAS = "todas";
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
  const [dias, definirDias] = useState([]);
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
  const [diaDoLote, definirDiaDoLote] = useState("");

  const [formAberto, definirFormAberto] = useState(false);
  const [campos, definirCampos] = useState(NOVA);
  const [salvando, definirSalvando] = useState(false);
  const [importando, definirImportando] = useState(false);
  const [renumerando, definirRenumerando] = useState(false);
  const [fichaAberta, definirFichaAberta] = useState(null);
  const [sigla, definirSigla] = useState("");

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

  // Abas e dias mudam quando a edicao muda.
  useEffect(() => {
    if (!edicaoId) return;
    let vivo = true;
    Promise.all([resumoInstituicoes(edicaoId), listarDias(edicaoId)])
      .then(([resumo, ds]) => {
        if (!vivo) return;
        definirAbas(resumo);
        definirDias(ds);
      })
      .catch((e) => vivo && definirErro(e.message));
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
  }, [edicaoId, abaAtiva, busca, codigo, pagina]);

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

  async function aplicarDiaEmLote() {
    definirErro("");
    try {
      await editarEmLote({
        criancas: marcadas,
        dia_evento_id: diaDoLote ? Number(diaDoLote) : null,
        definir_dia: true,
      });
      definirSucesso(
        diaDoLote
          ? `${marcadas.length} criança(s) marcada(s) no dia.`
          : `${marcadas.length} criança(s) sem dia.`,
      );
      definirMarcadas([]);
      buscar();
      recarregarAbas();
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function aplicarRenumerar() {
    definirErro("");
    try {
      await renumerar({
        edicao_id: Number(edicaoId),
        instituicao_id: Number(abaAtiva),
        sigla: sigla.trim() || null,
      });
      definirSucesso("Códigos refeitos na ordem: meninas, idade, alfabética.");
      definirRenumerando(false);
      definirSigla("");
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

  const opcoesDia = useMemo(
    () => [
      { valor: "", rotulo: "sem dia" },
      ...dias.map((d) => ({ valor: d.id, rotulo: formatarData(d.data) })),
    ],
    [dias],
  );

  const totalGeral = abas.reduce((soma, a) => soma + a.criancas, 0);
  const totalPaginas = Math.max(1, Math.ceil(criancas.total / POR_PAGINA));

  function alternar(id) {
    definirMarcadas((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));
  }

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

        {podeEditar && (
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
        )}
        {pode("importar_listas") && (
          <Button size="sm" variant="ghost" onClick={() => definirImportando(true)} disabled={!edicao}>
            Importar lista
          </Button>
        )}
        {podeEditar && abaAtiva !== TODAS && (
          <Button size="sm" variant="ghost" onClick={() => definirRenumerando(true)}>
            Renumerar códigos
          </Button>
        )}
      </div>

      {renumerando && (
        <div className="painel painel--destaque">
          <h2 className="painel__titulo">
            Renumerar {abas.find((a) => String(a.instituicao_id) === String(abaAtiva))?.instituicao}
          </h2>
          <p className="campo__dica" style={{ marginTop: 0 }}>
            Os códigos são refeitos na ordem do projeto: <strong>meninas primeiro</strong>,
            depois por idade, depois em ordem alfabética. Use depois de corrigir idades
            ou sexos que vieram errados da planilha.
          </p>
          <Mensagem tipo="aviso">
            Os códigos vão <strong>mudar</strong>. Crachás já impressos e listas já
            distribuídas ficam desatualizados.
          </Mensagem>
          <div className="linha-campos">
            <Entrada
              rotulo="Sigla"
              value={sigla}
              onChange={(e) => definirSigla(e.target.value.toUpperCase())}
              maxLength={6}
              dica="Em branco mantém a sigla atual da instituição."
            />
          </div>
          <div className="barra-acoes barra-acoes--fim">
            <Button size="sm" onClick={aplicarRenumerar}>Renumerar</Button>
            <Button size="sm" variant="ghost" onClick={() => definirRenumerando(false)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

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
              title={`${a.sem_padrinho} sem padrinho · ${a.sem_cartao} sem cartão · ${a.sem_dia} sem dia`}
            >
              <span>
                {a.instituicao}
                {(a.sem_padrinho > 0 || a.sem_dia > 0) && <span className="aba__alerta" />}
              </span>
              <span className="aba__contagem">
                {a.criancas} · {a.sem_padrinho} sem padrinho
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
        <Button type="submit" size="sm" variant="ghost">Buscar</Button>
        {(busca || codigo) && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              definirBusca("");
              definirCodigo("");
              definirPagina(1);
            }}
          >
            Limpar
          </Button>
        )}
        <span className="campo__dica" style={{ marginTop: 0 }}>
          {criancas.total} nesta aba
        </span>
      </form>

      {formAberto && (
        <form className="painel" onSubmit={salvarNova}>
          <h2 className="painel__titulo">Nova criança</h2>
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
            <Button type="submit" carregando={salvando}>Salvar</Button>
            <Button variant="ghost" onClick={() => definirFormAberto(false)}>Cancelar</Button>
          </div>
        </form>
      )}

      {fichaAberta && (
        <FichaCrianca criancaId={fichaAberta} aoFechar={() => definirFichaAberta(null)} />
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
                    className={marcadas.includes(c.id) ? "planilha__linha--marcada" : ""}
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
                      {podeEditar ? (
                        <CelulaEditavel
                          valor={c.dia_evento_id}
                          opcoes={opcoesDia}
                          aoSalvar={(v) => salvarCampo(c, "dia_evento_id", v ? Number(v) : null)}
                        />
                      ) : (
                        <span className="celula">
                          {c.dia_evento ? formatarData(c.dia_evento) : "—"}
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="celula" title={c.instituicao}>
                        {c.instituicao}
                      </span>
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
                        <button
                          type="button"
                          className="ver"
                          onClick={() => definirFichaAberta(c.id)}
                          title={`Ver ${c.nome}`}
                          aria-label={`Ver ficha de ${c.nome}`}
                        >
                          {/* Olho desenhado em SVG: nao depende de fonte de icones. */}
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path
                              d="M1.5 12S5 5.5 12 5.5 22.5 12 22.5 12 19 18.5 12 18.5 1.5 12 1.5 12Z"
                              stroke="currentColor" strokeWidth="2" strokeLinejoin="round"
                            />
                            <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="2" />
                          </svg>
                        </button>
                        <button
                          type="button"
                          className="remover"
                          onClick={() => remover(c)}
                          title={`Remover ${c.nome}`}
                          aria-label={`Remover ${c.nome}`}
                        >
                          ×
                        </button>
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
              <select
                value={diaDoLote}
                onChange={(e) => definirDiaDoLote(e.target.value)}
                aria-label="Dia do evento"
              >
                <option value="">Sem dia</option>
                {dias.map((d) => (
                  <option key={d.id} value={d.id}>{formatarData(d.data)}</option>
                ))}
              </select>
              <Button size="sm" onClick={aplicarDiaEmLote}>Aplicar dia</Button>
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
