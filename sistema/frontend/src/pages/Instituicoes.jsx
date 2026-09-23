import { useCallback, useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import {
  criarInstituicao,
  definirDiaDaInstituicao,
  editarInstituicao,
  listarCidades,
  listarDias,
  listarEdicoes,
  listarInstituicoes,
} from "../services/cadastros.js";
import { formatarData } from "../utils/dinheiro.js";
import { useSessao } from "../contexts/useSessao.js";

const VAZIO = {
  cidade_id: "",
  nome: "",
  sigla: "",
  dia_evento_id: "",
  responsavel: "",
  telefone: "",
  endereco: "",
};

export default function Instituicoes() {
  const { edicaoAtiva } = useSessao();

  const [instituicoes, definirInstituicoes] = useState([]);
  const [cidades, definirCidades] = useState([]);
  const [edicoes, definirEdicoes] = useState([]);
  // O dia do evento e por edicao: sem escolher uma, a pergunta nao tem resposta.
  const [edicaoId, definirEdicaoId] = useState(edicaoAtiva ?? "");
  const [dias, definirDias] = useState([]);
  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");

  const [formularioAberto, definirFormularioAberto] = useState(false);
  const [emEdicao, definirEmEdicao] = useState(null);
  const [campos, definirCampos] = useState(VAZIO);
  const [salvando, definirSalvando] = useState(false);
  const edicaoSelecionada = edicoes.find((e) => String(e.id) === String(edicaoId));
  const cidadeDoFormulario = emEdicao?.cidade_id ?? campos.cidade_id;
  const cidadeBateComEdicao =
    !edicaoSelecionada ||
    String(cidadeDoFormulario) === String(edicaoSelecionada.cidade_id);

  useEffect(() => {
    let vivo = true;
    Promise.all([listarCidades(), listarEdicoes()])
      .then(([cids, eds]) => {
        if (!vivo) return;
        definirCidades(cids);
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
      const [lista, ds] = await Promise.all([
        listarInstituicoes({ edicao_id: edicaoId || undefined }),
        edicaoId ? listarDias(edicaoId) : Promise.resolve([]),
      ]);
      definirInstituicoes(lista);
      definirDias(ds);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoId]);

  useEffect(() => {
    buscar();
  }, [buscar]);

  function abrirNova() {
    definirEmEdicao(null);
    // A cidade ja vem a da edicao escolhida: cadastrar numa cidade diferente
    // faria a instituicao sumir da lista e o dia nao poder ser marcado.
    definirCampos({
      ...VAZIO,
      cidade_id: edicaoSelecionada?.cidade_id ?? cidades[0]?.id ?? "",
    });
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
      dia_evento_id: inst.dia_evento_id ?? "",
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
      const salva = emEdicao
        ? await editarInstituicao(emEdicao.id, corpo)
        : await criarInstituicao({ ...corpo, cidade_id: Number(campos.cidade_id) });

      // O dia vive noutra tabela (e por edicao), entao vai numa chamada
      // propria — mas do ponto de vista de quem preenche e o mesmo cadastro.
      const diaMudou =
        String(campos.dia_evento_id ?? "") !== String(emEdicao?.dia_evento_id ?? "");
      if (edicaoId && diaMudou && cidadeBateComEdicao) {
        await definirDiaDaInstituicao(
          Number(edicaoId),
          salva.id,
          campos.dia_evento_id ? Number(campos.dia_evento_id) : null,
        );
      }

      definirSucesso(
        emEdicao ? `${salva.nome} atualizada.` : `${salva.nome} cadastrada.`,
      );
      definirFormularioAberto(false);
      buscar();
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
        elas que enviam as listas de crianças. <strong>O dia do evento é definido
        aqui</strong>: todas as crianças da instituição vão no mesmo dia.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      <div className="barra-acoes">
        {edicoes.length > 0 && (
          <Selecao
            value={edicaoId}
            onChange={(e) => definirEdicaoId(e.target.value)}
            aria-label="Edição"
          >
            {edicoes.map((e) => (
              <option key={e.id} value={e.id}>{e.nome}</option>
            ))}
          </Selecao>
        )}
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
        <Modal
          titulo={emEdicao ? `Editar ${emEdicao.nome}` : "Nova instituição"}
          aoFechar={() => !salvando && definirFormularioAberto(false)}
        >
          <form onSubmit={salvar}>
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

            {/* O dia e por edicao, e por isso depende da edicao escolhida na
                pagina — mas para quem cadastra e so mais um campo da ficha. */}
            <Selecao
              rotulo={`Dia do evento${edicaoSelecionada ? ` · ${edicaoSelecionada.nome}` : ""}`}
              value={cidadeBateComEdicao ? campos.dia_evento_id : ""}
              onChange={(e) => mudar("dia_evento_id", e.target.value)}
              disabled={!edicaoId || dias.length === 0 || !cidadeBateComEdicao}
              dica={
                !cidadeBateComEdicao
                  ? `O dia é da edição ${edicaoSelecionada?.nome}, que é de outra cidade. Escolha a cidade dela para poder marcar o dia.`
                  : dias.length === 0
                    ? "Esta edição ainda não tem dias cadastrados — crie em Cidades e edições."
                    : "Todas as crianças desta instituição vão neste dia."
              }
            >
              <option value="">Sem dia definido</option>
              {dias.map((d) => (
                <option key={d.id} value={d.id}>
                  {formatarData(d.data)}
                  {d.descricao ? ` · ${d.descricao}` : ""}
                </option>
              ))}
            </Selecao>

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
        </Modal>
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
                <th>Dia do evento</th>
                <th>Crianças</th>
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
                  <td>
                    {i.dia_evento ? (
                      formatarData(i.dia_evento)
                    ) : (
                      <span className="etiqueta etiqueta--espera">sem dia</span>
                    )}
                  </td>
                  <td>{i.criancas}</td>
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
