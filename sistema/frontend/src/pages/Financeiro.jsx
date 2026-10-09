import { useCallback, useEffect, useRef, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import BotaoIcone from "../components/core/BotaoIcone.jsx";
import Button from "../components/core/Button.jsx";
import MenuAcoes from "../components/core/MenuAcoes.jsx";
import { Baixar } from "../components/core/icones.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import Numero from "../components/feedback/Numero.jsx";
import NovoRecebimento from "../components/dados/NovoRecebimento.jsx";
import FichaSimples from "../components/dados/FichaSimples.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import useTelaEstreita from "../hooks/useTelaEstreita.js";
import {
  CATEGORIAS_SAIDA,
  ROTULO_CATEGORIA,
  apagarRecebimento,
  apagarSaida,
  baixarComprovanteDoRecebimento,
  criarSaida,
  listarRecebimentos,
  listarSaidas,
  subirComprovanteDoRecebimento,
} from "../services/financeiro.js";
import {
  apagarPagamento,
  baixarComprovante,
  subirComprovante,
} from "../services/padrinhos.js";
import { dinheiro, formatarData } from "../utils/dinheiro.js";

/** O nome curto do tipo, para a etiqueta da lista. O rotulo inteiro
 *  ("Apadrinhamento - cesta") fica na dica do mouse: repetido em toda linha, o
 *  "Apadrinhamento" e so ruido. */
const ETIQUETA_ORIGEM = {
  apadrinhamento_cesta: "cesta",
  apadrinhamento_festa: "festa",
  apadrinhamento: "sem destino",
  doacao: "doação",
  outros: "outros",
};

/** As etiquetas do tipo da linha, cada uma na cor da sua barra no grafico.
 *
 *  Uma por categoria, e nao uma "cesta + festa": o pagamento que quita as
 *  duas tem as duas etiquetas, e e assim que ele conta no "De onde veio" —
 *  partido, cesta de um lado e festa do outro. */
function EtiquetaOrigem({ linha }) {
  const doPagamento = linha.fonte === "pagamento";
  const categorias = linha.categorias?.length ? linha.categorias : [linha.categoria];

  return categorias.map((categoria) => {
    const rotulo = ROTULO_CATEGORIA[categoria] ?? categoria;
    return (
      <span
        key={categoria}
        className={`etiqueta etiqueta--origem origem--${categoria}`}
        title={doPagamento ? `${rotulo}: ${linha.descricao}` : rotulo}
      >
        {ETIQUETA_ORIGEM[categoria] ?? categoria}
      </span>
    );
  });
}

const hoje = () => new Date().toISOString().slice(0, 10);

const NOVA_SAIDA = {
  descricao: "", categoria: "",
  valor_total: "", fornecedor: "", data: hoje(),
};

/* A cor de cada categoria de saida, presa a CATEGORIA e nunca ao valor: a
   cor de "Alimentação" e a mesma em qualquer edicao. Sao as oito da paleta
   categorica validada (CVD deltaE >= 8 entre vizinhas NESTA ordem), e as
   fatias saem nesta ordem para as vizinhas serem sempre as validadas.

   Onze categorias e oito cores: uma nona cor gerada seria indistinguivel. As
   tres que sobram (as de menos gasto esperado) e as de texto livre de antes
   da lista fechada ficam num cinza neutro — mas cada uma com a PROPRIA fatia
   e o proprio nome na legenda, e nunca juntas num "demais". Amarelo, aqua e
   rosa ficam abaixo de 3:1 sobre o branco: por isso nome e valor vao sempre
   escritos na legenda. */
const COR_SAIDA = [
  ["Estrutura - cestas", "#2a78d6"],
  ["Estrutura - festa", "#eb6834"],
  ["Alimentação", "#1baf7a"],
  ["Decoração", "#eda100"],
  ["Monitoria", "#e87ba4"],
  ["Comissários", "#008300"],
  ["Ser Feliz", "#4a3aa7"],
  ["Intercessão", "#e34948"],
];
const COR_NEUTRA = "#8a8984";

/** Para onde foi o que saiu: o mesmo card do "De onde veio", com uma fatia
 *  e um nome na legenda para cada categoria. */
function DestinoDoGasto({ porCategoria, total }) {
  if (total <= 0) return null;
  const ordem = (categoria) => {
    const i = COR_SAIDA.findIndex(([c]) => c === categoria);
    if (i >= 0) return i;
    const j = CATEGORIAS_SAIDA.indexOf(categoria);
    return COR_SAIDA.length + (j >= 0 ? j : CATEGORIAS_SAIDA.length);
  };
  const fatias = Object.entries(porCategoria)
    .map(([categoria, bruto]) => ({ categoria, valor: Number(bruto) }))
    .filter((f) => f.valor > 0)
    .map((f) => ({
      ...f,
      cor: COR_SAIDA.find(([c]) => c === f.categoria)?.[1] ?? COR_NEUTRA,
      posicao: ordem(f.categoria),
    }))
    .sort((a, b) => a.posicao - b.posicao);
  if (fatias.length === 0) return null;

  const dica = (f) =>
    `${f.categoria}: ${dinheiro(f.valor)} (${Math.round((f.valor / total) * 100)}% das saídas)`;

  return (
    <div className="numero numero--largo">
      <span className="numero__rotulo">Para onde foi</span>
      <div className="origem__barra" role="img" aria-label={fatias.map(dica).join("; ")}>
        {fatias.map((f) => (
          <span
            key={f.categoria}
            className="origem__fatia"
            style={{ flexGrow: f.valor, "--cor-origem": f.cor }}
            title={dica(f)}
          />
        ))}
      </div>
      <ul className="origem__legenda">
        {fatias.map((f) => (
          <li key={f.categoria} style={{ "--cor-origem": f.cor }} title={dica(f)}>
            {f.categoria} <strong>{dinheiro(f.valor)}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

const SAIDAS = "saidas";
const RECEBIMENTOS = "recebimentos";

const SEM_SAIDAS = { itens: [], total: 0, total_gasto: "0.00", por_categoria: {} };
const SEM_RECEBIMENTOS = {
  itens: [], total: 0, total_recebido: "0.00", por_categoria: {},
  apadrinhamento: "0.00", pagamentos: 0, a_conferir: "0.00", sem_comprovante: 0,
};

const SEM_FILTRO = { categoria: "", comprovante: "" };

/** De onde veio o que entrou: uma barra so, partida por categoria.
 *
 * Mora na fileira dos numeros, e nao num painel proprio: e o detalhe do
 * "Recebido", e se le junto com ele. Uma barra partida, e nao uma por
 * categoria, para o card ter a altura dos outros — cinco barras empilhadas
 * faziam a fileira inteira crescer e empurravam a lista para baixo. Cada
 * categoria tem a sua cor, a mesma da etiqueta na lista; a legenda embaixo
 * escreve nome e valor, para a cor nunca ser a unica pista. Vem de todas as
 * linhas, antes de qualquer filtro: e um retrato da edicao, e nao da lista que
 * esta na tela.
 */
function OrigemDoRecebido({ porCategoria, total }) {
  const linhas = Object.entries(porCategoria)
    .map(([categoria, valor]) => [categoria, Number(valor)])
    .filter(([, valor]) => valor > 0)
    .sort((a, b) => b[1] - a[1]);

  if (linhas.length === 0 || total <= 0) return null;

  const dica = (categoria, valor) =>
    `${ROTULO_CATEGORIA[categoria] ?? categoria}: ${dinheiro(valor)} ` +
    `(${Math.round((valor / total) * 100)}% do recebido)`;

  return (
    <div className="numero numero--largo">
      <span className="numero__rotulo">De onde veio</span>
      <div className="origem__barra" role="img" aria-label={linhas.map(([c, v]) => dica(c, v)).join("; ")}>
        {linhas.map(([categoria, valor]) => (
          <span
            key={categoria}
            className={`origem__fatia origem--${categoria}`}
            style={{ flexGrow: valor }}
            title={dica(categoria, valor)}
          />
        ))}
      </div>
      <ul className="origem__legenda">
        {linhas.map(([categoria, valor]) => (
          <li key={categoria} className={`origem--${categoria}`} title={dica(categoria, valor)}>
            {ETIQUETA_ORIGEM[categoria] ?? categoria} <strong>{dinheiro(valor)}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** O caixa da edição: o que saiu e o que entrou.
 *
 * Duas abas porque são dois lançamentos diferentes, e duas permissões também:
 * uma lança saídas, a outra lança e confere o que entra. Quem tem
 * só uma delas vê só a sua aba, e a faixa de abas nem aparece. O saldo só
 * existe para quem alcança as duas metades: com meia conta na mão, um saldo
 * seria um número errado com cara de certo.
 *
 * **Os pagamentos dos padrinhos são linhas da lista de recebimentos**, e não
 * uma tela à parte: quem fecha o caixa quer ver todo o dinheiro que entrou de
 * uma vez. A linha é o próprio pagamento, lido de lado — a categoria dela vem
 * do que ele quita, e as ações dela (conferir, comprovante, remover) batem em
 * `/pagamentos`. `fonte` é o que diz em qual endereço cada linha responde.
 */
export default function Financeiro() {
  // A edicao vem da lateral: e a mesma para o sistema inteiro.
  const { edicaoAtiva, pode } = useSessao();

  const podeSaidas = pode("gerenciar_compras");
  const podeRecebimentos = pode("registrar_pagamentos");

  const [aba, definirAba] = useState(podeSaidas ? SAIDAS : RECEBIMENTOS);
  const [saidas, definirSaidas] = useState(SEM_SAIDAS);
  const [recebimentos, definirRecebimentos] = useState(SEM_RECEBIMENTOS);
  const [filtros, definirFiltros] = useState(SEM_FILTRO);
  const [categoriaSaida, definirCategoriaSaida] = useState("");

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const notificar = useNotificar();

  // As duas listas desta tela sao as mais largas do sistema — a de
  // recebimentos tem dez colunas. No celular fica de pe o que a linha e e
  // quanto ela vale, e o resto vai para uma janela, a um toque.
  const estreita = useTelaEstreita();
  const [detalhe, definirDetalhe] = useState(null);

  const [modal, definirModal] = useState(null);
  // O pagamento de padrinho esperando confirmacao para sair. Ele desfaz os
  // apadrinhamentos junto, entao nao sai num clique so.
  const [aRemover, definirARemover] = useState(null);
  const [removendo, definirRemovendo] = useState(false);
  const [saida, definirSaida] = useState(NOVA_SAIDA);
  const [salvando, definirSalvando] = useState(false);

  // Um seletor de arquivo para a tela inteira, e nao um por linha: qual linha
  // recebe o arquivo e uma escolha de antes de abrir a janela do sistema.
  const seletorArquivo = useRef(null);
  const [alvo, definirAlvo] = useState(null);
  const [subindo, definirSubindo] = useState("");

  const chave = (linha) => `${linha.fonte}-${linha.id}`;

  const buscar = useCallback(async () => {
    try {
      // Cada metade so e pedida por quem a alcanca: pedir a outra voltaria 403
      // e a tela inteira viraria um erro por causa de uma aba que nem existe
      // para esta pessoa.
      const [s, r] = await Promise.all([
        podeSaidas ? listarSaidas({ edicao_id: edicaoAtiva }) : SEM_SAIDAS,
        podeRecebimentos
          ? listarRecebimentos({ edicao_id: edicaoAtiva, ...filtros })
          : SEM_RECEBIMENTOS,
      ]);
      definirSaidas(s);
      definirRecebimentos(r);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoAtiva, podeSaidas, podeRecebimentos, filtros]);

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer: os
    // lancamentos so chegam depois do await, e nao daria para derivar no render.
    // eslint-disable-next-line react/set-state-in-effect
    if (edicaoAtiva) buscar();
  }, [edicaoAtiva, buscar]);

  function trocarAba(nova) {
    definirAba(nova);
    definirModal(null);
    definirErro("");
  }

  const saldo = Number(recebimentos.total_recebido) - Number(saidas.total_gasto);
  // As categorias do filtro de saidas: as da lista fechada, e as de texto
  // livre que vieram de antes dela (para essas saidas tambem poderem ser
  // achadas).
  const categoriasDasSaidas = [
    ...CATEGORIAS_SAIDA,
    ...Object.keys(saidas.por_categoria).filter(
      (c) => !CATEGORIAS_SAIDA.includes(c) && c !== "sem categoria",
    ),
  ];
  const saidasVisiveis = categoriaSaida
    ? saidas.itens.filter((c) => c.categoria === categoriaSaida)
    : saidas.itens;
  const filtrando = Object.values(filtros).some(Boolean);

  /** Onde cada acao da linha bate. A linha de apadrinhamento e um pagamento;
   *  a de doacao, um recebimento. Mesma acao, endereco diferente. */
  function rotas(linha) {
    const dePagamento = linha.fonte === "pagamento";
    return {
      baixar: dePagamento ? baixarComprovante : baixarComprovanteDoRecebimento,
      subir: dePagamento ? subirComprovante : subirComprovanteDoRecebimento,
      apagar: dePagamento ? apagarPagamento : apagarRecebimento,
    };
  }

  async function salvarSaida(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      await criarSaida({
        edicao_id: Number(edicaoAtiva),
        descricao: saida.descricao.trim(),
        categoria: saida.categoria || null,
        // Sem campo de quantidade: a saida e o valor gasto, e o "quantas
        // unidades" ia num campo que quase sempre era 1.
        quantidade: 1,
        valor_total: saida.valor_total,
        fornecedor: saida.fornecedor.trim() || null,
        data: saida.data,
      });
      notificar("Saída registrada.");
      definirSaida(NOVA_SAIDA);
      definirModal(null);
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function removerSaida(item) {
    definirErro("");
    try {
      await apagarSaida(item.id);
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function removerLinha(linha) {
    definirErro("");
    definirRemovendo(true);
    try {
      await rotas(linha).apagar(linha.id);
      notificar(
        linha.fonte === "pagamento"
          ? `Pagamento de ${linha.quem ?? "padrinho"} desfeito. As crianças dele voltaram a ficar disponíveis.`
          : "Recebimento removido.",
      );
      definirARemover(null);
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirRemovendo(false);
    }
  }

  async function baixarArquivo(linha) {
    definirErro("");
    try {
      await rotas(linha).baixar(linha.id);
    } catch (e) {
      definirErro(e.message);
    }
  }

  function pedirArquivo(linha) {
    definirAlvo(linha);
    // Zera antes de abrir: sem isso, escolher o MESMO arquivo de novo (depois
    // de um erro, por exemplo) nao dispara onChange.
    seletorArquivo.current.value = "";
    seletorArquivo.current.click();
  }

  async function aoEscolherArquivo(evento) {
    const arquivo = evento.target.files?.[0];
    if (!arquivo || !alvo) return;

    definirErro("");
    definirSubindo(chave(alvo));
    try {
      await rotas(alvo).subir(alvo.id, arquivo);
      notificar("Comprovante guardado.");
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSubindo("");
      definirAlvo(null);
    }
  }

  /* As duas listas viram a mesma janela: um titulo e os pares que a linha
     estreita deixou de mostrar. Montadas aqui, e nao dentro do `map`, para o
     que a janela diz nunca sair do lugar em que a lista foi lida. */
  function detalheDaSaida(c) {
    return {
      rotulo: "Saída:",
      titulo: c.descricao,
      campos: [
        { rotulo: "Categoria", valor: c.categoria },
        { rotulo: "Valor", valor: dinheiro(c.valor_total) },
        { rotulo: "Fornecedor", valor: c.fornecedor },
        { rotulo: "Data", valor: formatarData(c.data) },
        { rotulo: "Por", valor: c.responsavel },
      ],
    };
  }

  function detalheDoRecebimento(l) {
    return {
      rotulo: "Entrada:",
      titulo: l.descricao,
      campos: [
        { rotulo: "De quem", valor: l.quem },
        { rotulo: "Categoria", valor: ROTULO_CATEGORIA[l.categoria] ?? l.categoria },
        { rotulo: "Valor", valor: dinheiro(l.valor) },
        { rotulo: "Forma", valor: l.forma },
        { rotulo: "Data", valor: formatarData(l.data) },
        {
          // O comprovante vem inteiro para a janela, com o botao de baixar: no
          // celular e aqui que ele existe, e conferir um comprovante e
          // justamente o que se faz longe da mesa.
          rotulo: "Comprovante",
          valor: l.tem_comprovante ? (
            <span className="acoes-icone">
              <BotaoIcone
                tamanho="sm"
                titulo={`Baixar o comprovante de ${l.quem ?? l.descricao}`}
                onClick={() => baixarArquivo(l)}
                carregando={subindo === chave(l)}
              >
                <Baixar />
              </BotaoIcone>
              {l.comprovante_drive_link && (
                <a href={l.comprovante_drive_link} target="_blank" rel="noreferrer">
                  Drive
                </a>
              )}
            </span>
          ) : (
            <span className="etiqueta etiqueta--espera">Falta</span>
          ),
        },
        { rotulo: "Por", valor: l.responsavel },
        { rotulo: "Observações", valor: l.observacoes, largo: true },
      ],
    };
  }

  return (
    <div>
      {/* Os tres numeros da edicao na altura do titulo, a direita: sao a
          resposta que a coordenacao vem buscar aqui, e nao custam uma linha
          de altura. Nao mudam quando se troca de aba. */}
      <div className="pagina__cabecalho financeiro__cabecalho">
        <div className="pagina__texto">
          <div className="pagina__eyebrow">Edição</div>
          <h1 className="pagina__titulo">Financeiro</h1>
          <Rabisco className="pagina__onda" />
        </div>
        {!carregando && (
          <div className="financeiro__totais">
            {podeRecebimentos && (
              <Numero rotulo="Recebido" valor={dinheiro(recebimentos.total_recebido)} moeda />
            )}
            {podeSaidas && <Numero rotulo="Saídas" valor={dinheiro(saidas.total_gasto)} moeda />}
            {podeSaidas && podeRecebimentos && (
              <Numero rotulo="Saldo" valor={dinheiro(saldo)} moeda negativo={saldo < 0} />
            )}
          </div>
        )}
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {/* Fora da tabela e escondido: e o mesmo seletor para todas as linhas. */}
      <input
        ref={seletorArquivo}
        type="file"
        accept="image/jpeg,image/png,application/pdf"
        onChange={aoEscolherArquivo}
        hidden
      />

      {aRemover && (
        <Modal
          rotulo="Pagamento de padrinho"
          titulo={`Desfazer o pagamento de ${aRemover.quem ?? "padrinho"}?`}
          aoFechar={() => !removendo && definirARemover(null)}
          rodape={
            <div className="barra-acoes barra-acoes--fim" style={{ marginTop: 0 }}>
              <Button
                variant="perigo"
                onClick={() => removerLinha(aRemover)}
                carregando={removendo}
              >
                Desfazer pagamento
              </Button>
              <Button variant="ghost" onClick={() => definirARemover(null)} disabled={removendo}>
                Cancelar
              </Button>
            </div>
          }
        >
          <p className="exclusao__texto" style={{ marginTop: 0 }}>
            {dinheiro(aRemover.valor)} de {formatarData(aRemover.data)} sai do caixa, e{" "}
            <strong>os apadrinhamentos que ele pagava são desfeitos junto</strong>: as
            crianças somem da ficha do padrinho e voltam a ficar disponíveis para apadrinhar.
          </p>
        </Modal>
      )}

      {modal === SAIDAS && (
        <Modal titulo="Nova saída" aoFechar={() => !salvando && definirModal(null)}>
          <form onSubmit={salvarSaida}>
            <Entrada rotulo="Descrição" value={saida.descricao}
              onChange={(e) => definirSaida({ ...saida, descricao: e.target.value })} required />
            <div className="linha-campos">
              <Selecao rotulo="Categoria" value={saida.categoria}
                onChange={(e) => definirSaida({ ...saida, categoria: e.target.value })} required>
                <option value="" disabled>Selecione</option>
                {CATEGORIAS_SAIDA.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </Selecao>
              <Entrada rotulo="Valor" tipo="number" step="0.01" value={saida.valor_total}
                onChange={(e) => definirSaida({ ...saida, valor_total: e.target.value })} required />
            </div>
            <div className="linha-campos">
              <Entrada rotulo="Fornecedor" value={saida.fornecedor}
                onChange={(e) => definirSaida({ ...saida, fornecedor: e.target.value })} />
              <Entrada rotulo="Data" tipo="date" value={saida.data}
                onChange={(e) => definirSaida({ ...saida, data: e.target.value })} required />
            </div>
            <div className="barra-acoes barra-acoes--fim">
              <Button variant="secondary" type="submit" carregando={salvando}>Salvar</Button>
              <Button variant="ghost" onClick={() => definirModal(null)} disabled={salvando}>
                Cancelar
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {modal === RECEBIMENTOS && (
        <Modal titulo="Novo recebimento" aoFechar={() => definirModal(null)}>
          <NovoRecebimento
            edicaoId={edicaoAtiva}
            aoFechar={() => definirModal(null)}
            aoRegistrar={buscar}
          />
        </Modal>
      )}

      {carregando ? (
        <Carregando tela>Somando o caixa da edição...</Carregando>
      ) : (
        <>
          {/* De onde veio / para onde foi, na largura toda embaixo do
              cabecalho: a legenda cresce com as categorias, e espremida ao
              lado dos numeros ela quebrava em varias linhas. */}
          <div className="numeros numeros--compactos financeiro__grafico">
            {/* So na aba de recebimentos: e o detalhe dela, e com as saidas
                abertas seria um grafico falando de outra lista. */}
            {aba === RECEBIMENTOS && (
              <OrigemDoRecebido
                porCategoria={recebimentos.por_categoria}
                total={Number(recebimentos.total_recebido)}
              />
            )}
            {aba === SAIDAS && (
              <DestinoDoGasto
                porCategoria={saidas.por_categoria}
                total={Number(saidas.total_gasto)}
              />
            )}
          </div>

          {/* Abas a esquerda, filtros a direita, numa linha so: a lista e o
              que se veio ver, e duas faixas empilhadas a empurravam meia tela
              para baixo. Os filtros sao da lista de recebimentos, e so
              aparecem com ela aberta. Sem espaco, eles descem para a linha de
              baixo, ainda alinhados a direita. */}
          <div className="faixa-abas-filtros">
            {/* Com uma aba so, a faixa nao aparece: quem tem uma permissao das
                duas nao precisa saber que existe uma metade que ele nao alcanca. */}
            {podeSaidas && podeRecebimentos && (
              <div className="abas faixa-abas-filtros__abas" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={aba === SAIDAS}
                  className={`aba ${aba === SAIDAS ? "aba--ativa" : ""}`}
                  onClick={() => trocarAba(SAIDAS)}
                >
                  <span>Saídas</span>
                  <span className="aba__contagem">{dinheiro(saidas.total_gasto)}</span>
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={aba === RECEBIMENTOS}
                  className={`aba ${aba === RECEBIMENTOS ? "aba--ativa" : ""}`}
                  onClick={() => trocarAba(RECEBIMENTOS)}
                >
                  <span>Recebimentos</span>
                  <span className="aba__contagem">{dinheiro(recebimentos.total_recebido)}</span>
                </button>
              </div>
            )}

            <div className="faixa-abas-filtros__filtros">
              {/* Nas saidas o filtro e so de categoria, e corta a lista na
                  tela: os totais e o grafico continuam da edicao inteira. */}
              {aba === SAIDAS && (
                <Selecao
                  aria-label="Filtrar saídas por categoria"
                  value={categoriaSaida}
                  onChange={(e) => definirCategoriaSaida(e.target.value)}
                >
                  <option value="">Todas as categorias</option>
                  {categoriasDasSaidas.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </Selecao>
              )}
              {aba === RECEBIMENTOS && (
                <>
                  <Selecao
                    aria-label="Filtrar por categoria"
                    value={filtros.categoria}
                    onChange={(e) => definirFiltros({ ...filtros, categoria: e.target.value })}
                  >
                    <option value="">Todas as categorias</option>
                    {/* As derivadas tambem filtram: sao elas que aparecem na
                        lista, e "Apadrinhamento" sozinho e o pagamento que
                        quita cesta e festa juntas. */}
                    {Object.entries(ROTULO_CATEGORIA).map(([valor, rotulo]) => (
                      <option key={valor} value={valor}>{rotulo}</option>
                    ))}
                  </Selecao>
                  <Selecao
                    aria-label="Filtrar por comprovante"
                    value={filtros.comprovante}
                    onChange={(e) => definirFiltros({ ...filtros, comprovante: e.target.value })}
                  >
                    <option value="">Com e sem comprovante</option>
                    <option value="false">Falta o comprovante</option>
                    <option value="true">Comprovante guardado</option>
                  </Selecao>
                  {filtrando && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => definirFiltros(SEM_FILTRO)}
                    >
                      Limpar filtros
                    </Button>
                  )}
                </>
              )}
              {/* O botao fica na faixa, ao lado dos filtros, e nao no topo da
                  pagina: e a acao da lista aberta, e muda com a aba. Um botao
                  cheio por tela — os dois nunca aparecem juntos. */}
              <Button
                size="sm"
                onClick={() => definirModal(aba)}
                disabled={!edicaoAtiva}
              >
                {aba === SAIDAS ? "Nova saída" : "Novo recebimento"}
              </Button>
            </div>
          </div>

          <div role="tabpanel" aria-label={aba === SAIDAS ? "Saídas" : "Recebimentos"}>
            {aba === SAIDAS ? (
              <>
                {saidasVisiveis.length === 0 ? (
                  <EmptyState
                    titulo={categoriaSaida ? "Nenhuma saída nesta categoria" : "Nenhuma saída registrada"}
                    corpo={
                      categoriaSaida
                        ? "Escolha outra categoria, ou Todas as categorias."
                        : "Registre aqui o que a edição gasta: cestas, presentes, estrutura, transporte."
                    }
                  />
                ) : (
                  <div className="tabela-rolagem">
                    <table className={`tabela ${estreita ? "tabela--compacta" : ""}`}>
                      <thead>
                        <tr>
                          <th>Descrição</th>
                          {!estreita && (
                            <>
                              <th>Categoria</th>
                            </>
                          )}
                          <th>Valor</th>
                          {!estreita && (
                            <>
                              <th>Fornecedor</th><th>Data</th><th>Por</th>
                            </>
                          )}
                          <th className="tabela__acoes" />
                        </tr>
                      </thead>
                      <tbody>
                        {saidasVisiveis.map((c) => (
                          <tr
                            key={c.id}
                            onClick={estreita ? () => definirDetalhe(detalheDaSaida(c)) : undefined}
                          >
                            <td>{c.descricao}</td>
                            {!estreita && (
                              <>
                                <td>{c.categoria ?? "—"}</td>
                              </>
                            )}
                            <td><span className="dinheiro">{dinheiro(c.valor_total)}</span></td>
                            {!estreita && (
                              <>
                                <td>{c.fornecedor ?? "—"}</td>
                                <td>{formatarData(c.data)}</td>
                                <td>{c.responsavel ?? "—"}</td>
                              </>
                            )}
                            <td className="tabela__acoes" onClick={(e) => e.stopPropagation()}>
                              <MenuAcoes
                                titulo={`Ações de ${c.descricao}`}
                                itens={[
                                  estreita && {
                                    rotulo: "Ver detalhes",
                                    aoEscolher: () => definirDetalhe(detalheDaSaida(c)),
                                  },
                                  { rotulo: "Remover", perigo: true, aoEscolher: () => removerSaida(c) },
                                ]}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : (
              <>

                {recebimentos.itens.length === 0 ? (
                  <EmptyState
                    titulo={filtrando ? "Nada com esses filtros" : "Nada recebido ainda"}
                    corpo={
                      filtrando
                        ? "Limpe os filtros para ver a lista inteira."
                        : "O pagamento de um padrinho aparece aqui sozinho, assim que for registrado. Doação e patrocínio entram pelo botão acima."
                    }
                  />
                ) : (
                  <div className="tabela-rolagem">
                    {/* Sem `tabela--larga` no celular: e a largura minima dela
                        que fazia a lista rolar de lado. */}
                    <table className={`tabela ${estreita ? "tabela--compacta" : "tabela--larga"}`}>
                      {!estreita && (
                        <caption className="tabela-dica">
                          Arraste a lista para o lado para ver todas as colunas.
                        </caption>
                      )}
                      <thead>
                        <tr>
                          <th>Categoria</th>
                          {!estreita && <th>De quem</th>}
                          <th>Valor</th>
                          {!estreita && (
                            <>
                              <th>Forma</th>
                              <th>Data</th>
                              <th>Comprovante</th>
                              <th>Por</th>
                            </>
                          )}
                          <th className="tabela__acoes" />
                        </tr>
                      </thead>
                      <tbody>
                        {recebimentos.itens.map((l) => (
                          <tr
                            key={chave(l)}
                            onClick={
                              estreita ? () => definirDetalhe(detalheDoRecebimento(l)) : undefined
                            }
                          >
                            <td title={l.observacoes ?? undefined}>
                              {/* O tipo vem na frente, na cor da barra dele no
                                  grafico — e por isso a coluna "Categoria"
                                  saiu: dizia a mesma coisa, sem a cor. */}
                              <EtiquetaOrigem linha={l} />
                              {/* So "outros" escreve o que foi: no pagamento a
                                  descricao e a contagem ("2 cestas + 1
                                  festa"), que fica na dica da etiqueta; na
                                  doacao, a etiqueta ja diz tudo. */}
                              {l.categoria === "outros" && l.descricao}
                            </td>
                            {!estreita && <td>{l.quem ?? "—"}</td>}
                            <td><span className="dinheiro">{dinheiro(l.valor)}</span></td>
                            {!estreita && (
                              <>
                                <td>{l.forma ?? "—"}</td>
                                <td>{formatarData(l.data)}</td>
                                <td>
                                  {l.tem_comprovante ? (
                                    <span className="acoes-icone">
                                      <BotaoIcone
                                        tamanho="sm"
                                        titulo={`Baixar o comprovante de ${l.quem ?? l.descricao}`}
                                        onClick={() => baixarArquivo(l)}
                                        carregando={subindo === chave(l)}
                                      >
                                        <Baixar />
                                      </BotaoIcone>
                                      {/* O Drive e copia, nao substituto: aparece
                                          so quando existe. */}
                                      {l.comprovante_drive_link && (
                                        <a
                                          href={l.comprovante_drive_link}
                                          target="_blank"
                                          rel="noreferrer"
                                        >
                                          Drive
                                        </a>
                                      )}
                                    </span>
                                  ) : (
                                    <span className="etiqueta etiqueta--espera">
                                      {subindo === chave(l) ? "Subindo..." : "Falta"}
                                    </span>
                                  )}
                                </td>
                                {/* Quem lancou. A linha de apadrinhamento traz
                                    quem registrou o pagamento — pode ter sido
                                    pela ficha do padrinho, e nao por esta tela. */}
                                <td>{l.responsavel ?? "—"}</td>
                              </>
                            )}
                            <td className="tabela__acoes" onClick={(e) => e.stopPropagation()}>
                              <MenuAcoes
                                titulo={`Ações de ${l.descricao}`}
                                itens={[
                                  estreita && {
                                    rotulo: "Ver detalhes",
                                    aoEscolher: () => definirDetalhe(detalheDoRecebimento(l)),
                                  },
                                  {
                                    rotulo: l.tem_comprovante
                                      ? "Trocar comprovante"
                                      : "Subir comprovante",
                                    disabled: subindo === chave(l),
                                    aoEscolher: () => pedirArquivo(l),
                                  },
                                  {
                                    rotulo: "Remover",
                                    perigo: true,
                                    // Pagamento de padrinho pergunta antes:
                                    // ele leva os apadrinhamentos junto.
                                    aoEscolher: () =>
                                      l.fonte === "pagamento"
                                        ? definirARemover(l)
                                        : removerLinha(l),
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
                {/* Embaixo da lista, e nao na faixa dos filtros: e rodape, e
                    la em cima so alargava a faixa ate ela quebrar a linha. */}
                {recebimentos.itens.length > 0 && (
                  <p className="campo__dica">
                    {recebimentos.total} linha(s)
                    {recebimentos.itens.length < recebimentos.total &&
                      ` · mostrando as ${recebimentos.itens.length} mais recentes`}
                  </p>
                )}
              </>
            )}
          </div>
        </>
      )}

      {detalhe && (
        <FichaSimples
          rotulo={detalhe.rotulo}
          titulo={detalhe.titulo}
          campos={detalhe.campos}
          aoFechar={() => definirDetalhe(null)}
        />
      )}
    </div>
  );
}
