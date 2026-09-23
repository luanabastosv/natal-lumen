import { useCallback, useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { listarEdicoes } from "../services/cadastros.js";
import { listarKits, mudarKits } from "../services/logistica.js";
import { formatarData, formatarDataHora } from "../utils/dinheiro.js";

const ESTADOS = {
  pendente: ["espera", "Pendente"],
  montado: ["neutra", "Montado"],
  entregue: ["ok", "Entregue"],
};

export default function Kits() {
  const { edicaoAtiva } = useSessao();

  const [edicoes, definirEdicoes] = useState([]);
  const [edicaoId, definirEdicaoId] = useState(edicaoAtiva ?? "");
  const [situacao, definirSituacao] = useState("");
  const [dados, definirDados] = useState({ itens: [], total: 0, resumo: {} });
  const [marcados, definirMarcados] = useState([]);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");

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
      definirDados(await listarKits({ edicao_id: edicaoId, situacao }));
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoId, situacao]);

  useEffect(() => {
    if (edicaoId) buscar();
  }, [edicaoId, situacao, buscar]);

  async function mudar(status) {
    definirErro("");
    try {
      const mudados = await mudarKits(marcados, status);
      definirSucesso(`${mudados.length} kit(s) marcado(s) como ${status}.`);
      definirMarcados([]);
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  function alternar(id) {
    definirMarcados((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));
  }

  function marcarTodos() {
    definirMarcados(
      marcados.length === dados.itens.length ? [] : dados.itens.map((i) => i.crianca_id),
    );
  }

  return (
    <div>
      <div className="pagina__eyebrow">Estrutura</div>
      <h1 className="pagina__titulo">Kits</h1>
      <p className="pagina__lede">
        Um kit por criança: cesta, presente e kit de higiene. A lista parte das
        crianças, então quem ainda não tem kit aparece como pendente.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      <div className="barra-acoes">
        <Selecao value={edicaoId} onChange={(e) => definirEdicaoId(e.target.value)}>
          {edicoes.map((e) => (
            <option key={e.id} value={e.id}>{e.nome}</option>
          ))}
        </Selecao>
        <Selecao value={situacao} onChange={(e) => definirSituacao(e.target.value)}>
          <option value="">Todos</option>
          <option value="pendente">Pendentes</option>
          <option value="montado">Montados</option>
          <option value="entregue">Entregues</option>
        </Selecao>
        {Object.entries(dados.resumo).map(([estado, quantos]) => (
          <span key={estado} className={`etiqueta etiqueta--${ESTADOS[estado]?.[0] ?? "neutra"}`}>
            {quantos} {ESTADOS[estado]?.[1] ?? estado}
          </span>
        ))}
      </div>

      {marcados.length > 0 && (
        <div className="painel painel--destaque">
          <h2 className="painel__titulo">{marcados.length} criança(s) marcada(s)</h2>
          <div className="barra-acoes" style={{ margin: 0 }}>
            <Button size="sm" onClick={() => mudar("montado")}>Marcar como montado</Button>
            <Button size="sm" onClick={() => mudar("entregue")}>Marcar como entregue</Button>
            <Button size="sm" variant="ghost" onClick={() => mudar("pendente")}>
              Voltar para pendente
            </Button>
            <Button size="sm" variant="ghost" onClick={() => definirMarcados([])}>Limpar</Button>
          </div>
        </div>
      )}

      {carregando ? (
        <Carregando>Carregando kits...</Carregando>
      ) : dados.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhuma criança nesta lista"
          corpo="Importe as listas das instituições para os kits aparecerem aqui."
        />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={marcados.length === dados.itens.length && dados.itens.length > 0}
                    onChange={marcarTodos}
                    aria-label="Marcar todas"
                  />
                </th>
                <th>Criança</th>
                <th>Instituição</th>
                <th>Dia</th>
                <th>Kit</th>
                <th>Entregue em</th>
              </tr>
            </thead>
            <tbody>
              {dados.itens.map((k) => {
                const [tom, rotulo] = ESTADOS[k.status] ?? ["neutra", k.status];
                return (
                  <tr key={k.crianca_id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={marcados.includes(k.crianca_id)}
                        onChange={() => alternar(k.crianca_id)}
                        aria-label={`Marcar ${k.crianca_nome}`}
                      />
                    </td>
                    <td>{k.crianca_nome}</td>
                    <td>{k.instituicao}</td>
                    <td>{k.dia_evento ? formatarData(k.dia_evento) : "—"}</td>
                    <td><span className={`etiqueta etiqueta--${tom}`}>{rotulo}</span></td>
                    <td>{k.entregue_em ? formatarDataHora(k.entregue_em) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
