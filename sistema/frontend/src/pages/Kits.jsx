import { useCallback, useEffect, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import { Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import { listarKits, mudarKits } from "../services/logistica.js";
import EtiquetaDia from "../components/core/EtiquetaDia.jsx";
import { formatarDataHora } from "../utils/dinheiro.js";

const ESTADOS = {
  pendente: ["espera", "Pendente"],
  montado: ["neutra", "Montado"],
  entregue: ["ok", "Entregue"],
};

export default function Kits() {
  // A edicao vem da lateral: e a mesma para o sistema inteiro.
  const { edicaoAtiva } = useSessao();

  const [situacao, definirSituacao] = useState("");
  const [dados, definirDados] = useState({ itens: [], total: 0, resumo: {} });
  const [marcados, definirMarcados] = useState([]);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const notificar = useNotificar();

  const buscar = useCallback(async () => {
    try {
      definirDados(await listarKits({ edicao_id: edicaoAtiva, situacao }));
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoAtiva, situacao]);

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer: a
    // lista so chega depois do await, e nao daria para derivar no render.
    // eslint-disable-next-line react/set-state-in-effect
    if (edicaoAtiva) buscar();
  }, [edicaoAtiva, situacao, buscar]);

  async function mudar(status) {
    definirErro("");
    try {
      const mudados = await mudarKits(marcados, status);
      notificar(`${mudados.length} kit(s) marcado(s) como ${status}.`);
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
      <Rabisco className="pagina__onda" />
      <p className="pagina__lede">
        Um kit por criança: cesta, presente e kit de higiene. A lista parte das
        crianças, então quem ainda não tem kit aparece como pendente.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>

      <div className="barra-acoes">
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
            <Button variant="secondary" size="sm" onClick={() => mudar("entregue")}>Marcar como entregue</Button>
            <Button size="sm" variant="ghost" onClick={() => mudar("pendente")}>
              Voltar para pendente
            </Button>
            <Button size="sm" variant="ghost" onClick={() => definirMarcados([])}>Limpar</Button>
          </div>
        </div>
      )}

      {carregando ? (
        <Carregando tela>Carregando kits...</Carregando>
      ) : dados.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhuma criança nesta lista"
          corpo="Importe as listas das instituições para os kits aparecerem aqui."
        />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela tabela--larga">
            <caption className="tabela-dica">
              Arraste a lista para o lado para ver todas as colunas.
            </caption>
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
                    <td>
                      {k.dia_evento ? (
                        <EtiquetaDia data={k.dia_evento} descricao={k.dia_evento_descricao} />
                      ) : (
                        "—"
                      )}
                    </td>
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
