import { useCallback, useEffect, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import MenuAcoes from "../components/core/MenuAcoes.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import ConfirmarExclusao from "../components/feedback/ConfirmarExclusao.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import FichaSimples from "../components/dados/FichaSimples.jsx";
import ImprimirLista from "../components/dados/ImprimirLista.jsx";
import { Imprimir } from "../components/core/icones.jsx";
import {
  apagarInstituicao,
  criarInstituicao,
  definirDiaDaInstituicao,
  definirMonitorResponsavel,
  dependenciasDaInstituicao,
  editarInstituicao,
  listarCidades,
  listarDias,
  listarInstituicoes,
  listarMonitoresDaInstituicao,
} from "../services/cadastros.js";
import { doisNomes } from "../utils/nomes.js";
import EtiquetaDia from "../components/core/EtiquetaDia.jsx";
import { rotuloDia } from "../utils/dinheiro.js";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";

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
  onibus: "",
  responsavel: "",
  telefone: "",
  endereco: "",
  monitor_id: "",
};

/* Nome em cima, telefone embaixo, em letra miuda: o mesmo desenho do
   endereco embaixo do nome da instituicao. */
function PessoaNaCelula({ nome, telefone }) {
  if (!nome) return "—";
  return (
    <>
      <span className="tabela__pessoa">{nome}</span>
      {telefone && <div className="tabela__nota">{telefone}</div>}
    </>
  );
}

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

  // No celular as nove colunas nao cabem: ficam de pe o nome e quantas
  // criancas a instituicao mandou — o que identifica a linha e o numero que se
  // procura nela — e o resto vai para uma janela, a um toque.
  const estreita = useTelaEstreita();
  const [detalhe, definirDetalhe] = useState(null);
  const [imprimindo, definirImprimindo] = useState(false);

  const [formularioAberto, definirFormularioAberto] = useState(false);
  const [emEdicao, definirEmEdicao] = useState(null);
  const [campos, definirCampos] = useState(VAZIO);
  const [salvando, definirSalvando] = useState(false);
  // Os monitores atribuidos a instituicao em edicao: as opcoes do monitor
  // responsavel. Null enquanto carregam.
  const [monitores, definirMonitores] = useState([]);
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
      // Zero e "ainda nao fechei o transporte", e o campo mostra isso vazio:
      // um "0" escrito se leria como uma decisao ja tomada.
      onibus: inst.onibus ? String(inst.onibus) : "",
      responsavel: inst.responsavel ?? "",
      telefone: inst.telefone ?? "",
      endereco: inst.endereco ?? "",
      monitor_id: inst.monitor_responsavel_id ?? "",
    });
    definirFormularioAberto(true);
    definirErro("");

    // O monitor e da edicao, como o dia: sem edicao da mesma cidade, nao ha
    // quem escolher.
    definirMonitores(null);
    const daCidade =
      !edicaoSelecionada || String(inst.cidade_id) === String(edicaoSelecionada.cidade_id);
    if (!edicaoAtiva || !daCidade) {
      definirMonitores([]);
      return;
    }
    listarMonitoresDaInstituicao(Number(edicaoAtiva), inst.id)
      .then(definirMonitores)
      .catch((e) => {
        definirMonitores([]);
        definirErro(e.message);
      });
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

      // O dia e os onibus vivem noutra tabela (e sao por edicao), entao vao
      // numa chamada propria — mas do ponto de vista de quem preenche e o
      // mesmo cadastro.
      const diaMudou =
        String(campos.dia_evento_id ?? "") !== String(emEdicao?.dia_evento_id ?? "");
      const onibusMudou =
        String(campos.onibus ?? "") !== (emEdicao?.onibus ? String(emEdicao.onibus) : "");
      if (edicaoAtiva && (diaMudou || onibusMudou) && cidadeBateComEdicao) {
        await definirDiaDaInstituicao(
          Number(edicaoAtiva),
          salva.id,
          campos.dia_evento_id ? Number(campos.dia_evento_id) : null,
          Number(campos.onibus) || 0,
        );
      }

      // O monitor responsavel tambem e por edicao e mora na atribuicao do
      // monitor: outra chamada, mesmo formulario.
      if (
        emEdicao &&
        edicaoAtiva &&
        String(campos.monitor_id ?? "") !== String(emEdicao.monitor_responsavel_id ?? "")
      ) {
        await definirMonitorResponsavel(
          Number(edicaoAtiva),
          emEdicao.id,
          campos.monitor_id ? Number(campos.monitor_id) : null,
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
          <Rabisco className="pagina__onda" />
          <p className="pagina__lede">
            Continuam de um ano para o outro. <strong>O dia do evento é definido aqui.</strong>
          </p>
        </div>

        {/* Imprimir no alto, so o icone: o mesmo lugar e o mesmo botao das
            outras telas que imprimem. */}
        <div className="pagina__acoes">
          <Button
            size="sm"
            variant="ghost"
            soIcone
            titulo="Imprimir lista"
            iconLeft={<Imprimir t={15} />}
            onClick={() => definirImprimindo(true)}
            disabled={instituicoes.length === 0}
          />
          <Button size="sm" onClick={abrirNova} disabled={cidades.length === 0}>
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
                  {rotuloDia(d.data, d.descricao)}
                </option>
              ))}
            </Selecao>

            {/* Anda junto com o dia: onibus e o transporte PARA aquele dia, e
                sem dia marcado nao ha o que combinar. */}
            <Entrada
              rotulo="Qtde. ônibus"
              tipo="number"
              min={0}
              max={99}
              value={campos.onibus}
              onChange={(e) => mudar("onibus", e.target.value)}
              disabled={!edicaoAtiva || !campos.dia_evento_id || !cidadeBateComEdicao}
              dica={
                campos.dia_evento_id
                  ? "Quantos ônibus buscam esta instituição no dia dela."
                  : "Marque o dia acima para combinar o transporte."
              }
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

            {/* As opcoes sao so os monitores ja atribuidos a esta instituicao
                (em Usuarios). Sem nenhum, nao ha o que escolher. */}
            <Selecao
              rotulo={`Monitor responsável${edicaoSelecionada ? ` · ${edicaoSelecionada.nome}` : ""}`}
              value={campos.monitor_id}
              onChange={(e) => mudar("monitor_id", e.target.value)}
              disabled={!emEdicao || !monitores || monitores.length === 0}
              dica={(() => {
                if (!emEdicao) return "Salve a instituição e atribua monitores a ela em Usuários para escolher o responsável.";
                if (!monitores) return "Carregando os monitores...";
                if (monitores.length === 0)
                  return "Nenhum monitor atribuído a esta instituição nesta edição. Atribua em Usuários.";
                const escolhido = monitores.find((m) => String(m.usuario_id) === String(campos.monitor_id));
                if (escolhido)
                  return `${doisNomes(escolhido.nome)} · ${escolhido.whatsapp || "sem telefone cadastrado"}`;
                return "Só aparecem os monitores atribuídos a esta instituição.";
              })()}
            >
              <option value="">
                {monitores && monitores.length === 0 ? "Nenhum monitor atribuído" : "Sem monitor responsável"}
              </option>
              {(monitores ?? []).map((m) => (
                <option key={m.usuario_id} value={m.usuario_id}>
                  {doisNomes(m.nome)}
                </option>
              ))}
            </Selecao>

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
          {/* Sem `tabela--larga` no celular: e a largura minima de 680px dela
              que fazia a lista rolar de lado. Sem colunas demais, a tabela de
              layout automatico cabe na tela e nao rola mais. */}
          <table className={`tabela tabela--instituicoes ${estreita ? "tabela--compacta" : "tabela--larga"}`}>
            {!estreita && (
              <caption className="tabela-dica">
                Arraste a lista para o lado para ver todas as colunas.
              </caption>
            )}
            <thead>
              <tr>
                <th>Nome</th>
                {!estreita && (
                  <>
                    <th>Sigla</th>
                    <th>Dia do evento</th>
                    <th>Qtde. ônibus</th>
                  </>
                )}
                <th>Crianças</th>
                {!estreita && (
                  <>
                    <th>Responsável Inst.</th>
                    <th>Monitor Resp.</th>
                    <th>Situação</th>
                  </>
                )}
                <th className="tabela__acoes" />
              </tr>
            </thead>
            <tbody>
              {instituicoes.map((i) => (
                <tr
                  key={i.id}
                  /* No celular a linha inteira abre a janela dos detalhes: o
                     alvo passa a ser a faixa por toda a largura da tela, e nao
                     so os tres pontinhos do canto. O menu continua ali para
                     quem navega por teclado ou leitor de tela — e e por ele
                     que as acoes continuam acessiveis. */
                  onClick={estreita ? () => definirDetalhe(i) : undefined}
                >
                  <td>
                    {i.nome}
                    {/* So informativo, e so no monitor: o endereco vem miudo e
                        apagado, para a lista continuar sendo lida pelo nome. No
                        celular a linha fica como estava. */}
                    {!estreita && i.endereco && (
                      <div className="tabela__nota tabela__nota--uma-linha" title={i.endereco}>
                        {i.endereco}
                      </div>
                    )}
                  </td>
                  {!estreita && (
                    <>
                      <td>
                        <span className="etiqueta etiqueta--neutra">{i.sigla ?? "—"}</span>
                      </td>
                      <td>
                        {i.dia_evento ? (
                          <EtiquetaDia data={i.dia_evento} descricao={i.dia_evento_descricao} />
                        ) : (
                          // Sem etiqueta: nesta coluna a pilula e o dia, e uma
                          // pilula para a ausencia dele pesaria mais que os dias
                          // de verdade — que agora sao discretos de proposito.
                          <span className="dia-vazio">sem dia</span>
                        )}
                      </td>
                      {/* Zero aparece como travessao: o transporte ainda nao foi
                          combinado, e um "0" se leria como "nao precisa". */}
                      <td>{i.onibus || "—"}</td>
                    </>
                  )}
                  <td>{i.criancas}</td>
                  {!estreita && (
                    <>
                      <td>
                        <PessoaNaCelula nome={i.responsavel} telefone={i.telefone} />
                      </td>
                      <td>
                        <PessoaNaCelula
                          nome={i.monitor_responsavel && doisNomes(i.monitor_responsavel)}
                          telefone={i.monitor_responsavel_whatsapp}
                        />
                      </td>
                      <td>
                        <span className={`etiqueta ${i.ativo ? "etiqueta--ok" : "etiqueta--neutra"}`}>
                          {i.ativo ? "Ativa" : "Inativa"}
                        </span>
                      </td>
                    </>
                  )}
                  <td className="tabela__acoes" onClick={(e) => e.stopPropagation()}>
                    <MenuAcoes
                      titulo={`Ações de ${i.nome}`}
                      itens={[
                        // So no celular: no monitor a linha ja mostra tudo o
                        // que a janela mostraria.
                        estreita && {
                          rotulo: "Ver detalhes",
                          aoEscolher: () => definirDetalhe(i),
                        },
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

      {detalhe && (
        <FichaSimples
          rotulo="Instituição:"
          titulo={detalhe.nome}
          aoFechar={() => definirDetalhe(null)}
          campos={[
            { rotulo: "Sigla", valor: detalhe.sigla },
            {
              rotulo: "Dia do evento",
              valor: detalhe.dia_evento ? (
                <EtiquetaDia
                  data={detalhe.dia_evento}
                  descricao={detalhe.dia_evento_descricao}
                />
              ) : (
                <span className="dia-vazio">sem dia</span>
              ),
            },
            { rotulo: "Qtde. ônibus", valor: detalhe.onibus || null },
            { rotulo: "Crianças", valor: detalhe.criancas },
            { rotulo: "Responsável", valor: detalhe.responsavel },
            { rotulo: "Telefone", valor: detalhe.telefone },
            {
              rotulo: "Situação",
              valor: (
                <span className={`etiqueta ${detalhe.ativo ? "etiqueta--ok" : "etiqueta--neutra"}`}>
                  {detalhe.ativo ? "Ativa" : "Inativa"}
                </span>
              ),
            },
          ]}
        />
      )}

      {imprimindo && (
        <ImprimirLista
          titulo="Instituições"
          subtitulo={edicaoSelecionada?.nome ?? "Instituições"}
          aoFechar={() => definirImprimindo(false)}
          // A tela ja tem a lista inteira: nao ha paginacao aqui.
          buscarTudo={async () => instituicoes}
          colunas={[
            { id: "nome", rotulo: "Instituição", valor: (i) => i.nome },
            { id: "sigla", rotulo: "Sigla", valor: (i) => i.sigla ?? "" },
            { id: "endereco", rotulo: "Endereço", valor: (i) => i.endereco ?? "" },
            {
              id: "dia",
              rotulo: "Dia do evento",
              valor: (i) => (i.dia_evento ? rotuloDia(i.dia_evento, i.dia_evento_descricao) : ""),
            },
            { id: "onibus", rotulo: "Qtde. ônibus", valor: (i) => i.onibus || "" },
            { id: "criancas", rotulo: "Crianças", valor: (i) => i.criancas },
            { id: "responsavel", rotulo: "Responsável Inst.", valor: (i) => i.responsavel ?? "" },
            { id: "telefone", rotulo: "Telefone Inst.", valor: (i) => i.telefone ?? "" },
            {
              id: "monitor",
              rotulo: "Monitor Resp.",
              valor: (i) => (i.monitor_responsavel ? doisNomes(i.monitor_responsavel) : ""),
            },
            {
              id: "telefone_monitor",
              rotulo: "Telefone Monitor",
              valor: (i) => i.monitor_responsavel_whatsapp ?? "",
            },
            { id: "situacao", rotulo: "Situação", valor: (i) => (i.ativo ? "Ativa" : "Inativa") },
          ]}
          /* Deitada: com os dois contatos sao muitas colunas de texto. */
          sugestao={{
            colunas: [
              "nome",
              "sigla",
              "endereco",
              "dia",
              "onibus",
              "criancas",
              "responsavel",
              "telefone",
              "monitor",
              "telefone_monitor",
            ],
            orientacao: "paisagem",
            ordenarPor: "nome",
          }}
          agrupamentos={[
            {
              id: "dia",
              rotulo: "Dia do evento",
              de: (i) => (i.dia_evento ? rotuloDia(i.dia_evento, i.dia_evento_descricao) : null),
            },
            { id: "situacao", rotulo: "Situação", de: (i) => (i.ativo ? "Ativas" : "Inativas") },
          ]}
          ordenacoes={[
            { id: "nome", rotulo: "Nome", de: (i) => i.nome },
            { id: "sigla", rotulo: "Sigla", de: (i) => i.sigla },
            { id: "dia", rotulo: "Dia do evento", de: (i) => i.dia_evento },
          ]}
        />
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
