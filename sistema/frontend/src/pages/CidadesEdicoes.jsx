import { useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import ConfirmarExclusao from "../components/feedback/ConfirmarExclusao.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { dinheiro, formatarData } from "../utils/dinheiro.js";
import {
  apagarCidade,
  apagarDia,
  apagarEdicao,
  criarCidade,
  criarDia,
  criarEdicao,
  dependenciasDaCidade,
  dependenciasDaEdicao,
  listarCidades,
  listarDias,
  listarEdicoes,
} from "../services/cadastros.js";

const CIDADE_VAZIA = { nome: "", uf: "" };

/* O que a janela de exclusao diz alem da conta, em cada caso. E o ponto que a
   contagem sozinha nao ensina: o que NAO vai junto, e quando desativar
   resolve melhor do que apagar. */
const NOTA_CIDADE =
  "Uma cidade que só não participa este ano não precisa ser apagada: deixe-a " +
  "inativa e o histórico dos anos anteriores continua de pé.";
const NOTA_EDICAO =
  "As instituições da cidade não vão junto — o cadastro delas atravessa os " +
  "anos. Sai o que era deste ano.";
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

  // A exclusao em curso: { tipo, registro, dependencias, erro, apagando }.
  // Tudo num objeto so porque a conta que chega do servidor precisa ser
  // casada com o registro que a pediu — trocar de alvo com a resposta no ar
  // nao pode acabar mostrando a conta de um em cima do nome do outro.
  const [exclusao, definirExclusao] = useState(null);

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

  async function pedirExclusao(tipo, registro) {
    definirErro("");
    definirSucesso("");
    definirExclusao({ tipo, registro, dependencias: null, erro: "", apagando: false });
    try {
      const conta =
        tipo === "cidade"
          ? await dependenciasDaCidade(registro.id)
          : await dependenciasDaEdicao(registro.id);
      definirExclusao((atual) =>
        atual && atual.tipo === tipo && atual.registro.id === registro.id
          ? { ...atual, dependencias: conta }
          : atual,
      );
    } catch (e) {
      definirExclusao((atual) => (atual ? { ...atual, erro: e.message } : atual));
    }
  }

  async function confirmarExclusao() {
    const { tipo, registro } = exclusao;
    definirExclusao((atual) => ({ ...atual, apagando: true, erro: "" }));

    try {
      if (tipo === "cidade") {
        await apagarCidade(registro.id);
        definirCidades((l) => l.filter((c) => c.id !== registro.id));
        // As edicoes da cidade foram junto, no servidor: a lista da tela
        // precisa perder as dela tambem, senao sobram linhas apontando para
        // uma cidade que nao existe mais.
        definirEdicoes((l) => l.filter((e) => e.cidade_id !== registro.id));
        if (edicaoAberta?.cidade_id === registro.id) definirEdicaoAberta(null);
      } else {
        await apagarEdicao(registro.id);
        definirEdicoes((l) => l.filter((e) => e.id !== registro.id));
        if (edicaoAberta?.id === registro.id) definirEdicaoAberta(null);
      }
      definirSucesso(`${registro.nome} apagada.`);
      definirExclusao(null);
    } catch (e) {
      definirExclusao((atual) =>
        atual ? { ...atual, apagando: false, erro: e.message } : atual,
      );
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
        <Button variant="secondary" size="sm" onClick={() => definirFormCidade(CIDADE_VAZIA)}>
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
            <Button variant="secondary" type="submit" carregando={salvando}>Salvar</Button>
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
              <tr><th>Cidade</th><th>UF</th><th>Situação</th><th /></tr>
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
                  <td>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => pedirExclusao("cidade", c)}
                    >
                      Apagar
                    </Button>
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
            <Button variant="secondary" type="submit" carregando={salvando}>Salvar</Button>
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
                    <div className="barra-acoes" style={{ margin: 0 }}>
                      <Button size="sm" variant="ghost" onClick={() => abrirDias(e)}>
                        {edicaoAberta?.id === e.id ? "Fechar dias" : "Dias do evento"}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => pedirExclusao("edicao", e)}
                      >
                        Apagar
                      </Button>
                    </div>
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
            <Button variant="secondary" type="submit" size="sm" disabled={!novoDia.data}>
              Adicionar dia
            </Button>
          </form>
        </div>
      )}

      {exclusao && (
        <ConfirmarExclusao
          rotulo={exclusao.tipo === "cidade" ? "Cidade" : "Edição"}
          nome={
            exclusao.tipo === "cidade"
              ? `${exclusao.registro.nome} (${exclusao.registro.uf})`
              : exclusao.registro.nome
          }
          dependencias={exclusao.dependencias}
          nota={exclusao.tipo === "cidade" ? NOTA_CIDADE : NOTA_EDICAO}
          erro={exclusao.erro}
          apagando={exclusao.apagando}
          aoConfirmar={confirmarExclusao}
          aoFechar={() => definirExclusao(null)}
        />
      )}
    </div>
  );
}
