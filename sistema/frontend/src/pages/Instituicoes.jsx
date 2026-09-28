import { useCallback, useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import MenuAcoes from "../components/core/MenuAcoes.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import ConfirmarExclusao from "../components/feedback/ConfirmarExclusao.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import {
  apagarInstituicao,
  criarInstituicao,
  definirDiaDaInstituicao,
  dependenciasDaInstituicao,
  editarInstituicao,
  listarCidades,
  listarDias,
  listarInstituicoes,
} from "../services/cadastros.js";
import { formatarData } from "../utils/dinheiro.js";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";

/* O que a janela de exclusao diz alem da conta. Desativar e quase sempre o
   caminho certo: guarda o historico e tira a instituicao do ano corrente. */
const NOTA_INSTITUICAO =
  "A conta é de todas as edições, não só da que está aberta aqui: o cadastro " +
  "da instituição é um só e atravessa os anos. Se ela apenas não participa " +
  "deste ano, desative em vez de apagar.";

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
  // O dia do evento e por edicao, e a edicao vem da lateral: e a mesma para o
  // sistema inteiro.
  const { edicaoAtiva, edicao: edicaoSelecionada } = useSessao();

  const [instituicoes, definirInstituicoes] = useState([]);
  const [cidades, definirCidades] = useState([]);
  const [dias, definirDias] = useState([]);
  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const notificar = useNotificar();

  // A exclusao em curso: { registro, dependencias, erro, apagando }. Num
  // objeto so para a conta que chega do servidor nunca aparecer em cima do
  // nome de outra instituicao, se o alvo trocar com a resposta no ar.
  const [exclusao, definirExclusao] = useState(null);

  const [formularioAberto, definirFormularioAberto] = useState(false);
  const [emEdicao, definirEmEdicao] = useState(null);
  const [campos, definirCampos] = useState(VAZIO);
  const [salvando, definirSalvando] = useState(false);
  const cidadeDoFormulario = emEdicao?.cidade_id ?? campos.cidade_id;
  const cidadeBateComEdicao =
    !edicaoSelecionada ||
    String(cidadeDoFormulario) === String(edicaoSelecionada.cidade_id);

  useEffect(() => {
    let vivo = true;
    listarCidades()
      .then((cids) => vivo && definirCidades(cids))
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, []);

  const buscar = useCallback(async () => {
    try {
      const [lista, ds] = await Promise.all([
        listarInstituicoes({ edicao_id: edicaoAtiva || undefined }),
        edicaoAtiva ? listarDias(edicaoAtiva) : Promise.resolve([]),
      ]);
      definirInstituicoes(lista);
      definirDias(ds);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoAtiva]);

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer: a
    // lista so chega depois do await, e nao daria para derivar no render.
    // eslint-disable-next-line react/set-state-in-effect
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
      if (edicaoAtiva && diaMudou && cidadeBateComEdicao) {
        await definirDiaDaInstituicao(
          Number(edicaoAtiva),
          salva.id,
          campos.dia_evento_id ? Number(campos.dia_evento_id) : null,
        );
      }

      // Quando a sigla muda, o codigo das criancas muda junto — quem acabou de
      // salvar precisa saber, porque a planilha impressa ficou velha.
      const codigos = salva.codigos_atualizados ?? 0;
      notificar(
        emEdicao
          ? codigos > 0
            ? `${salva.nome} atualizada. ${codigos} ${
                codigos === 1 ? "código passou" : "códigos passaram"
              } a começar com ${salva.sigla} — listas e crachás já impressos ficaram desatualizados.`
            : `${salva.nome} atualizada.`
          : `${salva.nome} cadastrada.`,
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

  async function pedirExclusao(inst) {
    definirErro("");
    definirExclusao({ registro: inst, dependencias: null, erro: "", apagando: false });
    try {
      const conta = await dependenciasDaInstituicao(inst.id);
      definirExclusao((atual) =>
        atual && atual.registro.id === inst.id
          ? { ...atual, dependencias: conta }
          : atual,
      );
    } catch (e) {
      definirExclusao((atual) => (atual ? { ...atual, erro: e.message } : atual));
    }
  }

  async function confirmarExclusao() {
    const inst = exclusao.registro;
    definirExclusao((atual) => ({ ...atual, apagando: true, erro: "" }));
    try {
      await apagarInstituicao(inst.id);
      definirInstituicoes((lista) => lista.filter((i) => i.id !== inst.id));
      notificar(`${inst.nome} apagada.`);
      definirExclusao(null);
    } catch (e) {
      definirExclusao((atual) =>
        atual ? { ...atual, apagando: false, erro: e.message } : atual,
      );
    }
  }

  if (carregando) return <Carregando tela>Carregando instituições...</Carregando>;

  return (
    <div>
      <div className="pagina__cabecalho">
        <div className="pagina__texto">
          <div className="pagina__eyebrow">Cadastros</div>
          <h1 className="pagina__titulo">Instituições</h1>
          <p className="pagina__lede">
            Pertencem a uma cidade e continuam de um ano para o outro. São elas que
            enviam as listas. <strong>O dia do evento é definido aqui</strong>, e vale
            para todas as crianças da instituição.
          </p>
        </div>

        <div className="pagina__acoes">
          <Button onClick={abrirNova} disabled={cidades.length === 0}>
            Nova instituição
          </Button>
        </div>
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {/* So aparece no caso em que o botao esta desligado: fora dele a linha
          seria um vazio entre o titulo e a lista. */}
      {cidades.length === 0 && (
        <div className="barra-acoes">
          <span className="campo__dica">
            Nenhuma cidade cadastrada ainda — peça à administração geral.
          </span>
        </div>
      )}

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
              dica={
                emEdicao && emEdicao.criancas > 0
                  ? `Prefixo do código das crianças. Mudar a sigla troca o prefixo das ${emEdicao.criancas} crianças já cadastradas (ES04 vira SL04); o número de cada uma continua o mesmo.`
                  : 'Prefixo do código das crianças. "ES" gera ES00, ES01... Em branco, o sistema sugere.'
              }
            />

            {/* O dia e por edicao, e por isso depende da edicao escolhida na
                pagina — mas para quem cadastra e so mais um campo da ficha. */}
            <Selecao
              rotulo={`Dia do evento${edicaoSelecionada ? ` · ${edicaoSelecionada.nome}` : ""}`}
              value={cidadeBateComEdicao ? campos.dia_evento_id : ""}
              onChange={(e) => mudar("dia_evento_id", e.target.value)}
              disabled={!edicaoAtiva || dias.length === 0 || !cidadeBateComEdicao}
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
              <Button variant="secondary" type="submit" carregando={salvando} disabled={!campos.nome.trim()}>
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
          <table className="tabela tabela--larga">
            <caption className="tabela-dica">
              Arraste a lista para o lado para ver todas as colunas.
            </caption>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Sigla</th>
                <th>Dia do evento</th>
                <th>Crianças</th>
                <th>Responsável</th>
                <th>Telefone</th>
                <th>Situação</th>
                <th className="tabela__acoes" />
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
                  <td className="tabela__acoes">
                    <MenuAcoes
                      titulo={`Ações de ${i.nome}`}
                      itens={[
                        { rotulo: "Editar", aoEscolher: () => abrirEdicao(i) },
                        {
                          rotulo: i.ativo ? "Desativar" : "Ativar",
                          aoEscolher: () => alternarAtivo(i),
                        },
                        {
                          rotulo: "Apagar",
                          perigo: true,
                          aoEscolher: () => pedirExclusao(i),
                        },
                      ]}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {exclusao && (
        <ConfirmarExclusao
          rotulo="Instituição"
          nome={exclusao.registro.nome}
          dependencias={exclusao.dependencias}
          nota={NOTA_INSTITUICAO}
          erro={exclusao.erro}
          apagando={exclusao.apagando}
          aoConfirmar={confirmarExclusao}
          aoFechar={() => definirExclusao(null)}
        />
      )}
    </div>
  );
}
