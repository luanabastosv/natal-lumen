import { useCallback, useEffect, useRef, useState } from "react";
import BotaoIcone from "../core/BotaoIcone.jsx";
import Button from "../core/Button.jsx";
import { AreaTexto, Entrada, Selecao } from "../core/Campo.jsx";
import { Baixar, Visto } from "../core/icones.jsx";
import Carregando from "../feedback/Carregando.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import { useSessao } from "../../contexts/useSessao.js";
import {
  baixarComprovante,
  criarPagamento,
  listarPagamentos,
  subirComprovante,
} from "../../services/padrinhos.js";
import { dinheiro, formatarData } from "../../utils/dinheiro.js";

const FORMAS = ["Pix", "Dinheiro", "Transferência", "Cartão", "Boleto"];

/** Quantos de cada tipo, escrito como o comissário fala: "5 cestas + 2 festas". */
function resumoTipos(itens) {
  const conta = { cesta: 0, festa: 0 };
  for (const a of itens) conta[a.tipo] = (conta[a.tipo] ?? 0) + 1;

  const partes = [];
  if (conta.cesta) partes.push(`${conta.cesta} ${conta.cesta === 1 ? "cesta" : "cestas"}`);
  if (conta.festa) partes.push(`${conta.festa} ${conta.festa === 1 ? "festa" : "festas"}`);
  return partes.join(" + ");
}

/** A aba Pagamento da ficha: o que este padrinho já pagou, e o próximo.
 *
 * Duas partes, nesta ordem — registrar é o que se vem fazer aqui; conferir o
 * que já existe vem depois:
 *
 *   1. o formulário do novo pagamento, quando ainda há apadrinhamento em
 *      aberto;
 *   2. a lista dos pagamentos já registrados, cada um com o comprovante dele —
 *      para baixar e olhar, ou para subir o arquivo que ficou faltando.
 *
 * **O comprovante é obrigatório para registrar.** É a regra do dinheiro que
 * entra: sem arquivo, ninguém consegue conferir depois se aquele valor chegou
 * de verdade, e a linha virava uma promessa. Quem recebeu em dinheiro vivo
 * fotografa o recibo — e é justamente esse caso que mais precisa de prova.
 *
 * O servidor continua aceitando pagamento sem comprovante, de propósito: o
 * arquivo sobe numa SEGUNDA requisição (§6 dos padrões de UI), e se ela falhar
 * o dinheiro já está gravado — perder a quitação por causa do arquivo seria
 * pior. Quando isso acontece, a linha aparece aqui com "falta o comprovante" e
 * o arquivo entra depois.
 *
 * O valor NÃO é digitado: ele é a soma do que foi marcado. Cada apadrinhamento
 * já tem o próprio valor (cesta e festa custam diferente, e o preço vem da
 * edição da criança), então digitar de novo só criaria divergência entre o que
 * a base diz que foi quitado e o que o pagamento diz que custou. Pagamento de
 * valor diferente da soma — desconto, arredondamento — se registra pelo
 * Financeiro, que edita o valor solto.
 */
