import { useCallback, useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { listarEdicoes } from "../services/cadastros.js";
import { listarCriancas } from "../services/criancas.js";
import {
  apagarApadrinhamento,
  criarApadrinhamento,
  criarPadrinho,
  listarPadrinhos,
} from "../services/padrinhos.js";
import { dinheiro } from "../utils/dinheiro.js";

const POR_PAGINA = 25;
const NOVO = { nome: "", whatsapp: "", email: "", observacoes: "" };

export default function Padrinhos() {
  const { pode, edicaoAtiva } = useSessao();

  const [padrinhos, definirPadrinhos] = useState({ itens: [], total: 0 });
  const [edicoes, definirEdicoes] = useState([]);
  const [edicaoId, definirEdicaoId] = useState(edicaoAtiva ?? "");
  const [busca, definirBusca] = useState("");
  const [pagina, definirPagina] = useState(1);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");

  const [formAberto, definirFormAberto] = useState(false);
  const [campos, definirCampos] = useState(NOVO);
  const [salvando, definirSalvando] = useState(false);

  // Painel para ligar este padrinho a uma crianca.
  const [ligando, definirLigando] = useState(null);
  const [codigoCrianca, definirCodigoCrianca] = useState("");
  const [criancaAchada, definirCriancaAchada] = useState(null);
  const [tipo, definirTipo] = useState("cesta");

  useEffect(() => {
    let vivo = true;
    listarEdicoes()
      .then((eds) => {
        if (!vivo) return;
        definirEdicoes(eds);
        if (!edicaoId && eds.length) definirEdicaoId(eds[0].id);
      })
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const buscar = useCallback(async () => {
    try {
      definirPadrinhos(
        await listarPadrinhos({ edicao_id: edicaoId, busca, pagina, por_pagina: POR_PAGINA }),
      );
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoId, busca, pagina]);

  useEffect(() => {
    if (edicaoId) buscar();
  }, [edicaoId, pagina, buscar]);

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      await criarPadrinho({
        edicao_id: Number(edicaoId),
        nome: campos.nome.trim(),
        whatsapp: campos.whatsapp.trim() || null,
        email: campos.email.trim() || null,
        observacoes: campos.observacoes.trim() || null,
      });
      definirSucesso(`${campos.nome.trim()} cadastrado.`);
      definirCampos(NOVO);
      definirFormAberto(false);
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function procurarCrianca() {
    definirErro("");
    definirCriancaAchada(null);
    try {
      const resultado = await listarCriancas({ codigo: codigoCrianca.trim() });
      if (resultado.itens.length === 0) {
        definirErro("Nenhuma criança com este código nas suas edições.");
      } else {
        definirCriancaAchada(resultado.itens[0]);
      }
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function ligar() {
    definirErro("");
    try {
      await criarApadrinhamento({
        crianca_id: criancaAchada.id,
        padrinho_id: ligando.id,
        tipo,
      });
      definirSucesso(`${criancaAchada.nome} ligada a ${ligando.nome}.`);
      definirLigando(null);
      definirCriancaAchada(null);
      definirCodigoCrianca("");
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function desligar(apadrinhamento) {
    definirErro("");
    try {
      await apagarApadrinhamento(apadrinhamento.id);
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  const totalPaginas = Math.max(1, Math.ceil(padrinhos.total / POR_PAGINA));

  return (
    <div>
      <div className="pagina__eyebrow">Captação</div>
      <h1 className="pagina__titulo">Padrinhos</h1>
      <p className="pagina__lede">
        Cada padrinho pertence a uma edição e pode apadrinhar várias crianças, inclusive
        de outra cidade. Do lado do padrinho, a criança aparece só pelo primeiro nome e
        pela idade.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      <form
        className="painel"
        onSubmit={(e) => {
          e.preventDefault();
          definirPagina(1);
          buscar();
        }}
      >
        <div className="linha-campos">
          <Selecao
            rotulo="Edição"
            value={edicaoId}
            onChange={(e) => {
              definirEdicaoId(e.target.value);
              definirPagina(1);
            }}
          >
            {edicoes.map((e) => (
              <option key={e.id} value={e.id}>{e.nome}</option>
            ))}
          </Selecao>
          <Entrada
            rotulo="Buscar"
            value={busca}
            onChange={(e) => definirBusca(e.target.value)}
            dica="Nome, WhatsApp ou email."
          />
        </div>
        <Button type="submit" size="sm">Filtrar</Button>
      </form>

      {pode("editar_padrinhos") && (
        <div className="barra-acoes">
          <Button onClick={() => definirFormAberto(true)} disabled={!edicaoId}>
            Novo padrinho
          </Button>
          <span className="campo__dica" style={{ marginTop: 0 }}>
            {padrinhos.total} padrinho(s)
          </span>
        </div>
      )}

      {formAberto && (
        <form className="painel" onSubmit={salvar}>
          <h2 className="painel__titulo">Novo padrinho</h2>
          <div className="linha-campos">
            <Entrada rotulo="Nome" value={campos.nome}
              onChange={(e) => definirCampos({ ...campos, nome: e.target.value })} required />
            <Entrada rotulo="WhatsApp" value={campos.whatsapp}
              onChange={(e) => definirCampos({ ...campos, whatsapp: e.target.value })} />
            <Entrada rotulo="Email" tipo="email" value={campos.email}
              onChange={(e) => definirCampos({ ...campos, email: e.target.value })} />
            <Entrada rotulo="Observações" value={campos.observacoes}
              onChange={(e) => definirCampos({ ...campos, observacoes: e.target.value })} />
          </div>
          <div className="barra-acoes barra-acoes--fim">
            <Button type="submit" carregando={salvando} disabled={!campos.nome.trim()}>Salvar</Button>
            <Button variant="ghost" onClick={() => definirFormAberto(false)}>Cancelar</Button>
          </div>
        </form>
      )}

      {ligando && (
        <div className="painel painel--destaque">
          <h2 className="painel__titulo">Apadrinhar uma criança · {ligando.nome}</h2>
          <p className="campo__dica" style={{ marginTop: 0 }}>
            Busque pelo código da criança. A busca alcança qualquer instituição das suas
            edições e fica registrada.
          </p>
          <div className="linha-campos">
            <Entrada
              rotulo="Código da criança"
              value={codigoCrianca}
              onChange={(e) => definirCodigoCrianca(e.target.value)}
            />
            <Selecao rotulo="Tipo" value={tipo} onChange={(e) => definirTipo(e.target.value)}>
              <option value="cesta">Cesta</option>
              <option value="festa">Festa</option>
            </Selecao>
          </div>

          {criancaAchada && (
            <Mensagem tipo="sucesso">
              <strong>{criancaAchada.nome}</strong>, {criancaAchada.idade} anos ·{" "}
              {criancaAchada.instituicao}
            </Mensagem>
          )}

          <div className="barra-acoes barra-acoes--fim">
            {!criancaAchada ? (
              <Button size="sm" onClick={procurarCrianca} disabled={!codigoCrianca.trim()}>
                Procurar
              </Button>
            ) : (
              <Button size="sm" onClick={ligar}>Confirmar apadrinhamento</Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                definirLigando(null);
                definirCriancaAchada(null);
                definirCodigoCrianca("");
              }}
            >
              Fechar
            </Button>
          </div>
        </div>
      )}

      {carregando ? (
        <Carregando>Carregando padrinhos...</Carregando>
      ) : padrinhos.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhum padrinho ainda"
          corpo="Cadastre os padrinhos captados e ligue cada um às crianças."
        />
      ) : (
        <>
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Contato</th>
                  <th>Apadrinhamentos</th>
                  <th>Combinado</th>
                  <th>Pago</th>
                  {pode("editar_padrinhos") && <th />}
                </tr>
              </thead>
              <tbody>
                {padrinhos.itens.map((p) => (
                  <tr key={p.id}>
                    <td>
                      {p.nome}
                      <br />
                      <span className="etiqueta etiqueta--neutra">{p.cidade} {p.ano ?? ""}</span>
                    </td>
                    <td>
                      {p.whatsapp ?? "—"}
                      {p.email && <><br />{p.email}</>}
                    </td>
                    <td>
                      {p.apadrinhamentos.length === 0
                        ? "—"
                        : p.apadrinhamentos.map((a) => (
                            <div key={a.id} className="detalhe-vinculo">
                              <span className="detalhe-vinculo__edicao">
                                {a.crianca_primeiro_nome}, {a.crianca_idade}
                              </span>
                              <span className="etiqueta etiqueta--neutra">{a.tipo}</span>
                              <span
                                className={`etiqueta ${a.pago ? "etiqueta--ok" : "etiqueta--espera"}`}
                              >
                                {a.pago ? "pago" : "a pagar"}
                              </span>
                              {pode("editar_padrinhos") && !a.pago && (
                                <Button size="sm" variant="ghost" onClick={() => desligar(a)}>
                                  Desfazer
                                </Button>
                              )}
                            </div>
                          ))}
                    </td>
                    <td>{dinheiro(p.total_combinado)}</td>
                    <td>{dinheiro(p.total_pago)}</td>
                    {pode("editar_padrinhos") && (
                      <td>
                        <Button size="sm" variant="ghost" onClick={() => definirLigando(p)}>
                          Apadrinhar
                        </Button>
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
        </>
      )}
    </div>
  );
}
