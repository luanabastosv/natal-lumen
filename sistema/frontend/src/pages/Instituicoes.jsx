import { useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import {
  criarInstituicao,
  editarInstituicao,
  listarCidades,
  listarInstituicoes,
} from "../services/cadastros.js";

const VAZIO = { cidade_id: "", nome: "", sigla: "", responsavel: "", telefone: "", endereco: "" };

export default function Instituicoes() {
  const [instituicoes, definirInstituicoes] = useState([]);
  const [cidades, definirCidades] = useState([]);
  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");

  const [formularioAberto, definirFormularioAberto] = useState(false);
  const [emEdicao, definirEmEdicao] = useState(null);
  const [campos, definirCampos] = useState(VAZIO);
  const [salvando, definirSalvando] = useState(false);

  useEffect(() => {
    let vivo = true;
    Promise.all([listarInstituicoes(), listarCidades()])
      .then(([lista, cids]) => {
        if (!vivo) return;
        definirInstituicoes(lista);
        definirCidades(cids);
      })
      .catch((e) => vivo && definirErro(e.message))
      .finally(() => vivo && definirCarregando(false));
    return () => {
      vivo = false;
    };
  }, []);

  function abrirNova() {
    definirEmEdicao(null);
    definirCampos({ ...VAZIO, cidade_id: cidades[0]?.id ?? "" });
    definirFormularioAberto(true);
    definirErro("");
    definirSucesso("");
  }

  function abrirEdicao(inst) {
    definirEmEdicao(inst);
    definirCampos({
      cidade_id: inst.cidade_id,
      nome: inst.nome,
      sigla: inst.sigla ?? "",
      responsavel: inst.responsavel ?? "",
      telefone: inst.telefone ?? "",
      endereco: inst.endereco ?? "",
    });
    definirFormularioAberto(true);
    definirErro("");
    definirSucesso("");
  }

  function mudar(campo, valor) {
    definirCampos((atual) => ({ ...atual, [campo]: valor }));
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);

    // Campos opcionais vazios viram null, e nao "".
    const corpo = {
      nome: campos.nome.trim(),
      sigla: campos.sigla.trim().toUpperCase() || null,
      responsavel: campos.responsavel.trim() || null,
      telefone: campos.telefone.trim() || null,
      endereco: campos.endereco.trim() || null,
    };

    try {
      if (emEdicao) {
        const atualizada = await editarInstituicao(emEdicao.id, corpo);
        definirInstituicoes((lista) =>
          lista.map((i) => (i.id === atualizada.id ? atualizada : i)),
        );
        definirSucesso(`${atualizada.nome} atualizada.`);
      } else {
        const nova = await criarInstituicao({
          ...corpo,
          cidade_id: Number(campos.cidade_id),
        });
        definirInstituicoes((lista) =>
          [...lista, nova].sort((a, b) => a.nome.localeCompare(b.nome)),
        );
        definirSucesso(`${nova.nome} cadastrada.`);
      }
      definirFormularioAberto(false);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function alternarAtivo(inst) {
    definirErro("");
    try {
      const atualizada = await editarInstituicao(inst.id, { ativo: !inst.ativo });
      definirInstituicoes((lista) =>
        lista.map((i) => (i.id === atualizada.id ? atualizada : i)),
      );
    } catch (e) {
      definirErro(e.message);
    }
  }

  if (carregando) return <Carregando tela>Carregando instituições...</Carregando>;

  return (
    <div>
      <div className="pagina__eyebrow">Cadastros</div>
      <h1 className="pagina__titulo">Instituições</h1>
      <p className="pagina__lede">
        As instituições pertencem a uma cidade e continuam de um ano para o outro. São
        elas que enviam as listas de crianças.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      <div className="barra-acoes">
        <Button onClick={abrirNova} disabled={cidades.length === 0}>
          Nova instituição
        </Button>
        {cidades.length === 0 && (
          <span className="campo__dica">
            Nenhuma cidade cadastrada ainda — peça à administração geral.
          </span>
        )}
      </div>

      {formularioAberto && (
        <form className="painel" onSubmit={salvar}>
          <h2 className="painel__titulo">
            {emEdicao ? `Editar ${emEdicao.nome}` : "Nova instituição"}
          </h2>

          <div className="linha-campos">
            {!emEdicao && (
              <Selecao
                rotulo="Cidade"
                value={campos.cidade_id}
                onChange={(e) => mudar("cidade_id", e.target.value)}
                required
              >
                {cidades.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome} · {c.uf}
                  </option>
                ))}
              </Selecao>
            )}
            <Entrada
              rotulo="Nome"
              value={campos.nome}
              onChange={(e) => mudar("nome", e.target.value)}
              required
            />
            <Entrada
              rotulo="Sigla"
              value={campos.sigla}
              onChange={(e) => mudar("sigla", e.target.value.toUpperCase())}
              maxLength={6}
              dica='Prefixo do código das crianças. "ES" gera ES00, ES01... Em branco, o sistema sugere.'
            />
            <Entrada
              rotulo="Responsável"
              value={campos.responsavel}
              onChange={(e) => mudar("responsavel", e.target.value)}
            />
            <Entrada
              rotulo="Telefone"
              value={campos.telefone}
              onChange={(e) => mudar("telefone", e.target.value)}
            />
            <Entrada
              rotulo="Endereço"
              value={campos.endereco}
              onChange={(e) => mudar("endereco", e.target.value)}
            />
          </div>

          <div className="barra-acoes barra-acoes--fim">
            <Button type="submit" carregando={salvando} disabled={!campos.nome.trim()}>
              {salvando ? "Salvando..." : "Salvar"}
            </Button>
            <Button
              variant="ghost"
              onClick={() => definirFormularioAberto(false)}
              disabled={salvando}
            >
              Cancelar
            </Button>
          </div>
        </form>
      )}

      {instituicoes.length === 0 ? (
        <EmptyState
          titulo="Nenhuma instituição cadastrada"
          corpo="Cadastre as instituições que enviam listas de crianças nesta cidade."
        />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Sigla</th>
                <th>Cidade</th>
                <th>Responsável</th>
                <th>Telefone</th>
                <th>Situação</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {instituicoes.map((i) => (
                <tr key={i.id}>
                  <td>{i.nome}</td>
                  <td>
                    <span className="etiqueta etiqueta--neutra">{i.sigla ?? "—"}</span>
                  </td>
                  <td>{i.cidade}</td>
                  <td>{i.responsavel ?? "—"}</td>
                  <td>{i.telefone ?? "—"}</td>
                  <td>
                    <span className={`etiqueta ${i.ativo ? "etiqueta--ok" : "etiqueta--neutra"}`}>
                      {i.ativo ? "Ativa" : "Inativa"}
                    </span>
                  </td>
                  <td>
                    <div className="barra-acoes" style={{ margin: 0 }}>
                      <Button size="sm" variant="ghost" onClick={() => abrirEdicao(i)}>
                        Editar
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => alternarAtivo(i)}>
                        {i.ativo ? "Desativar" : "Ativar"}
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