export default function RegistrarPagamento({ padrinho, aoFechar, aoRegistrar }) {
  const { usuario, vinculoAtivo } = useSessao();

  // Um padrinho recebe criancas de varios comissarios. Quitar o apadrinhamento
  // do colega e MEXER nele — era promessa e vira apadrinhamento confirmado, no
  // nome de quem o registrou —, e por isso o comissario so quita os proprios.
  // Quem coordena a captacao fecha a conta inteira.
  const soMinhas = Boolean(vinculoAtivo?.so_criancas_atribuidas);
  const meu = (a) => !soMinhas || a.comissario_id === usuario?.id;

  const abertos = padrinho.apadrinhamentos.filter((a) => !a.pago);
  const aPagar = abertos.filter(meu);
  const doColega = abertos.length - aPagar.length;

  const [marcados, definirMarcados] = useState([]);
  const [data, definirData] = useState(() => new Date().toISOString().slice(0, 10));
  const [forma, definirForma] = useState(FORMAS[0]);
  const [observacoes, definirObservacoes] = useState("");
  const [arquivo, definirArquivo] = useState(null);
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState("");

  // Os pagamentos que este padrinho ja tem. Vem do servidor, e nao do objeto
  // da ficha: a ficha carrega os apadrinhamentos, que dizem se estao pagos,
  // mas nao os pagamentos em si — e e o pagamento que carrega o comprovante.
  const [pagamentos, definirPagamentos] = useState(null);
  const [subindo, definirSubindo] = useState(null);
  const [baixando, definirBaixando] = useState(null);

  // Um seletor para a aba inteira: qual pagamento recebe o arquivo e uma
  // escolha de antes de abrir a janela do sistema operacional.
  const seletorArquivo = useRef(null);
  const [alvo, definirAlvo] = useState(null);

  const buscarPagamentos = useCallback(async () => {
    try {
      const r = await listarPagamentos({ padrinho_id: padrinho.id });
      definirPagamentos(r.itens);
    } catch (e) {
      definirErro(e.message);
      definirPagamentos([]);
    }
  }, [padrinho.id]);

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer.
    // eslint-disable-next-line react/set-state-in-effect
    buscarPagamentos();
  }, [buscarPagamentos]);

  const escolhidos = aPagar.filter((a) => marcados.includes(a.id));
  const total = escolhidos.reduce((soma, a) => soma + Number(a.valor), 0);

  // O que ainda impede de registrar, na ordem em que a pessoa resolve. Vira a
  // frase da barra e o motivo de o botao estar inativo — os dois saem daqui,
  // entao nao ha como um dizer uma coisa e o outro dizer outra.
  const falta =
    marcados.length === 0
      ? "Marque o que este dinheiro quita."
      : !arquivo
        ? "Escolha o comprovante para poder registrar."
        : "";

  function alternar(id) {
    definirMarcados((atual) =>
      atual.includes(id) ? atual.filter((x) => x !== id) : [...atual, id],
    );
  }

  function marcarTodos() {
    definirMarcados(marcados.length === aPagar.length ? [] : aPagar.map((a) => a.id));
  }

  async function registrar() {
    definirErro("");
    definirSalvando(true);
    try {
      const pagamento = await criarPagamento({
        padrinho_id: padrinho.id,
        valor: total.toFixed(2),
        data,
        forma,
        observacoes: observacoes.trim() || null,
        apadrinhamentos: marcados,
      });

      // O comprovante vem depois e em separado: se ele falhar, a quitacao ja
      // esta gravada, e o arquivo pode ser reenviado pela lista aqui embaixo.
      try {
        await subirComprovante(pagamento.id, arquivo);
      } catch (e) {
        definirErro(
          `Pagamento registrado, mas o comprovante não subiu: ${e.message} ` +
            "Envie o arquivo pela lista abaixo.",
        );
        await aoRegistrar();
        await buscarPagamentos();
        definirMarcados([]);
        definirArquivo(null);
        return;
      }

      await aoRegistrar();
      aoFechar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function baixar(pagamento) {
    definirErro("");
    definirBaixando(pagamento.id);
    try {
      await baixarComprovante(pagamento.id);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirBaixando(null);
    }
  }

  function pedirArquivo(pagamento) {
    definirAlvo(pagamento.id);
    // Zera antes de abrir: sem isso, escolher o MESMO arquivo de novo (depois
    // de um erro) nao dispara onChange.
    seletorArquivo.current.value = "";
    seletorArquivo.current.click();
  }

  async function aoEscolherArquivo(evento) {
    const escolhido = evento.target.files?.[0];
    if (!escolhido || !alvo) return;

    definirErro("");
    definirSubindo(alvo);
    try {
      await subirComprovante(alvo, escolhido);
      await buscarPagamentos();
      // A planilha atras mostra o comprovante na linha: ela precisa saber.
      await aoRegistrar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSubindo(null);
      definirAlvo(null);
    }
  }

  return (
    <div className="pagamento">
      <Mensagem tipo="erro">{erro}</Mensagem>

      {/* Fora das linhas e escondido: e o mesmo seletor para todas elas. */}
      <input
        ref={seletorArquivo}
        type="file"
        accept="image/jpeg,image/png,application/pdf"
        onChange={aoEscolherArquivo}
        hidden
      />

      {/* A aba existe mesmo sem nada a pagar: "tudo quitado" e uma resposta, e
          some-la faria a faixa de abas mudar de tamanho — o defeito que as abas
          vieram resolver. E, quitado ou nao, os comprovantes ficam aqui. */}
      {/* A aba existe mesmo sem nada a pagar: "tudo quitado" e uma resposta, e
          some-la faria a faixa de abas mudar de tamanho — o defeito que as abas
          vieram resolver. E, quitado ou nao, os comprovantes ficam aqui. */}
      {/* Dois "nada a pagar" diferentes, e dizer o errado aqui faria a pessoa
          procurar um defeito que nao existe. */}
      {aPagar.length === 0 ? (
        doColega > 0 ? (
          <Mensagem tipo="aviso">
            Este padrinho tem {doColega} apadrinhamento(s) a pagar, mas todos foram
            registrados por outra pessoa do time. Quem recebe o pagamento deles é quem
            os registrou, ou quem coordena a captação.
          </Mensagem>
        ) : (
          <Mensagem tipo="sucesso">
            Todos os apadrinhamentos deste padrinho já estão <strong>quitados</strong>.
          </Mensagem>
        )
      ) : (
        <>
          {/* PRIMEIRO o que o dinheiro quita: e a decisao, e e dela que sai o
              valor. Perguntar data e forma antes seria pedir o detalhe de um
              pagamento que ainda nao existe. */}
          <div className="pagamento__secao">
            <div className="pagamento__secao-topo">
              <div className="ficha__secao">O que este pagamento quita</div>
              <Button size="sm" variant="ghost" onClick={marcarTodos}>
                {marcados.length === aPagar.length ? "Desmarcar todas" : "Marcar todas"}
              </Button>
            </div>

            <div className="pagamento__lista">
              {aPagar.map((a) => (
                <label key={a.id} className="pagamento__linha">
                  <input
                    type="checkbox"
                    checked={marcados.includes(a.id)}
                    onChange={() => alternar(a.id)}
                  />
                  {/* Mesmo par de sempre: codigo na frente, nome completo em
                      seguida. Quem confere um comprovante contra a planilha
                      procura pelo codigo, nao pelo primeiro nome. */}
                  <span
                    className="pagamento__nome"
                    title={`${a.crianca_codigo} · ${a.crianca_nome}`}
                  >
                    <span className="ficha__linha-codigo">{a.crianca_codigo}</span>
                    {a.crianca_nome}, {a.crianca_idade}
                  </span>
                  <span className="etiqueta etiqueta--neutra">{a.tipo}</span>
                  <span className="pagamento__preco">{dinheiro(a.valor)}</span>
                </label>
              ))}
            </div>
          </div>

          {/* DEPOIS como esse dinheiro chegou. Campos com rotulo, um assunto
              por bloco: antes eram data e forma soltas numa barra, sem rotulo
              visivel, ao lado de um total e de dois botoes. */}
          <div className="pagamento__secao">
            <div className="ficha__secao">Como o dinheiro chegou</div>

            <div className="linha-campos">
              <Entrada
                rotulo="Data"
                tipo="date"
                value={data}
                onChange={(e) => definirData(e.target.value)}
              />
              <Selecao
                rotulo="Forma"
                value={forma}
                onChange={(e) => definirForma(e.target.value)}
              >
                {FORMAS.map((f) => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </Selecao>
            </div>

            <label className={`arquivo ${arquivo ? "arquivo--cheio" : ""}`}>
              <span className="arquivo__rotulo">
                {arquivo && <Visto t={14} />}
                Comprovante
                {!arquivo && <span className="arquivo__exigido">obrigatório</span>}
              </span>
              <input
                type="file"
                accept="image/jpeg,image/png,application/pdf"
                onChange={(e) => definirArquivo(e.target.files?.[0] ?? null)}
              />
              <span className="arquivo__estado">
                {arquivo
                  ? arquivo.name
                  : "Foto do Pix, print ou PDF do banco. Sem ele não há como conferir o valor depois."}
              </span>
            </label>

            <AreaTexto
              rotulo="Observação"
              linhas={2}
              value={observacoes}
              onChange={(e) => definirObservacoes(e.target.value)}
              dica="O que este dinheiro tem de diferente. Opcional, e aparece na linha dele no Financeiro."
            />
          </div>
        </>
      )}

      {/* O que ja foi pago, com o comprovante de cada um. */}
      <div className="pagamento__ja-pagos">
        <div className="ficha__secao">Pagamentos deste padrinho</div>

        {pagamentos === null ? (
          <Carregando>Buscando os pagamentos...</Carregando>
        ) : pagamentos.length === 0 ? (
          <span className="campo__dica">Nenhum pagamento registrado ainda.</span>
        ) : (
          <div className="ficha__lista">
            {pagamentos.map((p) => (
              <div key={p.id} className="ficha__linha">
                <div className="ficha__linha-corpo">
                  <span className="ficha__linha-etiquetas">
                    <span
                      className={`etiqueta ${p.conferido ? "etiqueta--ok" : "etiqueta--espera"}`}
                    >
                      {p.conferido ? "Conferido" : "A conferir"}
                    </span>
                    {!p.comprovante_arquivo && (
                      <span className="etiqueta etiqueta--espera">falta o comprovante</span>
                    )}
                  </span>
                  <span className="ficha__linha-nome">
                    {dinheiro(p.valor)} · {formatarData(p.data)}
                    {p.forma ? ` · ${p.forma}` : ""}
                  </span>
                  {p.observacoes && (
                    <span className="vinculo-linha__detalhe">{p.observacoes}</span>
                  )}
                </div>

                <span className="ficha__linha-acoes">
                  {p.comprovante_arquivo && (
                    <BotaoIcone
                      titulo={`Baixar o comprovante de ${dinheiro(p.valor)}`}
                      onClick={() => baixar(p)}
                      carregando={baixando === p.id}
                    >
                      <Baixar t={16} />
                    </BotaoIcone>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => pedirArquivo(p)}
                    carregando={subindo === p.id}
                  >
                    {p.comprovante_arquivo ? "Trocar" : "Subir"}
                  </Button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* A confirmacao fica no fim, na ordem em que se le — e grudada no pe da
          area que rola, para continuar a vista com vinte criancas marcadas.
          A frase ao lado diz o que falta: botao inativo sem explicacao faz a
          pessoa procurar defeito na tela. */}
      {aPagar.length > 0 && (
        <div className="pagamento__barra">
          <div className="pagamento__soma">
            <span className="pagamento__valor">{dinheiro(total)}</span>
            <span className="pagamento__tipos">
              {escolhidos.length === 0
                ? `nada marcado · ${aPagar.length} em aberto`
                : `${resumoTipos(escolhidos)} · ${escolhidos.length} de ${aPagar.length}`}
            </span>
          </div>

          {falta && <span className="pagamento__falta">{falta}</span>}

          <Button
            variant="secondary"
            size="sm"
            onClick={registrar}
            disabled={Boolean(falta)}
            carregando={salvando}
          >
            Registrar
          </Button>
          <Button size="sm" variant="ghost" onClick={aoFechar} disabled={salvando}>
            Cancelar
          </Button>
        </div>
      )}
    </div>
  );
}
