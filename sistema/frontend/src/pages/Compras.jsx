import { useCallback, useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { listarEdicoes } from "../services/cadastros.js";
import { apagarCompra, criarCompra, listarCompras } from "../services/logistica.js";
import { dinheiro, formatarData } from "../utils/dinheiro.js";

const hoje = () => new Date().toISOString().slice(0, 10);
const NOVA = {
  descricao: "", categoria: "", quantidade: "1",
  valor_total: "", fornecedor: "", data: hoje(),
};

export default function Compras() {
  const { edicaoAtiva } = useSessao();

  const [edicoes, definirEdicoes] = useState([]);
  const [edicaoId, definirEdicaoId] = useState(edicaoAtiva ?? "");
  const [dados, definirDados] = useState({ itens: [], total: 0, total_gasto: "0.00", por_categoria: {} });

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");
  const [formAberto, definirFormAberto] = useState(false);
  const [campos, definirCampos] = useState(NOVA);
  const [salvando, definirSalvando] = useState(false);

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
      definirDados(await listarCompras({ edicao_id: edicaoId }));
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoId]);

  useEffect(() => {
    if (edicaoId) buscar();
  }, [edicaoId, buscar]);

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      await criarCompra({
        edicao_id: Number(edicaoId),
        descricao: campos.descricao.trim(),
        categoria: campos.categoria.trim() || null,
        quantidade: Number(campos.quantidade),
        valor_total: campos.valor_total,
        fornecedor: campos.fornecedor.trim() || null,
        data: campos.data,
      });
      definirSucesso("Compra registrada.");
      definirCampos(NOVA);
      definirFormAberto(false);
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function remover(compra) {
    definirErro("");
    try {
      await apagarCompra(compra.id);
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  return (
    <div>
      <div className="pagina__eyebrow">Estrutura</div>
      <h1 className="pagina__titulo">Compras</h1>
      <p className="pagina__lede">
        O que foi comprado para a edição, com o total por categoria.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      <div className="barra-acoes">
        <Selecao value={edicaoId} onChange={(e) => definirEdicaoId(e.target.value)}>
          {edicoes.map((e) => (
            <option key={e.id} value={e.id}>{e.nome}</option>
          ))}
        </Selecao>
        <Button onClick={() => definirFormAberto(true)} disabled={!edicaoId}>
          Nova compra
        </Button>
      </div>

      {dados.total > 0 && (
        <div className="painel">
          <h2 className="painel__titulo">Total gasto: {dinheiro(dados.total_gasto)}</h2>
          <div className="marcaveis">
            {Object.entries(dados.por_categoria).map(([categoria, valor]) => (
              <span key={categoria} className="marcavel">
                {categoria}: <strong>{dinheiro(valor)}</strong>
              </span>
            ))}
          </div>
        </div>
      )}

      {formAberto && (
        <form className="painel" onSubmit={salvar}>
          <h2 className="painel__titulo">Nova compra</h2>
          <div className="linha-campos">
            <Entrada rotulo="Descrição" value={campos.descricao}
              onChange={(e) => definirCampos({ ...campos, descricao: e.target.value })} required />
            <Entrada rotulo="Categoria" value={campos.categoria}
              onChange={(e) => definirCampos({ ...campos, categoria: e.target.value })}
              dica="Ex.: cesta, presente, higiene, estrutura" />
            <Entrada rotulo="Quantidade" tipo="number" min="1" value={campos.quantidade}
              onChange={(e) => definirCampos({ ...campos, quantidade: e.target.value })} required />
            <Entrada rotulo="Valor total" tipo="number" step="0.01" value={campos.valor_total}
              onChange={(e) => definirCampos({ ...campos, valor_total: e.target.value })} required />
            <Entrada rotulo="Fornecedor" value={campos.fornecedor}
              onChange={(e) => definirCampos({ ...campos, fornecedor: e.target.value })} />
            <Entrada rotulo="Data" tipo="date" value={campos.data}
              onChange={(e) => definirCampos({ ...campos, data: e.target.value })} required />
          </div>
          <div className="barra-acoes barra-acoes--fim">
            <Button type="submit" carregando={salvando}>Salvar</Button>
            <Button variant="ghost" onClick={() => definirFormAberto(false)}>Cancelar</Button>
          </div>
        </form>
      )}

      {carregando ? (
        <Carregando>Carregando compras...</Carregando>
      ) : dados.itens.length === 0 ? (
        <EmptyState titulo="Nenhuma compra registrada" corpo="Registre o que a equipe de estrutura comprar." />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th>Descrição</th><th>Categoria</th><th>Qtd</th>
                <th>Valor</th><th>Fornecedor</th><th>Data</th><th>Por</th><th />
              </tr>
            </thead>
            <tbody>
              {dados.itens.map((c) => (
                <tr key={c.id}>
                  <td>{c.descricao}</td>
                  <td>{c.categoria ?? "—"}</td>
                  <td>{c.quantidade}</td>
                  <td>{dinheiro(c.valor_total)}</td>
                  <td>{c.fornecedor ?? "—"}</td>
                  <td>{formatarData(c.data)}</td>
                  <td>{c.responsavel ?? "—"}</td>
                  <td>
                    <Button size="sm" variant="ghost" onClick={() => remover(c)}>Remover</Button>
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
