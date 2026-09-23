import { useCallback, useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import {
  apagarPagamento,
  criarPagamento,
  editarPagamento,
  listarPadrinhos,
  listarPagamentos,
} from "../services/padrinhos.js";
import { dinheiro, formatarData } from "../utils/dinheiro.js";

const hoje = () => new Date().toISOString().slice(0, 10);
const NOVO = { padrinho_id: "", valor: "", data: hoje(), forma: "pix", apadrinhamentos: [] };

export default function Pagamentos() {
  const [pagamentos, definirPagamentos] = useState({ itens: [], total: 0 });
  const [padrinhos, definirPadrinhos] = useState([]);
  const [conferido, definirConferido] = useState("");

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");

  const [formAberto, definirFormAberto] = useState(false);
  const [campos, definirCampos] = useState(NOVO);
  const [salvando, definirSalvando] = useState(false);

  const buscar = useCallback(async () => {
    // Sem definirCarregando(true) aqui: o efeito o chamaria de forma sincrona,
    // provocando um render extra. O estado ja nasce carregando.
    try {
      const [pags, pads] = await Promise.all([
        listarPagamentos({ conferido }),
        listarPadrinhos({ por_pagina: 200 }),
      ]);
      definirPagamentos(pags);
      definirPadrinhos(pads.itens);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [conferido]);

  useEffect(() => {
    // Buscar dados e o caso classico de efeito. O aviso do lint e falso
    // positivo: buscar() e assincrona e so mexe no estado depois do await.
    // eslint-disable-next-line react/set-state-in-effect
    buscar();
  }, [buscar]);

  const padrinho = padrinhos.find((p) => String(p.id) === String(campos.padrinho_id));
  const emAberto = padrinho?.apadrinhamentos.filter((a) => !a.pago) ?? [];

  // O valor sugerido acompanha o que foi marcado.
  const somaMarcada = emAberto
    .filter((a) => campos.apadrinhamentos.includes(a.id))
    .reduce((soma, a) => soma + Number(a.valor), 0);

  function alternar(id) {
    definirCampos((atual) => {
      const marcados = atual.apadrinhamentos.includes(id)
        ? atual.apadrinhamentos.filter((x) => x !== id)
        : [...atual.apadrinhamentos, id];
      return { ...atual, apadrinhamentos: marcados };
    });
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      await criarPagamento({
        padrinho_id: Number(campos.padrinho_id),
        valor: campos.valor || somaMarcada.toFixed(2),
        data: campos.data,
        forma: campos.forma || null,
        apadrinhamentos: campos.apadrinhamentos,
      });
      definirSucesso("Pagamento registrado.");
      definirCampos(NOVO);
      definirFormAberto(false);
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function alternarConferido(p) {
    definirErro("");
    try {
      await editarPagamento(p.id, { conferido: !p.conferido });
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function remover(p) {
    definirErro("");
    try {
      await apagarPagamento(p.id);
      definirSucesso("Pagamento removido. Os apadrinhamentos voltaram a ficar em aberto.");
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  return (
    <div>
      <div className="pagina__eyebrow">Financeiro</div>
      <h1 className="pagina__titulo">Pagamentos</h1>
      <p className="pagina__lede">
        Um pagamento pode quitar vários apadrinhamentos de uma vez. Marque quais ele
        cobre para o acompanhamento ficar certo.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      <div className="barra-acoes">
        <Button onClick={() => definirFormAberto(true)} disabled={padrinhos.length === 0}>
          Registrar pagamento
        </Button>
        <Selecao value={conferido} onChange={(e) => definirConferido(e.target.value)}>
          <option value="">Todos</option>
          <option value="false">A conferir</option>
          <option value="true">Conferidos</option>
        </Selecao>
        <span className="campo__dica" style={{ marginTop: 0 }}>
          {pagamentos.total} pagamento(s)
        </span>
      </div>

      {formAberto && (
        <form className="painel" onSubmit={salvar}>
          <h2 className="painel__titulo">Novo pagamento</h2>
          <div className="linha-campos">
            <Selecao
              rotulo="Padrinho"
              value={campos.padrinho_id}
              onChange={(e) =>
                definirCampos({ ...campos, padrinho_id: e.target.value, apadrinhamentos: [] })
              }
              required
            >
              <option value="">Escolha</option>
              {padrinhos.map((p) => (
                <option key={p.id} value={p.id}>{p.nome}</option>
              ))}
            </Selecao>
            <Entrada
              rotulo="Data"
              tipo="date"
              value={campos.data}
              onChange={(e) => definirCampos({ ...campos, data: e.target.value })}
              required
            />
            <Entrada
              rotulo="Forma"
              value={campos.forma}
              onChange={(e) => definirCampos({ ...campos, forma: e.target.value })}
              dica="Pix, dinheiro, transferência..."
            />
            <Entrada
              rotulo="Valor"
              tipo="number"
              step="0.01"
              value={campos.valor}
              onChange={(e) => definirCampos({ ...campos, valor: e.target.value })}
              dica={
                somaMarcada > 0
                  ? `Em branco usa a soma marcada: ${dinheiro(somaMarcada)}`
                  : "Em branco usa a soma dos apadrinhamentos marcados."
              }
            />
          </div>

          {padrinho && (
            <div className="campo">
              <span className="campo__rotulo">Apadrinhamentos que este pagamento quita</span>
              {emAberto.length === 0 ? (
                <span className="campo__dica">
                  Este padrinho não tem apadrinhamento em aberto.
                </span>
              ) : (
                <div className="marcaveis">
                  {emAberto.map((a) => (
                    <label
                      key={a.id}
                      className={`marcavel ${campos.apadrinhamentos.includes(a.id) ? "marcavel--marcado" : ""}`}
                    >
                      <input
                        type="checkbox"
                        checked={campos.apadrinhamentos.includes(a.id)}
                        onChange={() => alternar(a.id)}
                      />
                      {a.crianca_primeiro_nome} · {a.tipo} · {dinheiro(a.valor)}
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="barra-acoes barra-acoes--fim">
            <Button
              type="submit"
              carregando={salvando}
              disabled={!campos.padrinho_id || (!campos.valor && somaMarcada === 0)}
            >
              Salvar
            </Button>
            <Button variant="ghost" onClick={() => definirFormAberto(false)}>Cancelar</Button>
          </div>
        </form>
      )}

      {carregando ? (
        <Carregando>Carregando pagamentos...</Carregando>
      ) : pagamentos.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhum pagamento registrado"
          corpo="Assim que um padrinho pagar, registre aqui e marque o que foi quitado."
        />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th>Padrinho</th>
                <th>Valor</th>
                <th>Data</th>
                <th>Forma</th>
                <th>Quita</th>
                <th>Situação</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {pagamentos.itens.map((p) => (
                <tr key={p.id}>
                  <td>{p.padrinho}</td>
                  <td>{dinheiro(p.valor)}</td>
                  <td>{formatarData(p.data)}</td>
                  <td>{p.forma ?? "—"}</td>
                  <td>{p.apadrinhamentos.length} apadrinhamento(s)</td>
                  <td>
                    <span className={`etiqueta ${p.conferido ? "etiqueta--ok" : "etiqueta--espera"}`}>
                      {p.conferido ? "Conferido" : "A conferir"}
                    </span>
                  </td>
                  <td>
                    <div className="barra-acoes" style={{ margin: 0 }}>
                      <Button size="sm" variant="ghost" onClick={() => alternarConferido(p)}>
                        {p.conferido ? "Desmarcar" : "Conferir"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => remover(p)}>
                        Remover
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
