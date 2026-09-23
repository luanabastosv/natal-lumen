import { useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { dinheiro, formatarData } from "../utils/dinheiro.js";
import {
  apagarDia,
  criarCidade,
  criarDia,
  criarEdicao,
  listarCidades,
  listarDias,
  listarEdicoes,
} from "../services/cadastros.js";

const CIDADE_VAZIA = { nome: "", uf: "" };
const EDICAO_VAZIA = { cidade_id: "", ano: new Date().getFullYear(), nome: "", valor_cesta: "120.00", valor_festa: "60.00" };

export default function CidadesEdicoes() {
  const [cidades, definirCidades] = useState([]);
  const [edicoes, definirEdicoes] = useState([]);
  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");

  const [formCidade, definirFormCidade] = useState(null);
  const [formEdicao, definirFormEdicao] = useState(null);
  const [salvando, definirSalvando] = useState(false);

  // Dias da edicao aberta
  const [edicaoAberta, definirEdicaoAberta] = useState(null);
  const [dias, definirDias] = useState([]);
  const [novoDia, definirNovoDia] = useState({ data: "", descricao: "" });

  useEffect(() => {
    let vivo = true;
    Promise.all([listarCidades(), listarEdicoes()])
      .then(([cids, eds]) => {
        if (!vivo) return;
        definirCidades(cids);
        definirEdicoes(eds);
      })
      .catch((e) => vivo && definirErro(e.message))
      .finally(() => vivo && definirCarregando(false));
    return () => {
      vivo = false;
    };
  }, []);

  async function salvarCidade(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      const nova = await criarCidade({
        nome: formCidade.nome.trim(),
        uf: formCidade.uf.trim().toUpperCase(),
      });
      definirCidades((l) => [...l, nova].sort((a, b) => a.nome.localeCompare(b.nome)));
      definirSucesso(`${nova.nome} cadastrada.`);
      definirFormCidade(null);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function salvarEdicao(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      const nova = await criarEdicao({
        cidade_id: Number(formEdicao.cidade_id),
        ano: Number(formEdicao.ano),
        nome: formEdicao.nome.trim(),
        valor_cesta: formEdicao.valor_cesta,
        valor_festa: formEdicao.valor_festa,
      });
      definirEdicoes((l) => [nova, ...l]);
      definirSucesso(`${nova.nome} criada.`);
      definirFormEdicao(null);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function abrirDias(edicao) {
    if (edicaoAberta?.id === edicao.id) {
      definirEdicaoAberta(null);
      return;
    }
    definirErro("");
    definirEdicaoAberta(edicao);
    definirNovoDia({ data: "", descricao: "" });
    try {
      definirDias(await listarDias(edicao.id));
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function adicionarDia(evento) {
    evento.preventDefault();
    definirErro("");
    try {
      const dia = await criarDia(edicaoAberta.id, {
        data: novoDia.data,
        descricao: novoDia.descricao.trim() || null,
      });
      definirDias((l) => [...l, dia].sort((a, b) => a.data.localeCompare(b.data)));
      definirNovoDia({ data: "", descricao: "" });
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function removerDia(dia) {
    definirErro("");
    try {
      await apagarDia(edicaoAberta.id, dia.id);
      definirDias((l) => l.filter((d) => d.id !== dia.id));
    } catch (e) {
      definirErro(e.message);
    }
  }

  if (carregando) return <Carregando tela>Carregando cadastros...</Carregando>;

  return (
    <div>
      <div className="pagina__eyebrow">Administração geral</div>
      <h1 className="pagina__titulo">Cidades e edições</h1>
      <p className="pagina__lede">
        Cada cidade num ano é uma edição independente. Os valores de cesta e festa
        valem para os apadrinhamentos registrados a partir daí.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      <h2 className="painel__titulo">Cidades</h2>
      <div className="barra-acoes">
        <Button size="sm" onClick={() => definirFormCidade(CIDADE_VAZIA)}>
          Nova cidade
        </Button>
      </div>

      {formCidade && (
        <form className="painel" onSubmit={salvarCidade}>
          <div className="linha-campos">
            <Entrada
              rotulo="Nome"
              value={formCidade.nome}
              onChange={(e) => definirFormCidade({ ...formCidade, nome: e.target.value })}
              required
            />
            <Entrada
              rotulo="UF"
              value={formCidade.uf}
              onChange={(e) => definirFormCidade({ ...formCidade, uf: e.target.value })}
              maxLength={2}
              required
            />
          </div>
          <div className="barra-acoes barra-acoes--fim">
            <Button type="submit" carregando={salvando}>Salvar</Button>
            <Button variant="ghost" onClick={() => definirFormCidade(null)}>Cancelar</Button>
          </div>
        </form>
      )}

      {cidades.length === 0 ? (
        <EmptyState titulo="Nenhuma cidade cadastrada" corpo="Comece cadastrando a cidade, depois crie a edição do ano." />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr><th>Cidade</th><th>UF</th><th>Situação</th></tr>
            </thead>
            <tbody>
              {cidades.map((c) => (
                <tr key={c.id}>
                  <td>{c.nome}</td>
                  <td>{c.uf}</td>
                  <td>
                    <span className={`etiqueta ${c.ativo ? "etiqueta--ok" : "etiqueta--neutra"}`}>
                      {c.ativo ? "Ativa" : "Inativa"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="painel__titulo" style={{ marginTop: "var(--space-7)" }}>Edições</h2>
      <div className="barra-acoes">
        <Button
          size="sm"
          onClick={() => definirFormEdicao({ ...EDICAO_VAZIA, cidade_id: cidades[0]?.id ?? "" })}
          disabled={cidades.length === 0}
        >
          Nova edição
        </Button>
      </div>

      {formEdicao && (
        <form className="painel" onSubmit={salvarEdicao}>
          <div className="linha-campos">
            <Selecao
              rotulo="Cidade"
              value={formEdicao.cidade_id}
              onChange={(e) => definirFormEdicao({ ...formEdicao, cidade_id: e.target.value })}
              required
            >
              {cidades.map((c) => (
                <option key={c.id} value={c.id}>{c.nome} · {c.uf}</option>
              ))}
            </Selecao>
            <Entrada
              rotulo="Ano"
              tipo="number"
              value={formEdicao.ano}
              onChange={(e) => definirFormEdicao({ ...formEdicao, ano: e.target.value })}
              required
            />
            <Entrada
              rotulo="Nome da edição"
              value={formEdicao.nome}
              onChange={(e) => definirFormEdicao({ ...formEdicao, nome: e.target.value })}
              dica="Ex.: Fortaleza 2026"
              required
            />
            <Entrada
              rotulo="Valor da cesta"
              tipo="number"
              step="0.01"
              value={formEdicao.valor_cesta}
              onChange={(e) => definirFormEdicao({ ...formEdicao, valor_cesta: e.target.value })}
              required
            />
            <Entrada
              rotulo="Valor da festa"
              tipo="number"
              step="0.01"
              value={formEdicao.valor_festa}
              onChange={(e) => definirFormEdicao({ ...formEdicao, valor_festa: e.target.value })}
              required
            />
          </div>
          <div className="barra-acoes barra-acoes--fim">
            <Button type="submit" carregando={salvando}>Salvar</Button>
            <Button variant="ghost" onClick={() => definirFormEdicao(null)}>Cancelar</Button>
          </div>
        </form>
      )}

      {edicoes.length === 0 ? (
        <EmptyState titulo="Nenhuma edição criada" corpo="A edição é o que liga crianças, padrinhos e equipe a um ano e uma cidade." />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr><th>Edição</th><th>Cidade</th><th>Ano</th><th>Cesta</th><th>Festa</th><th>Situação</th><th /></tr>
            </thead>
            <tbody>
              {edicoes.map((e) => (
                <tr key={e.id}>
                  <td>{e.nome}</td>
                  <td>{e.cidade} · {e.uf}</td>
                  <td>{e.ano}</td>
                  <td>{dinheiro(e.valor_cesta)}</td>
                  <td>{dinheiro(e.valor_festa)}</td>
                  <td>
                    <span className={`etiqueta ${e.ativa ? "etiqueta--ok" : "etiqueta--neutra"}`}>
                      {e.ativa ? "Ativa" : "Encerrada"}
                    </span>
                  </td>
                  <td>
                    <Button size="sm" variant="ghost" onClick={() => abrirDias(e)}>
                      {edicaoAberta?.id === e.id ? "Fechar dias" : "Dias do evento"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {edicaoAberta && (
        <div className="painel" style={{ marginTop: "var(--space-5)" }}>
          <h3 className="painel__titulo">Dias de {edicaoAberta.nome}</h3>
          <p className="campo__dica" style={{ marginTop: 0, marginBottom: "var(--space-4)" }}>
            Cada criança vai a um único dia. Um dia só pode ser apagado quando não tem
            criança marcada.
          </p>

          {dias.length > 0 && (
            <div className="tabela-rolagem">
              <table className="tabela">
                <thead>
                  <tr><th>Data</th><th>Descrição</th><th>Crianças</th><th /></tr>
                </thead>
                <tbody>
                  {dias.map((d) => (
                    <tr key={d.id}>
                      <td>{formatarData(d.data)}</td>
                      <td>{d.descricao ?? "—"}</td>
                      <td>{d.total_criancas}</td>
                      <td>
                        <Button size="sm" variant="ghost" onClick={() => removerDia(d)}>
                          Apagar
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <form onSubmit={adicionarDia} style={{ marginTop: "var(--space-5)" }}>
            <div className="linha-campos">
              <Entrada
                rotulo="Data"
                tipo="date"
                value={novoDia.data}
                onChange={(e) => definirNovoDia({ ...novoDia, data: e.target.value })}
                required
              />
              <Entrada
                rotulo="Descrição"
                value={novoDia.descricao}
                onChange={(e) => definirNovoDia({ ...novoDia, descricao: e.target.value })}
                dica="Opcional. Ex.: Sábado de manhã"
              />
            </div>
            <Button type="submit" size="sm" disabled={!novoDia.data}>
              Adicionar dia
            </Button>
          </form>
        </div>
      )}
    </div>
  );
}
