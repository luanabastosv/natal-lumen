import { useCallback, useEffect, useState } from "react";
import BotaoIcone from "../components/core/BotaoIcone.jsx";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import FaixaDeAbas from "../components/core/FaixaDeAbas.jsx";
import { Olho, Xis } from "../components/core/icones.jsx";
import CelulaEditavel from "../components/dados/CelulaEditavel.jsx";
import FichaCrianca from "../components/dados/FichaCrianca.jsx";
import { rotuloDoPerfil } from "../components/dados/perfis.js";
import Carregando from "../components/feedback/Carregando.jsx";
import ConfirmarExclusao from "../components/feedback/ConfirmarExclusao.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";
import { listarInstituicoes } from "../services/cadastros.js";
import {
  apagarCrianca,
  criarCrianca,
  dependenciasDaCrianca,
  editarCrianca,
  editarEmLote,
  listarComissarios,
  listarCriancas,
  resumoInstituicoes,
} from "../services/criancas.js";
import EtiquetaDia from "../components/core/EtiquetaDia.jsx";
import { tomDoDia } from "../utils/dias.js";
import ImportarLista from "./ImportarLista.jsx";

/** Como um responsavel se escreve nas listas desta tela.
 *
 *  A lista e quase toda de comissarios, e para eles o nome basta. Coordenacao e
 *  administracao geral tambem podem ficar com uma crianca no nome — mas sao
 *  poucas pessoas e alcancam a cidade inteira, entao aparecer ali sem aviso
 *  faria parecer que sao mais um comissario do time daquela escola.
 */
function comoAparece(membro) {
  return membro.papel === "Comissario"
    ? membro.nome
    : `${membro.nome} · ${rotuloDoPerfil(membro.papel)}`;
}

const POR_PAGINA = 100;
const TODAS = "todas";
const SEM_RESPONSAVEL = "sem";
const NOVA = { instituicao_id: "", codigo: "", nome: "", idade: "", sexo: "F" };

/* O que a janela de exclusao diz alem da conta. Desistencia e quase sempre o
   caminho certo: guarda o cadastro e so tira a crianca do evento — e da para
   voltar atras ate a vespera. */
const NOTA_CRIANCA =
  "Se a criança apenas não vai ao evento, marque desistência na ficha dela em " +
  "vez de apagar — isso guarda o histórico e dá para voltar atrás.";

const SEXOS = [
  { valor: "F", rotulo: "F" },
  { valor: "M", rotulo: "M" },
];

