import { useEffect, useState } from "react";
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
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";
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
  editarCidade,
  editarEdicao,
  listarCidades,
  listarDias,
  listarEdicoes,
} from "../services/cadastros.js";

const CIDADE_VAZIA = { nome: "", uf: "" };
const EDICAO_VAZIA = {
  cidade_id: "",
  ano: new Date().getFullYear(),
  nome: "",
  valor_cesta: "120.00",
  valor_festa: "60.00",
};

/* O que a janela de exclusao diz alem da conta. E o ponto que a contagem
   sozinha nao ensina: o que NAO vai junto, e quando desativar resolve melhor
   do que apagar. */
const NOTA_CIDADE =
  "Uma cidade que só não participa este ano não precisa ser apagada: deixe-a " +
  "inativa e o histórico dos anos anteriores continua de pé.";
const NOTA_EDICAO =
  "As instituições da cidade não vão junto — o cadastro delas atravessa os " +
  "anos. Sai o que era deste ano.";

export default function CidadesEdicoes() {
  // Criar, renomear ou apagar uma edicao muda o seletor da lateral: a lista de
  // la e a mesma, e precisa saber.
  const { recarregarEdicoes } = useSessao();

  const [cidades, definirCidades] = useState([]);
  const [edicoes, definirEdicoes] = useState([]);
  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const notificar = useNotificar();
  const [salvando, definirSalvando] = useState(false);

  // Toda acao desta tela acontece dentro de uma janela: cadastrar, editar,
  // ver os dias, apagar. Formulario aberto no meio da pagina empurrava a
  // planilha para baixo e deixava quem preenchia sem saber em que linha
  // estava mexendo.
  //
  // `registro` em null quer dizer "e um cadastro novo"; preenchido, e edicao
  // daquele registro.
  // A lista de cidades e a dos dias tem quatro colunas curtas e cabem em
  // qualquer tela; a de edicoes tem sete e nao cabe. So ela encolhe no celular,
  // e o que sai dela vai para uma janela, a um toque.
  const estreita = useTelaEstreita();
  const [detalheEdicao, definirDetalheEdicao] = useState(null);

  const [formCidade, definirFormCidade] = useState(null);
  const [formEdicao, definirFormEdicao] = useState(null);

  // Os dias da edicao, numa janela propria: { edicao, lista, novo }.
  const [dias, definirDias] = useState(null);

  // A exclusao em curso: { tipo, registro, dependencias, erro, apagando }.
  // Tudo num objeto so porque a conta que chega do servidor precisa ser
  // casada com o registro que a pediu — trocar de alvo com a resposta no ar
  // nao pode acabar mostrando a conta de um em cima do nome do outro.
  const [exclusao, definirExclusao] = useState(null);

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

  function limparErro() {
    definirErro("");
  }

  // ---------------------------------------------------------------- cidades

  function abrirFormCidade(registro = null) {
    limparErro();
    definirFormCidade({
      registro,
      campos: registro ? { nome: registro.nome, uf: registro.uf } : CIDADE_VAZIA,
    });
  }

  function mudarCidade(campo, valor) {
    definirFormCidade((atual) => ({
      ...atual,
      campos: { ...atual.campos, [campo]: valor },
    }));
  }

  async function salvarCidade(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);

    const { registro, campos } = formCidade;
    const corpo = {
      nome: campos.nome.trim(),
      uf: campos.uf.trim().toUpperCase(),
      // O PATCH da cidade pede a ficha inteira: sem repetir a situacao aqui,
      // editar o nome de uma cidade inativa a reativaria sem querer.
      ativo: registro ? registro.ativo : true,
    };

    try {
      if (registro) {
        const salva = await editarCidade(registro.id, corpo);
        definirCidades((l) => l.map((c) => (c.id === salva.id ? salva : c)));
        notificar(`${salva.nome} atualizada.`);
      } else {
        const nova = await criarCidade(corpo);
        definirCidades((l) =>
          [...l, nova].sort((a, b) => a.nome.localeCompare(b.nome)),
        );
        notificar(`${nova.nome} cadastrada.`);
      }
      definirFormCidade(null);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function alternarCidade(cidade) {
    limparErro();
    try {
      const salva = await editarCidade(cidade.id, {
        nome: cidade.nome,
        uf: cidade.uf,
        ativo: !cidade.ativo,
      });
      definirCidades((l) => l.map((c) => (c.id === salva.id ? salva : c)));
    } catch (e) {
      definirErro(e.message);
    }
  }

  // ---------------------------------------------------------------- edicoes

  function abrirFormEdicao(registro = null) {
    limparErro();
    definirFormEdicao({
      registro,
      campos: registro
        ? {
            cidade_id: registro.cidade_id,
            ano: registro.ano,
            nome: registro.nome,
            valor_cesta: registro.valor_cesta,
            valor_festa: registro.valor_festa,
          }
        : { ...EDICAO_VAZIA, cidade_id: cidades[0]?.id ?? "" },
    });
  }

  function mudarEdicao(campo, valor) {
    definirFormEdicao((atual) => ({
      ...atual,
      campos: { ...atual.campos, [campo]: valor },
    }));
  }

  async function salvarEdicao(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);

    const { registro, campos } = formEdicao;

    try {
      if (registro) {
        // Cidade e ano nao entram: sao a identidade da edicao, e o servidor
        // nem aceita muda-los.
        const salva = await editarEdicao(registro.id, {
          nome: campos.nome.trim(),
          valor_cesta: campos.valor_cesta,
          valor_festa: campos.valor_festa,
        });
        definirEdicoes((l) => l.map((e) => (e.id === salva.id ? salva : e)));
        recarregarEdicoes().catch(() => {});
        notificar(`${salva.nome} atualizada.`);
      } else {
        const nova = await criarEdicao({
          cidade_id: Number(campos.cidade_id),
          ano: Number(campos.ano),
          nome: campos.nome.trim(),
          valor_cesta: campos.valor_cesta,
          valor_festa: campos.valor_festa,
        });
        definirEdicoes((l) => [nova, ...l]);
        recarregarEdicoes().catch(() => {});
        notificar(`${nova.nome} criada.`);
      }
      definirFormEdicao(null);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function alternarEdicao(edicao) {
    limparErro();
    try {
      const salva = await editarEdicao(edicao.id, { ativa: !edicao.ativa });
      definirEdicoes((l) => l.map((e) => (e.id === salva.id ? salva : e)));
    } catch (e) {
      definirErro(e.message);
    }
  }

  // ------------------------------------------------------------------- dias

  async function abrirDias(edicao) {
    limparErro();
    definirDias({ edicao, lista: null, novo: { data: "", descricao: "" }, erro: "" });
    try {
      const lista = await listarDias(edicao.id);
      definirDias((atual) =>
        atual && atual.edicao.id === edicao.id ? { ...atual, lista } : atual,
      );
    } catch (e) {
      definirDias((atual) => (atual ? { ...atual, erro: e.message, lista: [] } : atual));
    }
  }

  function mudarNovoDia(campo, valor) {
    definirDias((atual) => ({ ...atual, novo: { ...atual.novo, [campo]: valor } }));
  }

  async function adicionarDia(evento) {
    evento.preventDefault();
    definirDias((atual) => ({ ...atual, erro: "" }));
    try {
      const dia = await criarDia(dias.edicao.id, {
        data: dias.novo.data,
        descricao: dias.novo.descricao.trim() || null,
      });
      definirDias((atual) => ({
        ...atual,
        // `?? []` porque da para preencher a data antes de a lista chegar.
        lista: [...(atual.lista ?? []), dia].sort((a, b) => a.data.localeCompare(b.data)),
        novo: { data: "", descricao: "" },
      }));
    } catch (e) {
      definirDias((atual) => ({ ...atual, erro: e.message }));
    }
  }

  async function removerDia(dia) {
    definirDias((atual) => ({ ...atual, erro: "" }));
    try {
      await apagarDia(dias.edicao.id, dia.id);
      definirDias((atual) => ({
        ...atual,
        lista: atual.lista.filter((d) => d.id !== dia.id),
      }));
    } catch (e) {
      definirDias((atual) => ({ ...atual, erro: e.message }));
    }
  }

  // -------------------------------------------------------------- exclusao

  async function pedirExclusao(tipo, registro) {
    limparErro();
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

  async function confirmarExclusao(senha) {
    const { tipo, registro } = exclusao;
    definirExclusao((atual) => ({ ...atual, apagando: true, erro: "" }));

    try {
      if (tipo === "cidade") {
        await apagarCidade(registro.id, senha);
        definirCidades((l) => l.filter((c) => c.id !== registro.id));
        // As edicoes da cidade foram junto, no servidor: a lista da tela
        // precisa perder as dela tambem, senao sobram linhas apontando para
        // uma cidade que nao existe mais.
        definirEdicoes((l) => l.filter((e) => e.cidade_id !== registro.id));
        if (dias?.edicao.cidade_id === registro.id) definirDias(null);
      } else {
        await apagarEdicao(registro.id, senha);
        definirEdicoes((l) => l.filter((e) => e.id !== registro.id));
        if (dias?.edicao.id === registro.id) definirDias(null);
      }
      recarregarEdicoes().catch(() => {});
      notificar(`${registro.nome} apagada.`);
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
      <Rabisco className="pagina__onda" />
      <p className="pagina__lede">
        Cada cidade num ano é uma edição, com os próprios valores de cesta e festa.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>

      <h2 className="painel__titulo">Cidades</h2>
      <div className="barra-acoes">
        <Button variant="secondary" size="sm" onClick={() => abrirFormCidade()}>
          Nova cidade
        </Button>
      </div>

      {cidades.length === 0 ? (
        <EmptyState
          titulo="Nenhuma cidade cadastrada"
          corpo="Comece cadastrando a cidade, depois crie a edição do ano."
        />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr><th>Cidade</th><th>UF</th><th>Situação</th><th className="tabela__acoes" /></tr>
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
                  <td className="tabela__acoes">
                    <MenuAcoes
                      titulo={`Ações de ${c.nome}`}
                      itens={[
                        { rotulo: "Editar", aoEscolher: () => abrirFormCidade(c) },
                        {
                          rotulo: c.ativo ? "Desativar" : "Ativar",
                          aoEscolher: () => alternarCidade(c),
                        },
                        {
                          rotulo: "Apagar",
                          perigo: true,
                          aoEscolher: () => pedirExclusao("cidade", c),
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

      <h2 className="painel__titulo" style={{ marginTop: "var(--space-7)" }}>Edições</h2>
      <div className="barra-acoes">
        <Button size="sm" onClick={() => abrirFormEdicao()} disabled={cidades.length === 0}>
          Nova edição
        </Button>
        {cidades.length === 0 && (
          <span className="campo__dica">Cadastre uma cidade primeiro.</span>
        )}
      </div>

      {edicoes.length === 0 ? (
        <EmptyState
          titulo="Nenhuma edição criada"
          corpo="A edição é o que liga crianças, padrinhos e equipe a um ano e uma cidade."
        />
      ) : (
        <div className="tabela-rolagem">
          {/* Sem `tabela--larga` no celular: e a largura minima dela que fazia
              a lista rolar de lado. */}
          <table className={`tabela ${estreita ? "tabela--compacta" : "tabela--larga"}`}>
            {!estreita && (
              <caption className="tabela-dica">
                Arraste a lista para o lado para ver todas as colunas.
              </caption>
            )}
            <thead>
              <tr>
                <th>Edição</th>
                {!estreita && (
                  <>
                    <th>Cidade</th>
                    <th>Ano</th>
                    <th>Cesta</th>
                    <th>Festa</th>
                  </>
                )}
                <th>Situação</th>
                <th className="tabela__acoes" />
              </tr>
            </thead>
            <tbody>
              {edicoes.map((e) => (
                <tr
                  key={e.id}
                  onClick={estreita ? () => definirDetalheEdicao(e) : undefined}
                >
                  <td>{e.nome}</td>
                  {!estreita && (
                    <>
                      <td>{e.cidade} · {e.uf}</td>
                      <td>{e.ano}</td>
                      <td>{dinheiro(e.valor_cesta)}</td>
                      <td>{dinheiro(e.valor_festa)}</td>
                    </>
                  )}
                  <td>
                    <span className={`etiqueta ${e.ativa ? "etiqueta--ok" : "etiqueta--neutra"}`}>
                      {e.ativa ? "Ativa" : "Encerrada"}
                    </span>
                  </td>
                  <td className="tabela__acoes" onClick={(ev) => ev.stopPropagation()}>
                    <MenuAcoes
                      titulo={`Ações de ${e.nome}`}
                      itens={[
                        estreita && {
                          rotulo: "Ver detalhes",
                          aoEscolher: () => definirDetalheEdicao(e),
                        },
                        { rotulo: "Editar", aoEscolher: () => abrirFormEdicao(e) },
                        { rotulo: "Dias do evento", aoEscolher: () => abrirDias(e) },
                        {
                          rotulo: e.ativa ? "Encerrar" : "Reabrir",
                          aoEscolher: () => alternarEdicao(e),
                        },
                        {
                          rotulo: "Apagar",
                          perigo: true,
                          aoEscolher: () => pedirExclusao("edicao", e),
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

      {formCidade && (
        <Modal
          rotulo="Cidade"
          titulo={formCidade.registro ? `Editar ${formCidade.registro.nome}` : "Nova cidade"}
          aoFechar={() => !salvando && definirFormCidade(null)}
        >
          <form onSubmit={salvarCidade}>
            <Entrada
              rotulo="Nome"
              value={formCidade.campos.nome}
              onChange={(e) => mudarCidade("nome", e.target.value)}
              required
            />
            <Entrada
              rotulo="UF"
              value={formCidade.campos.uf}
              onChange={(e) => mudarCidade("uf", e.target.value.toUpperCase())}
              maxLength={2}
              required
            />
            <div className="barra-acoes barra-acoes--fim">
              <Button variant="secondary" type="submit" carregando={salvando}>
                {salvando ? "Salvando..." : "Salvar"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => definirFormCidade(null)}
                disabled={salvando}
              >
                Cancelar
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {formEdicao && (
        <Modal
          rotulo="Edição"
          titulo={formEdicao.registro ? `Editar ${formEdicao.registro.nome}` : "Nova edição"}
          aoFechar={() => !salvando && definirFormEdicao(null)}
        >
          <form onSubmit={salvarEdicao}>
            {/* Cidade e ano sao a identidade da edicao e nao mudam depois de
                criada — na edicao eles aparecem so para situar quem abriu. */}
            {formEdicao.registro ? (
              <p className="campo__dica" style={{ marginTop: 0 }}>
                {formEdicao.registro.cidade} · {formEdicao.registro.uf} ·{" "}
                {formEdicao.registro.ano}
              </p>
            ) : (
              <>
                <Selecao
                  rotulo="Cidade"
                  value={formEdicao.campos.cidade_id}
                  onChange={(e) => mudarEdicao("cidade_id", e.target.value)}
                  required
                >
                  {cidades.map((c) => (
                    <option key={c.id} value={c.id}>{c.nome} · {c.uf}</option>
                  ))}
                </Selecao>
                <Entrada
                  rotulo="Ano"
                  tipo="number"
                  value={formEdicao.campos.ano}
                  onChange={(e) => mudarEdicao("ano", e.target.value)}
                  required
                />
              </>
            )}

            <Entrada
              rotulo="Nome da edição"
              value={formEdicao.campos.nome}
              onChange={(e) => mudarEdicao("nome", e.target.value)}
              dica="Ex.: Fortaleza 2026"
              required
            />
            <Entrada
              rotulo="Valor da cesta"
              tipo="number"
              step="0.01"
              value={formEdicao.campos.valor_cesta}
              onChange={(e) => mudarEdicao("valor_cesta", e.target.value)}
              required
            />
            <Entrada
              rotulo="Valor da festa"
              tipo="number"
              step="0.01"
              value={formEdicao.campos.valor_festa}
              onChange={(e) => mudarEdicao("valor_festa", e.target.value)}
              dica="Vale para os apadrinhamentos registrados daqui para a frente; os já combinados guardam o valor do dia."
              required
            />

            <div className="barra-acoes barra-acoes--fim">
              <Button variant="secondary" type="submit" carregando={salvando}>
                {salvando ? "Salvando..." : "Salvar"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => definirFormEdicao(null)}
                disabled={salvando}
              >
                Cancelar
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {dias && (
        /* `grande`: a lista muda com a janela aberta (adicionar, apagar), e
           com a altura acompanhando o conteudo a janela pularia embaixo do
           ponteiro a cada acao. */
        <Modal
          rotulo="Dias do evento"
          titulo={dias.edicao.nome}
          tamanho="grande"
          aoFechar={() => definirDias(null)}
        >
          <Mensagem tipo="erro">{dias.erro}</Mensagem>

          <p className="campo__dica" style={{ marginTop: 0 }}>
            Cada criança vai a um único dia, e quem define o dia é a instituição.
            Um dia só pode ser apagado quando não tem criança marcada.
          </p>

          {dias.lista === null ? (
            <Carregando>Carregando os dias...</Carregando>
          ) : dias.lista.length === 0 ? (
            <EmptyState
              titulo="Nenhum dia cadastrado"
              corpo="Cadastre os dias do evento para poder marcar em qual cada instituição vai."
            />
          ) : (
            <div className="tabela-rolagem">
              <table className="tabela">
                <thead>
                  <tr><th>Data</th><th>Descrição</th><th>Crianças</th><th className="tabela__acoes" /></tr>
                </thead>
                <tbody>
                  {dias.lista.map((d) => (
                    <tr key={d.id}>
                      <td>{formatarData(d.data)}</td>
                      <td>{d.descricao ?? "—"}</td>
                      <td>{d.total_criancas}</td>
                      <td className="tabela__acoes">
                        <MenuAcoes
                          titulo={`Ações de ${formatarData(d.data)}`}
                          itens={[
                            {
                              rotulo: "Apagar",
                              perigo: true,
                              // Com crianca marcada o servidor recusa. Travar
                              // aqui tambem evita o clique que so traz erro.
                              disabled: d.total_criancas > 0,
                              aoEscolher: () => removerDia(d),
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

          <form onSubmit={adicionarDia} style={{ marginTop: "var(--space-6)" }}>
            <div className="linha-campos">
              <Entrada
                rotulo="Data"
                tipo="date"
                value={dias.novo.data}
                onChange={(e) => mudarNovoDia("data", e.target.value)}
              />
              <Entrada
                rotulo="Descrição"
                value={dias.novo.descricao}
                onChange={(e) => mudarNovoDia("descricao", e.target.value)}
                dica="Opcional. Ex.: Sábado de manhã"
              />
            </div>
            <Button variant="secondary" type="submit" size="sm" disabled={!dias.novo.data}>
              Adicionar dia
            </Button>
          </form>
        </Modal>
      )}

      {detalheEdicao && (
        <FichaSimples
          rotulo="Edição:"
          titulo={detalheEdicao.nome}
          aoFechar={() => definirDetalheEdicao(null)}
          campos={[
            { rotulo: "Cidade", valor: `${detalheEdicao.cidade} · ${detalheEdicao.uf}` },
            { rotulo: "Ano", valor: detalheEdicao.ano },
            { rotulo: "Cesta", valor: dinheiro(detalheEdicao.valor_cesta) },
            { rotulo: "Festa", valor: dinheiro(detalheEdicao.valor_festa) },
            {
              rotulo: "Situação",
              valor: (
                <span className={`etiqueta ${detalheEdicao.ativa ? "etiqueta--ok" : "etiqueta--neutra"}`}>
                  {detalheEdicao.ativa ? "Ativa" : "Encerrada"}
                </span>
              ),
            },
          ]}
        />
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
          /* Edicao e cidade levam um ano inteiro junto: a senha de quem
             apaga, de novo, alem da janela (o servidor confere). */
          pedirSenha
          aoConfirmar={confirmarExclusao}
          aoFechar={() => definirExclusao(null)}
        />
      )}
    </div>
  );
}