export default function Criancas() {
  // A edicao vem da lateral: e a mesma para o sistema inteiro.
  const { pode, edicaoAtiva, edicao } = useSessao();

  const [instituicoes, definirInstituicoes] = useState([]);
  const [abas, definirAbas] = useState([]);
  const [abaAtiva, definirAbaAtiva] = useState(TODAS);

  const [criancas, definirCriancas] = useState({ itens: [], total: 0 });
  const [busca, definirBusca] = useState("");
  const [codigo, definirCodigo] = useState("");
  const [pagina, definirPagina] = useState(1);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const notificar = useNotificar();

  const [marcadas, definirMarcadas] = useState([]);

  // Quem pode responder por uma crianca desta edicao: o time de comissarios e,
  // sem recorte de escola, a coordenacao e a administracao geral. Uma
  // instituicao e atendida por varios deles, e a coluna do responsavel diz
  // quem responde por cada crianca.
  const [comissarios, definirComissarios] = useState([]);
  const [filtroComissario, definirFiltroComissario] = useState("");
  const [atribuindo, definirAtribuindo] = useState(false);

  const [formAberto, definirFormAberto] = useState(false);
  const [campos, definirCampos] = useState(NOVA);
  const [salvando, definirSalvando] = useState(false);
  const [importando, definirImportando] = useState(false);
  const [fichaAberta, definirFichaAberta] = useState(null);

  // A exclusao em curso: { registro, dependencias, erro, apagando }. Num
  // estado so porque as quatro coisas andam juntas — abrir a janela zera as
  // outras tres, e fechar joga tudo fora.
  const [exclusao, definirExclusao] = useState(null);

  const podeEditar = pode("editar_criancas");

  // No celular a planilha inteira nao cabe: ficam de pe as tres colunas que
  // fazem alguem reconhecer a crianca e saber o que falta nela — codigo, nome
  // e os padrinhos — e o resto vai para a ficha, a um toque de distancia.
  const estreita = useTelaEstreita();

  // O check-in so acontece no dia do evento. Ate la a coluna seria uma fileira
  // de "nao" ocupando largura que o nome e a instituicao precisam mais — entao
  // ela so entra quando ha check-in feito.
  //
  // O `some` nao e redundante com a conta do servidor: a ficha aberta na
  // planilha devolve a crianca atualizada, e a coluna tem de aparecer no
  // mesmo instante, sem esperar a proxima busca.
  const mostrarCheckin =
    criancas.com_checkin > 0 || criancas.itens.some((c) => c.checkin_em);

  useEffect(() => {
    let vivo = true;
    listarInstituicoes()
      .then((insts) => vivo && definirInstituicoes(insts))
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, []);

  // Trocar de edicao na lateral recomeca a planilha: as abas, a pagina e as
  // linhas marcadas sao todas da edicao anterior. Ajustado durante o render, e
  // nao por efeito: evita uma busca jogada fora.
  const [ultimaEdicao, definirUltimaEdicao] = useState(edicaoAtiva);
  if (edicaoAtiva !== ultimaEdicao) {
    definirUltimaEdicao(edicaoAtiva);
    definirAbaAtiva(TODAS);
    definirPagina(1);
    definirMarcadas([]);
  }

  // As abas mudam quando a edicao muda.
  useEffect(() => {
    if (!edicaoAtiva) return;
    let vivo = true;
    resumoInstituicoes(edicaoAtiva)
      .then((resumo) => {
        if (!vivo) return;
        definirAbas(resumo);
      })
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, [edicaoAtiva]);

  // O time tambem muda com a edicao: comissario e vinculo por edicao.
  useEffect(() => {
    if (!edicaoAtiva) return;
    let vivo = true;
    listarComissarios(edicaoAtiva)
      .then((time) => vivo && definirComissarios(time))
      .catch(() => vivo && definirComissarios([]));
    return () => {
      vivo = false;
    };
  }, [edicaoAtiva]);

  const buscar = useCallback(async () => {
    try {
      definirCriancas(
        await listarCriancas({
          edicao_id: edicaoAtiva,
          instituicao_id: abaAtiva === TODAS ? "" : abaAtiva,
          comissario_id: filtroComissario === SEM_RESPONSAVEL ? "" : filtroComissario,
          sem_comissario: filtroComissario === SEM_RESPONSAVEL ? true : "",
          busca,
          codigo,
          pagina,
          por_pagina: POR_PAGINA,
        }),
      );
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoAtiva, abaAtiva, filtroComissario, busca, codigo, pagina]);

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer: a
    // lista so chega depois do await, e nao daria para derivar no render.
    // eslint-disable-next-line react/set-state-in-effect
    if (edicaoAtiva) buscar();
  }, [edicaoAtiva, abaAtiva, pagina, buscar]);

  async function recarregarAbas() {
    try {
      definirAbas(await resumoInstituicoes(edicaoAtiva));
    } catch {
      // A planilha e o que importa; as abas atualizam na proxima troca.
    }
  }

  /** Salva uma celula e atualiza só aquela linha, sem recarregar a tabela. */
  async function salvarCampo(crianca, campo, valor) {
    const atualizada = await editarCrianca(crianca.id, { [campo]: valor });
    definirCriancas((atual) => ({
      ...atual,
      itens: atual.itens.map((c) => (c.id === crianca.id ? atualizada : c)),
    }));
    if (campo === "dia_evento_id") recarregarAbas();
  }

  /** Quem alcanca esta instituicao, como opcoes do seletor da coluna. */
  function opcoesComissario(instituicaoId) {
    return [
      // O mesmo texto da celula so-leitura: a coluna diz a mesma coisa para
      // quem edita e para quem so olha.
      { valor: "", rotulo: "sem responsável" },
      ...comissarios
        .filter((c) => c.instituicoes.includes(instituicaoId))
        .map((c) => ({ valor: c.id, rotulo: comoAparece(c) })),
    ];
  }

  /** Poe (ou tira) o responsavel das criancas marcadas, de uma vez. */
  async function atribuirMarcadas(comissarioId) {
    definirErro("");
    definirAtribuindo(true);
    try {
      const atualizadas = await editarEmLote({
        criancas: marcadas,
        comissario_id: comissarioId === SEM_RESPONSAVEL ? null : Number(comissarioId),
      });
      const porId = new Map(atualizadas.map((c) => [c.id, c]));
      definirCriancas((atual) => ({
        ...atual,
        itens: atual.itens.map((c) => porId.get(c.id) ?? c),
      }));
      const nome = comissarios.find((c) => String(c.id) === String(comissarioId))?.nome;
      notificar(
        nome
          ? `${marcadas.length} criança(s) agora com ${nome}.`
          : `${marcadas.length} criança(s) sem responsável.`,
      );
      definirMarcadas([]);
      recarregarAbas();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirAtribuindo(false);
    }
  }

  /** Abre a janela e ja pergunta ao servidor o que vai junto. */
  async function pedirExclusao(crianca) {
    definirErro("");
    definirExclusao({ registro: crianca, dependencias: null, erro: "", apagando: false });
    try {
      const conta = await dependenciasDaCrianca(crianca.id);
      definirExclusao((atual) =>
        atual && atual.registro.id === crianca.id
          ? { ...atual, dependencias: conta }
          : atual,
      );
    } catch (e) {
      definirExclusao((atual) => (atual ? { ...atual, erro: e.message } : atual));
    }
  }

  async function confirmarExclusao() {
    const crianca = exclusao.registro;
    definirExclusao((atual) => ({ ...atual, apagando: true, erro: "" }));
    try {
      await apagarCrianca(crianca.id);
      notificar(`${crianca.nome} removida.`);
      definirExclusao(null);
      buscar();
      recarregarAbas();
    } catch (e) {
      definirExclusao((atual) =>
        atual ? { ...atual, apagando: false, erro: e.message } : atual,
      );
    }
  }

  async function salvarNova(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      await criarCrianca({
        edicao_id: Number(edicaoAtiva),
        instituicao_id: Number(campos.instituicao_id),
        codigo: campos.codigo.trim(),
        nome: campos.nome.trim(),
        idade: Number(campos.idade),
        sexo: campos.sexo,
      });
      notificar(`${campos.nome.trim()} cadastrada.`);
      definirCampos(NOVA);
      definirFormAberto(false);
      buscar();
      recarregarAbas();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  const instituicoesDaCidade = instituicoes.filter((i) => i.cidade_id === edicao?.cidade_id);

  const totalGeral = abas.reduce((soma, a) => soma + a.criancas, 0);
  const totalPaginas = Math.max(1, Math.ceil(criancas.total / POR_PAGINA));

  function alternar(id) {
    definirMarcadas((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));
  }

  // Num lote de escolas diferentes so cabe quem atende TODAS elas: o seletor
  // do lote nao pode oferecer um nome que a conferencia do servidor vai negar.
  const escolasMarcadas = [
    ...new Set(
      criancas.itens.filter((c) => marcadas.includes(c.id)).map((c) => c.instituicao_id),
    ),
  ];
  const comissariosDoLote = comissarios.filter((c) =>
    escolasMarcadas.every((i) => c.instituicoes.includes(i)),
  );

  function marcarTodas() {
    definirMarcadas(
      marcadas.length === criancas.itens.length ? [] : criancas.itens.map((c) => c.id),
    );
  }

  if (importando) {
    return (
      <ImportarLista
        edicao={edicao}
        instituicoes={instituicoesDaCidade}
        aoTerminar={(quantas) => {
          definirImportando(false);
          if (quantas) notificar(`${quantas} criança(s) importada(s).`);
          buscar();
          recarregarAbas();
        }}
      />
    );
  }

  return (
    <div>
      <div className="pagina__cabecalho">
        <div className="pagina__texto">
          <div className="pagina__eyebrow">Dados sensíveis</div>
          <h1 className="pagina__titulo">Crianças</h1>
          <p className="pagina__lede">
            {estreita
              ? "Uma aba por instituição. Toque em Ver ficha para o resto dos dados da criança."
              : "Uma aba por instituição. Clique na célula para editar — Enter salva, Esc desfaz."}
          </p>
        </div>

        {/* Importar e acao da pagina, nao da lista: na folga lateral do titulo
            ela nao custa nenhuma linha de altura. Sem permissao de importar,
            o cabecalho fica so com o texto.

            No celular ela nao aparece: a importacao e escolher um arquivo de
            planilha e conferir o que veio, e isso se faz onde a planilha
            esta. */}
        {pode("importar_listas") && !estreita && (
          <div className="pagina__acoes">
            <Button size="sm" variant="ghost" onClick={() => definirImportando(true)} disabled={!edicao}>
              Importar lista
            </Button>
          </div>
        )}
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {/* Abas: uma por instituição, com o que falta em cada uma. Passam de
          lado por chevron — numa cidade grande são mais de vinte, e elas nunca
          caberiam na largura da tela. */}
      {abas.length > 0 && (
        <FaixaDeAbas reiniciarEm={edicaoAtiva}>
          <button
            type="button"
            role="tab"
            aria-selected={abaAtiva === TODAS}
            className={`aba ${abaAtiva === TODAS ? "aba--ativa" : ""}`}
            onClick={() => {
              definirAbaAtiva(TODAS);
              definirPagina(1);
              definirMarcadas([]);
            }}
          >
            <span>Todas</span>
            <span className="aba__contagem">{totalGeral} crianças</span>
          </button>

          {abas.map((a) => (
            <button
              key={a.instituicao_id}
              type="button"
              role="tab"
              aria-selected={String(abaAtiva) === String(a.instituicao_id)}
              className={`aba ${String(abaAtiva) === String(a.instituicao_id) ? "aba--ativa" : ""}`}
              onClick={() => {
                definirAbaAtiva(a.instituicao_id);
                definirPagina(1);
                definirMarcadas([]);
              }}
              title={`${a.sem_padrinho} sem padrinho · ${a.sem_cartao} sem cartão`}
            >
              <span>
                {a.instituicao}
                {/* O pontinho e o dia, na mesma cor da etiqueta logo abaixo:
                    de longe a faixa de abas vira dois grupos, sabado e
                    domingo. Sem dia marcado nao ha pontinho — a ausencia ja
                    diz que falta resolver aquela escola. */}
                {a.dia_evento && (
                  <span className={`aba__ponto dia--${tomDoDia(a.dia_evento_descricao)}`} />
                )}
              </span>
              <span className="aba__contagem">
                {a.criancas}
                {a.dia_evento ? (
                  <EtiquetaDia data={a.dia_evento} descricao={a.dia_evento_descricao} />
                ) : (
                  <>· sem dia</>
                )}
              </span>
            </button>
          ))}
        </FaixaDeAbas>
      )}

      <form
        className="barra-acoes"
        onSubmit={(e) => {
          e.preventDefault();
          definirPagina(1);
          buscar();
        }}
      >
        {/* O campo do nome e o unico que sobrevive ao celular: e a busca que
            se faz de pe, com a lista da instituicao na mao. Sozinho num
            formulario, ele ainda submete no Enter — o teclado do celular mostra
            "Buscar" na tecla, e nenhum botao precisa ocupar a linha. */}
        <Entrada
          value={busca}
          onChange={(e) => definirBusca(e.target.value)}
          placeholder="Buscar por nome"
        />

        {/* Busca por código exato, filtro de responsável, contagem e o CTA de
            cadastrar sao trabalho de mesa: no celular a barra inteira nao cabe
            numa linha, e empilhada empurrava a lista para fora da primeira
            tela. Quem cadastra e filtra faz isso no computador. */}
        {!estreita && (
          <>
            <Entrada
              value={codigo}
              onChange={(e) => definirCodigo(e.target.value)}
              placeholder="Código exato"
            />
            {comissarios.length > 0 && (
              <Selecao
                value={filtroComissario}
                onChange={(e) => {
                  definirFiltroComissario(e.target.value);
                  definirPagina(1);
                  definirMarcadas([]);
                }}
                aria-label="Filtrar por responsável"
              >
                <option value="">Todos os responsáveis</option>
                <option value={SEM_RESPONSAVEL}>Sem responsável</option>
                {comissarios.map((c) => (
                  <option key={c.id} value={c.id}>{comoAparece(c)}</option>
                ))}
              </Selecao>
            )}
            <Button type="submit" size="sm" variant="ghost">Buscar</Button>
            {(busca || codigo) && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  definirBusca("");
                  definirCodigo("");
                  definirFiltroComissario("");
                  definirPagina(1);
                }}
              >
                Limpar
              </Button>
            )}
            <span className="campo__dica">{criancas.total} nesta aba</span>

            {/* Na ponta oposta da linha: o CTA da pagina fica longe dos campos
                de busca, sem roubar uma linha so para ele. */}
            {podeEditar && (
              <div className="barra-acoes__ponta">
                <Button
                  size="sm"
                  onClick={() => {
                    definirCampos({
                      ...NOVA,
                      instituicao_id:
                        abaAtiva !== TODAS ? abaAtiva : (instituicoesDaCidade[0]?.id ?? ""),
                    });
                    definirFormAberto(true);
                  }}
                  disabled={instituicoesDaCidade.length === 0}
                >
                  Nova criança
                </Button>
              </div>
            )}
          </>
        )}
      </form>

      {formAberto && (
        <Modal titulo="Nova criança" aoFechar={() => !salvando && definirFormAberto(false)}>
          <form onSubmit={salvarNova}>
            <div className="linha-campos">
              <Selecao
                rotulo="Instituição"
                value={campos.instituicao_id}
                onChange={(e) => definirCampos({ ...campos, instituicao_id: e.target.value })}
                required
              >
                {instituicoesDaCidade.map((i) => (
                  <option key={i.id} value={i.id}>{i.nome}</option>
                ))}
              </Selecao>
              <Entrada rotulo="Código" value={campos.codigo}
                onChange={(e) => definirCampos({ ...campos, codigo: e.target.value })} required />
              <Entrada rotulo="Nome" value={campos.nome}
                onChange={(e) => definirCampos({ ...campos, nome: e.target.value })} required />
              <Entrada rotulo="Idade" tipo="number" min="0" max="21" value={campos.idade}
                onChange={(e) => definirCampos({ ...campos, idade: e.target.value })} required />
              <Selecao rotulo="Sexo" value={campos.sexo}
                onChange={(e) => definirCampos({ ...campos, sexo: e.target.value })}>
                <option value="F">Feminino</option>
                <option value="M">Masculino</option>
              </Selecao>
            </div>
            <div className="barra-acoes barra-acoes--fim">
              <Button variant="secondary" type="submit" carregando={salvando}>Salvar</Button>
              <Button variant="ghost" onClick={() => definirFormAberto(false)} disabled={salvando}>
                Cancelar
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {fichaAberta && (
        <FichaCrianca
          criancaId={fichaAberta}
          aoFechar={() => definirFichaAberta(null)}
          podeEditar={podeEditar}
          /* Troca so a linha mexida: recarregar a tabela inteira perderia a
             posicao de quem estava no meio da planilha. */
          aoMudar={(atualizada) =>
            definirCriancas((atual) => ({
              ...atual,
              itens: atual.itens.map((c) => (c.id === atualizada.id ? atualizada : c)),
            }))
          }
        />
      )}

      {exclusao && (
        <ConfirmarExclusao
          rotulo="Criança"
          nome={exclusao.registro.nome}
          dependencias={exclusao.dependencias}
          nota={NOTA_CRIANCA}
          erro={exclusao.erro}
          apagando={exclusao.apagando}
          aoConfirmar={confirmarExclusao}
          aoFechar={() => definirExclusao(null)}
        />
      )}

      {carregando ? (
        <Carregando tela>Carregando crianças...</Carregando>
      ) : criancas.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhuma criança aqui"
          corpo={
            busca || codigo
              ? "Nenhum resultado para esta busca."
              : "Importe a lista que a instituição enviou."
          }
        />
      ) : (
        <>
          <div className="tabela-rolagem">
            <table
              className={`planilha planilha--criancas ${
                estreita ? "planilha--compacta" : ""
              }`}
            >
              {/* So faz sentido onde a lista de fato rola. Na versao estreita
                  as colunas cabem todas na tela, e prometer arraste ali seria
                  mandar a pessoa procurar o que nao existe. */}
              {!estreita && (
                <caption className="tabela-dica">
                  Arraste a lista para o lado para ver todas as colunas.
                </caption>
              )}
              {/* As larguras ficam aqui, e nao no conteudo: trocar de aba nao
                  move nenhuma coluna de lugar. */}
              <colgroup>
                {podeEditar && !estreita && <col style={{ width: 34 }} />}
                <col style={{ width: estreita ? 74 : 92 }} />
                <col />
                {!estreita && (
                  <>
                    <col style={{ width: 64 }} />
                    <col style={{ width: 58 }} />
                    <col style={{ width: 112 }} />
                    <col style={{ width: 190 }} />
                    <col style={{ width: 150 }} />
                    <col style={{ width: 120 }} />
                  </>
                )}
                <col style={{ width: estreita ? 62 : 84 }} />
                {!estreita && (
                  <>
                    <col style={{ width: 72 }} />
                    <col style={{ width: 72 }} />
                  </>
                )}
                {/* Condicional junto com o <th>: um <col> a mais que as celulas
                    nao some — vira uma coluna vazia no fim, e a planilha
                    parece nao alcancar a borda do container. */}
                {mostrarCheckin && !estreita && <col style={{ width: 82 }} />}
                {/* Os mesmos 66 de antes, que agora levam dois botoes de 24px
                    em vez de um de tres pontinhos. Sem o de apagar sobra a
                    largura de um, e os 26px voltam para a coluna do nome.
                    No celular e um olho so, mas de 40px: alvo de dedo, e nao
                    de ponteiro. */}
                <col style={{ width: estreita ? 48 : podeEditar ? 66 : 40 }} />
              </colgroup>
              <thead>
                <tr>
                  {podeEditar && !estreita && (
                    <th className="planilha__marcar">
                      <input
                        type="checkbox"
                        checked={marcadas.length === criancas.itens.length}
                        onChange={marcarTodas}
                        aria-label="Marcar todas"
                      />
                    </th>
                  )}
                  <th>Código</th>
                  <th>Nome</th>
                  {!estreita && (
                    <>
                      <th>Idade</th>
                      <th>Sexo</th>
                      <th>Dia</th>
                      <th>Instituição</th>
                      <th title="Comissário responsável por esta criança. A instituição é atendida pelo time todo; aqui fica quem responde por ela.">
                        Comissário
                      </th>
                      <th title="O grupo do comissário responsável na comunidade. Vem do cadastro dele nesta edição e não se edita aqui.">
                        Grupo
                      </th>
                    </>
                  )}
                  <th title="Padrinho de cesta e de festa">Padrinhos</th>
                  {!estreita && (
                    <>
                      <th title="Cartões digitalizados, de 2">Cartões</th>
                      <th>Kit</th>
                    </>
                  )}
                  {mostrarCheckin && !estreita && <th>Check-in</th>}
                  <th className="planilha__acoes" />
                </tr>
              </thead>
              <tbody>
                {criancas.itens.map((c) => (
                  <tr
                    key={c.id}
                    className={[
                      marcadas.includes(c.id) ? "planilha__linha--marcada" : "",
                      c.desistiu_em ? "planilha__linha--desistiu" : "",
                    ].filter(Boolean).join(" ")}
                    title={c.desistiu_em ? `${c.nome} desistiu de ir ao evento` : undefined}
                    /* No celular a linha inteira abre a ficha: o olho e um
                       alvo de 40px numa faixa de 48 por toda a largura da
                       tela, e mirar nele nao deveria ser exigencia de nada.
                       So no celular — no desktop o clique na celula e o que
                       abre a edicao dela, e os dois nao cabem no mesmo lugar.

                       O olho fica: ele e quem anuncia a acao para quem navega
                       por teclado ou leitor de tela, e quem diz de que crianca
                       e a ficha. A linha e atalho de dedo, e por isso nao ganha
                       `role` nem foco proprio — seria um segundo botao dizendo
                       a mesma coisa no caminho de quem usa Tab. */
                    onClick={estreita ? () => definirFichaAberta(c.id) : undefined}
                  >
                    {podeEditar && !estreita && (
                      <td className="planilha__marcar">
                        <input
                          type="checkbox"
                          checked={marcadas.includes(c.id)}
                          onChange={() => alternar(c.id)}
                          aria-label={`Marcar ${c.nome}`}
                        />
                      </td>
                    )}
                    {/* No celular as duas viram texto, mesmo para quem pode
                        editar: a celula que vira campo ao toque abriria o
                        teclado em quem so queria rolar a lista, e um codigo
                        trocado sem querer nao avisa que foi trocado. Edicao e
                        no computador. */}
                    <td>
                      {podeEditar && !estreita ? (
                        <CelulaEditavel
                          valor={c.codigo}
                          aoSalvar={(v) => salvarCampo(c, "codigo", v)}
                        />
                      ) : (
                        <span className="celula celula--fixa">{c.codigo}</span>
                      )}
                    </td>
                    <td>
                      {podeEditar && !estreita ? (
                        <CelulaEditavel
                          valor={c.nome}
                          aoSalvar={(v) => salvarCampo(c, "nome", v)}
                        />
                      ) : (
                        <span className="celula celula--fixa" title={c.nome}>
                          {c.nome}
                        </span>
                      )}
                    </td>
                    {!estreita && (
                      <>
                        <td>
                        {podeEditar ? (
                          <CelulaEditavel
                            valor={c.idade}
                            tipo="number"
                            aoSalvar={(v) => salvarCampo(c, "idade", Number(v))}
                          />
                        ) : (
                          <span className="celula">{c.idade}</span>
                        )}
                      </td>
                      <td>
                        {podeEditar ? (
                          <CelulaEditavel
                            valor={c.sexo}
                            opcoes={SEXOS}
                            aoSalvar={(v) => salvarCampo(c, "sexo", v)}
                          />
                        ) : (
                          <span className="celula">{c.sexo}</span>
                        )}
                      </td>
                      <td>
                        {/* Somente leitura: o dia e da instituicao, e se muda na
                            aba dela. Editar por crianca deixaria duas da mesma
                            escola em dias diferentes. */}
                        <span
                          className={`celula ${c.dia_evento ? "" : "celula--vazia"}`}
                          style={{ cursor: "default" }}
                          title="O dia vem da instituição"
                        >
                          {c.dia_evento ? (
                            <EtiquetaDia data={c.dia_evento} descricao={c.dia_evento_descricao} />
                          ) : (
                            "sem dia"
                          )}
                        </span>
                      </td>
                      <td>
                        <span className="celula" title={c.instituicao}>
                          {c.instituicao}
                        </span>
                      </td>
                      <td>
                        {/* Responsavel por ESTA crianca. Nao muda quem alcanca o
                            que: o time inteiro da instituicao continua vendo e
                            trabalhando a lista toda dela. */}
                        {podeEditar ? (
                          <CelulaEditavel
                            valor={c.comissario_id}
                            opcoes={opcoesComissario(c.instituicao_id)}
                            aoSalvar={(v) =>
                              salvarCampo(c, "comissario_id", v === "" ? null : Number(v))
                            }
                          />
                        ) : (
                          <span
                            className={`celula ${c.comissario ? "" : "celula--vazia"}`}
                            style={{ cursor: "default" }}
                            title={c.comissario ?? "Nenhum comissário responsável"}
                          >
                            {c.comissario ?? "sem responsável"}
                          </span>
                        )}
                      </td>
                      <td>
                        {/* So leitura: o grupo e do cadastro do comissario, na
                            tela de usuarios. Editar aqui mudaria o grupo dele
                            para TODAS as criancas de uma vez, o que ninguem
                            esperaria de um clique na linha de uma. */}
                        <span
                          className={`celula ${c.comissario_grupo ? "" : "celula--vazia"}`}
                          style={{ cursor: "default" }}
                          title={
                            c.comissario
                              ? (c.comissario_grupo ?? `${c.comissario} ainda não tem grupo nomeado`)
                              : "Nenhum comissário responsável"
                          }
                        >
                          {c.comissario_grupo ?? (c.comissario ? "sem grupo" : "—")}
                        </span>
                      </td>
                      </>
                    )}
                    <td>
                      {/* O cursor de "aqui nao se clica" so vale onde a celula
                          e mesmo o alvo. No celular o alvo e a linha, e ela
                          toda mostra a mao. */}
                      <span
                        className="celula"
                        style={estreita ? undefined : { cursor: "default" }}
                      >
                        <span
                          className={`marcador ${c.tem_padrinho_cesta ? "marcador--feito" : ""}`}
                          title={c.tem_padrinho_cesta ? "Tem padrinho de cesta" : "Sem padrinho de cesta"}
                        >
                          C
                        </span>
                        <span
                          className={`marcador ${c.tem_padrinho_festa ? "marcador--feito" : ""}`}
                          title={c.tem_padrinho_festa ? "Tem padrinho de festa" : "Sem padrinho de festa"}
                        >
                          F
                        </span>
                      </span>
                    </td>
                    {!estreita && (
                      <>
                        <td>
                        <span className="celula" style={{ cursor: "default" }}>
                          <span
                            className={`marcador ${
                              c.cartoes >= 2 ? "marcador--feito" : c.cartoes > 0 ? "marcador--parcial" : ""
                            }`}
                          >
                            {c.cartoes}/2
                          </span>
                        </span>
                      </td>
                      <td>
                        <span className="celula" style={{ cursor: "default" }}>
                          <span
                            className={`marcador ${
                              c.kit_status === "entregue"
                                ? "marcador--feito"
                                : c.kit_status === "montado"
                                  ? "marcador--parcial"
                                  : ""
                            }`}
                          >
                            {c.kit_status.slice(0, 4)}
                          </span>
                        </span>
                      </td>
                      </>
                    )}
                    {mostrarCheckin && !estreita && (
                      <td>
                        <span className="celula" style={{ cursor: "default" }}>
                          <span className={`marcador ${c.checkin_em ? "marcador--feito" : ""}`}>
                            {c.checkin_em ? "sim" : "não"}
                          </span>
                        </span>
                      </td>
                    )}
                    {/* Duas acoes por linha, e as duas a um clique: com so
                        isso, o menu de tres pontinhos cobrava um clique a mais
                        para chegar na ficha — a acao mais comum da planilha. O
                        X continua abrindo a janela de confirmacao.

                        No celular fica so o olho, e maior: o apagar e acao de
                        planilha, e a planilha inteira mora na tela grande —
                        alem de ser o vizinho mais perigoso que um dedo podia
                        ter ao lado da acao que se repete em toda linha. */}
                    <td className="planilha__acoes">
                      <span className="acoes-icone">
                        <BotaoIcone
                          titulo={`Ver ficha de ${c.nome}`}
                          tamanho="sm"
                          onClick={() => definirFichaAberta(c.id)}
                        >
                          <Olho t={estreita ? 20 : undefined} />
                        </BotaoIcone>
                        {podeEditar && !estreita && (
                          <BotaoIcone
                            perigo
                            titulo={`Apagar ${c.nome}`}
                            tamanho="sm"
                            onClick={() => pedirExclusao(c)}
                          >
                            <Xis />
                          </BotaoIcone>
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPaginas > 1 && (
            <div className="barra-acoes" style={{ marginTop: "var(--space-5)" }}>
              <Button size="sm" variant="ghost" onClick={() => definirPagina((p) => p - 1)} disabled={pagina <= 1}>
                Anterior
              </Button>
              <span className="campo__dica" style={{ marginTop: 0 }}>
                Página {pagina} de {totalPaginas}
              </span>
              <Button size="sm" variant="ghost" onClick={() => definirPagina((p) => p + 1)} disabled={pagina >= totalPaginas}>
                Próxima
              </Button>
            </div>
          )}

          {podeEditar && !estreita && marcadas.length > 0 && (
            <div className="lote">
              <span className="lote__texto">{marcadas.length} marcada(s)</span>
              <Selecao
                value=""
                disabled={atribuindo}
                onChange={(e) => atribuirMarcadas(e.target.value)}
                aria-label="Atribuir as marcadas a um responsável"
              >
                <option value="" disabled>
                  {atribuindo ? "Atribuindo..." : "Atribuir a..."}
                </option>
                {comissariosDoLote.length === 0 && (
                  <option value="" disabled>
                    (ninguém da equipe atende todas as escolas marcadas)
                  </option>
                )}
                {comissariosDoLote.map((c) => (
                  <option key={c.id} value={c.id}>{comoAparece(c)}</option>
                ))}
                <option value={SEM_RESPONSAVEL}>Sem responsável</option>
              </Selecao>
              <Button size="sm" variant="ghost" onClick={() => definirMarcadas([])}>
                Desmarcar
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
