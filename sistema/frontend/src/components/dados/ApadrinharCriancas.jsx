import { useState } from "react";
import { createPortal } from "react-dom";
import Button from "../core/Button.jsx";
import { AreaTexto, Entrada, Selecao } from "../core/Campo.jsx";
import BotaoIcone from "../core/BotaoIcone.jsx";
import { Baixar, Enviar, Visto, Xis } from "../core/icones.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import EtiquetaDesistente from "../core/EtiquetaDesistente.jsx";
import { useNotificar } from "../../contexts/useNotificar.js";
import { useSessao } from "../../contexts/useSessao.js";
import { listarCriancas } from "../../services/criancas.js";
import {
  apadrinharComPagamento,
  baixarAgradecimento,
  subirComprovante,
} from "../../services/padrinhos.js";
import { dinheiro, formatarData } from "../../utils/dinheiro.js";
import { nomeCurto, primeiroNome } from "../../utils/nomes.js";
import { linkWhatsapp } from "../../utils/whatsapp.js";

// Busca por codigo e o "escape" que alcanca qualquer instituicao das edicoes
// do usuario, e cada uma fica registrada em log. Uma busca por codigo, uma
// linha de log — por isso o teto: colar uma lista de duzentos codigos nao
// pode virar duzentas consultas de uma tacada.
const TETO = 20;

const TIPOS = ["cesta", "festa"];
const PASSOS = ["Crianças", "Pagamento", "Confirmar"];
const FORMAS = ["Pix", "Dinheiro", "Transferência", "Cartão", "Boleto"];

/** Separa "SL03, SL04 SL06;SL13" em codigos, sem repetir. */
function separarCodigos(texto) {
  const partes = texto
    .split(/[\s,;]+/)
    .map((c) => c.trim())
    .filter(Boolean);
  return [...new Set(partes.map((c) => c.toUpperCase()))];
}

/** "2 cestas + 1 festa". */
function resumoTipos(escolhas) {
  const conta = { cesta: 0, festa: 0 };
  for (const e of escolhas) conta[e.tipo] += 1;
  const partes = [];
  if (conta.cesta)
    partes.push(`${conta.cesta} ${conta.cesta === 1 ? "cesta" : "cestas"}`);
  if (conta.festa)
    partes.push(`${conta.festa} ${conta.festa === 1 ? "festa" : "festas"}`);
  return partes.join(" + ");
}

/** Apadrinhar uma crianca, passo a passo: escolher, pagar, confirmar.
 *
 * Nao existe mais "reservar" uma crianca para pagar depois — a promessa
 * segurava a crianca para um padrinho que podia nunca pagar. Agora so se grava
 * quando tudo esta na mao, comprovante incluido, e o servidor grava criancas e
 * pagamento juntos, ou nada.
 *
 * Um passo por vez, e nao tudo numa tela: quem esta no telefone com o
 * padrinho resolve uma pergunta de cada vez — quais criancas, como pagou, e
 * so entao confere o resumo antes de gravar. Voltar nao perde nada.
 *
 * O valor nao e digitado: e a soma do preco de cada escolha, que vem da
 * edicao da crianca (cesta e festa custam diferente, e entre cidades o preco
 * e o da cidade dela).
 */
export default function ApadrinharCriancas({
  padrinho,
  aoMudar,
  aoFechar,
  // Pagina inteira em vez de janela — o caminho do celular.
  comoPagina = false,
}) {
  const { usuario } = useSessao();
  const notificar = useNotificar();
  const [passo, definirPasso] = useState(0);
  // Depois de gravar, no celular: o padrinho atualizado e as criancas que
  // acabaram de entrar, para o fim do fluxo — o agradecimento.
  const [concluido, definirConcluido] = useState(null);
  const [baixando, definirBaixando] = useState(false);

  const [texto, definirTexto] = useState("");
  const [procurando, definirProcurando] = useState(false);
  const [erro, definirErro] = useState("");

  // Um item por codigo procurado, na ordem em que foi escrito.
  const [resultados, definirResultados] = useState([]);
  // As escolhas: "idDaCrianca:tipo".
  const [marcadas, definirMarcadas] = useState([]);

  const [data, definirData] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [forma, definirForma] = useState(FORMAS[0]);
  const [observacoes, definirObservacoes] = useState("");
  const [arquivo, definirArquivo] = useState(null);
  const [salvando, definirSalvando] = useState(false);

  /** Por que este tipo desta crianca nao pode ser escolhido — ou "" se pode.
   *
   *  A promessa antiga ainda conta: ela segura o lugar no banco, que e unico
   *  por (crianca, tipo). Se a tela a ignorasse, ofereceria uma escolha que o
   *  servidor vai recusar. */
  function bloqueio(crianca, tipo) {
    if (crianca[`tem_padrinho_${tipo}`]) return "já apadrinhada";
    if (crianca[`promessa_${tipo}`]) return "reservada, a pagar";
    return "";
  }

  /** Esta crianca nao e da lista de quem esta olhando?
   *
   *  A busca por codigo ACHA crianca de qualquer instituicao das suas
   *  edicoes, mas achar nao e poder ligar: o comissario so apadrinha as
   *  atribuidas a ele, e o backend recusa as outras. Vale so para quem e
   *  filtrado crianca a crianca. */
  function foraDaMinhaLista(crianca) {
    if (!crianca || usuario.admin_geral) return false;
    const vinculo = usuario.vinculos.find(
      (v) => v.edicao_id === crianca.edicao_id,
    );
    if (!vinculo?.so_criancas_atribuidas) return false;
    return crianca.comissario_id !== usuario.id;
  }

  /** A crianca inteira esta fora: nao e da lista, ou desistiu. */
  function barrada(crianca) {
    return (
      !crianca || foraDaMinhaLista(crianca) || Boolean(crianca.desistiu_em)
    );
  }

  const soMinhaLista =
    !usuario.admin_geral &&
    usuario.vinculos.some((v) => v.so_criancas_atribuidas);

  const achadas = resultados.filter((r) => r.crianca);
  const escolhas = achadas.flatMap((r) =>
    TIPOS.filter((t) => marcadas.includes(`${r.crianca.id}:${t}`)).map((t) => ({
      crianca: r.crianca,
      tipo: t,
      valor: Number(r.crianca[`valor_${t}`] ?? 0),
    })),
  );
  const total = escolhas.reduce((s, e) => s + e.valor, 0);

  // O que ainda impede de seguir, em cada passo. Vira a frase do rodape e o
  // motivo de o botao estar inativo — os dois saem daqui.
  const falta = [
    escolhas.length === 0 ? "Procure as crianças e marque cesta ou festa." : "",
    !arquivo ? "Escolha o comprovante para continuar." : "",
    "",
  ][passo];

  function alternar(crianca, tipo) {
    const chave = `${crianca.id}:${tipo}`;
    definirMarcadas((atual) =>
      atual.includes(chave)
        ? atual.filter((x) => x !== chave)
        : [...atual, chave],
    );
  }

  /** O atalho de quem leva "a cesta de todas": marca o tipo onde ele cabe. */
  function marcarTodas(tipo) {
    const livres = achadas
      .filter((r) => !barrada(r.crianca) && !bloqueio(r.crianca, tipo))
      .map((r) => `${r.crianca.id}:${tipo}`);
    const todasJa = livres.every((c) => marcadas.includes(c));
    definirMarcadas((atual) =>
      todasJa
        ? atual.filter((c) => !livres.includes(c))
        : [...new Set([...atual, ...livres])],
    );
  }

  async function procurar() {
    const codigos = separarCodigos(texto);
    definirErro("");
    if (codigos.length === 0) return;
    if (codigos.length > TETO) {
      definirErro(`Procure no máximo ${TETO} códigos por vez.`);
      return;
    }

    definirProcurando(true);
    try {
      // Em paralelo: sao consultas independentes e pequenas.
      const achados = await Promise.all(
        codigos.map(async (codigo) => {
          try {
            const { itens } = await listarCriancas({ codigo });
            return itens.length
              ? { codigo, crianca: itens[0] }
              : { codigo, crianca: null, estado: "nao-encontrada" };
          } catch (e) {
            return { codigo, crianca: null, estado: "falhou", erro: e.message };
          }
        }),
      );
      // Uma nova busca SOMA a lista, e nao a substitui: o padrinho lembra de
      // mais uma crianca no meio da conversa, e o que ja foi marcado fica.
      definirResultados((atual) => {
        const ja = new Set(atual.map((r) => r.codigo));
        return [...atual, ...achados.filter((r) => !ja.has(r.codigo))];
      });
      definirTexto("");
    } finally {
      definirProcurando(false);
    }
  }

  function tirar(codigo, crianca) {
    definirResultados((atual) => atual.filter((r) => r.codigo !== codigo));
    if (crianca) {
      definirMarcadas((atual) =>
        atual.filter((c) => !c.startsWith(`${crianca.id}:`)),
      );
    }
  }

  async function confirmar() {
    definirErro("");
    definirSalvando(true);
    try {
      const atualizado = await apadrinharComPagamento(padrinho.id, {
        criancas: escolhas.map((e) => ({
          crianca_id: e.crianca.id,
          tipo: e.tipo,
        })),
        data,
        forma,
        observacoes: observacoes.trim() || null,
      });
      aoMudar?.(atualizado);

      // O comprovante vem depois e em separado: se ele falhar, o apadrinhamento
      // e o pagamento ja estao gravados, e o arquivo entra pela aba Pagamentos.
      try {
        await subirComprovante(atualizado.ultimo_pagamento_id, arquivo);
        notificar(
          `${resumoTipos(escolhas)} para ${padrinho.nome.split(" ")[0]}, ${dinheiro(total)} registrados.`,
        );
      } catch (e) {
        notificar(
          `Apadrinhado e pago, mas o comprovante não subiu: ${e.message} ` +
            "Envie o arquivo pela aba Pagamentos.",
        );
      }
      if (comoPagina) {
        // No celular o fluxo nao acaba aqui: o comissario esta com o padrinho
        // na conversa, e o agradecimento e o proximo gesto. Um por crianca —
        // cesta e festa da mesma crianca sao o mesmo agradecimento.
        const novas = new Set(escolhas.map((e) => e.crianca.id));
        const porCrianca = new Map();
        for (const a of atualizado.apadrinhamentos) {
          if (a.pago && novas.has(a.crianca_id) && !porCrianca.has(a.crianca_id)) {
            porCrianca.set(a.crianca_id, a);
          }
        }
        definirConcluido({ padrinho: atualizado, apadrinhamentos: [...porCrianca.values()] });
        return;
      }
      aoFechar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  // No celular os botoes crescem para o tamanho do dedo, e o Continuar perde
  // o valor e encurta o rotulo final: lado a lado com o Voltar, numa tela de
  // 360px, o texto longo nao cabia.
  const tamanho = comoPagina ? "md" : "sm";
  const rodape = (
    <div className="passos__rodape">
      {passo === 0 ? (
        <Button size={tamanho} variant="ghost" onClick={aoFechar}>
          Cancelar
        </Button>
      ) : (
        <Button
          size={tamanho}
          variant="ghost"
          onClick={() => definirPasso(passo - 1)}
          disabled={salvando}
        >
          Voltar
        </Button>
      )}
      {falta && <span className="pagamento__falta">{falta}</span>}
      {passo < PASSOS.length - 1 ? (
        <Button
          size={tamanho}
          variant="secondary"
          disabled={Boolean(falta)}
          onClick={() => definirPasso(passo + 1)}
        >
          {passo === 0 && escolhas.length > 0 && !comoPagina
            ? `Continuar · ${dinheiro(total)}`
            : "Continuar"}
        </Button>
      ) : (
        <Button
          size={tamanho}
          variant="secondary"
          onClick={confirmar}
          carregando={salvando}
        >
          {comoPagina ? "Apadrinhar e pagar" : "Apadrinhar e registrar pagamento"}
        </Button>
      )}
    </div>
  );

  /* Onde se esta e o que vem depois. So mostra; quem anda e o rodape. */
  const faixaDePassos = (
    <ol className="passos" aria-label="Passos">
      {PASSOS.map((nome, i) => (
        <li
          key={nome}
          className={`passos__item ${i === passo ? "passos__item--atual" : ""} ${
            i < passo ? "passos__item--feito" : ""
          }`}
          aria-current={i === passo ? "step" : undefined}
        >
          <span className="passos__numero">{i < passo ? <Visto t={12} /> : i + 1}</span>
          {nome}
        </li>
      ))}
    </ol>
  );

  const conteudo = (
    <>
      <Mensagem tipo="erro">{erro}</Mensagem>

      {passo === 0 && passoCriancas()}
      {passo === 1 && passoPagamento()}
      {passo === 2 && passoConfirmar()}
    </>
  );

  /* No celular o passo a passo e uma PAGINA, e nao uma janela: o modal
     espremia a lista de criancas e o teclado aberto cobria o rodape. Ela
     cobre a tela inteira em tres faixas — os passos fixos em cima, os botoes
     fixos embaixo, e so o meio rola. Assim, com vinte criancas na lista, o
     Continuar e o "onde estou" continuam a vista. */
  if (comoPagina && concluido) {
    return createPortal(telaFinal(), document.body);
  }

  if (comoPagina) {
    // Por portal, direto no <body>: dentro da arvore do layout, qualquer
    // ancestral com transform ou overflow vira a referencia do `fixed` e
    // corta a pagina.
    return createPortal(
      <div className="apadrinhar-pagina">
        <header className="apadrinhar-pagina__topo">
          <button
            type="button"
            className="pasta-aberta__voltar"
            onClick={() => !salvando && aoFechar()}
          >
            ← {padrinho.nome.split(" ")[0]}
          </button>
          <div className="pagina__eyebrow">Apadrinhar com {padrinho.nome}</div>
          <h1 className="pagina__titulo">{PASSOS[passo]}</h1>
          {faixaDePassos}
        </header>
        <div className="apadrinhar-pagina__meio">{conteudo}</div>
        <div className="apadrinhar-pagina__rodape">{rodape}</div>
      </div>,
      document.body,
    );
  }

  return (
    <Modal
      rotulo={`Apadrinhar com ${padrinho.nome.split(" ")[0]}:`}
      titulo={PASSOS[passo]}
      aoFechar={() => !salvando && aoFechar()}
      tamanho="grande"
      rodape={rodape}
    >
      {faixaDePassos}
      {conteudo}
    </Modal>
  );

  /** Baixa o agradecimento de cada crianca nova, um arquivo por vez. Em
   *  serie e com pausa: disparados juntos, o navegador descarta parte. */
  async function baixarAgradecimentos() {
    definirErro("");
    definirBaixando(true);
    try {
      for (const a of concluido.apadrinhamentos) {
        await baixarAgradecimento(a.id);
        await new Promise((pronto) => setTimeout(pronto, 400));
      }
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirBaixando(false);
    }
  }

  /** O fim do fluxo no celular: deu certo, e o agradecimento a um toque. */
  function telaFinal() {
    const { padrinho: atual, apadrinhamentos } = concluido;
    const nomes = apadrinhamentos.map((a) => a.crianca_primeiro_nome);
    const criancas =
      nomes.length > 1 ? `${nomes.slice(0, -1).join(", ")} e ${nomes.at(-1)}` : nomes[0];
    const zap = linkWhatsapp(
      atual.whatsapp,
      `Oi, ${primeiroNome(atual.nome)}! Obrigado por apadrinhar ${criancas} no Natal Lumen. ` +
        "Segue o nosso agradecimento.",
    );

    return (
      <div className="apadrinhar-pagina">
        <header className="apadrinhar-pagina__topo">
          <div className="pagina__eyebrow">Apadrinhar com {atual.nome}</div>
          <h1 className="pagina__titulo">Apadrinhado!</h1>
        </header>

        <div className="apadrinhar-pagina__meio">
          <Mensagem tipo="erro">{erro}</Mensagem>
          <p className="apadrinhar-final__texto">
            <Visto t={16} /> {primeiroNome(atual.nome)} apadrinhou {criancas}. O pagamento já
            está registrado.
          </p>

          {/* Os dois gestos, na ordem: baixar a arte para o celular, e abrir
              a conversa com a mensagem pronta para anexar nela. O link do
              WhatsApp so leva texto — a imagem vai pela galeria. */}
          <div className="apadrinhar-final__agradecimento">
            <Button
              larguraTotal
              variant="ghost"
              iconLeft={<Baixar t={16} />}
              onClick={baixarAgradecimentos}
              carregando={baixando}
            >
              {apadrinhamentos.length === 1
                ? "Baixar o agradecimento"
                : `Baixar os ${apadrinhamentos.length} agradecimentos`}
            </Button>
            <Button
              larguraTotal
              variant="secondary"
              iconLeft={<Enviar t={16} />}
              disabled={!zap}
              onClick={() => window.open(zap, "_blank", "noopener")}
            >
              Enviar mensagem no WhatsApp
            </Button>
            <p className="campo__dica">
              {zap
                ? "Baixe primeiro: a conversa abre com o texto pronto, e a imagem você anexa da galeria."
                : "Este padrinho não tem WhatsApp válido cadastrado."}
            </p>
          </div>
        </div>

        <div className="apadrinhar-pagina__rodape">
          <div className="passos__rodape">
            <Button variant="ghost" onClick={aoFechar}>
              Concluir
            </Button>
          </div>
        </div>
      </div>
    );
  }

  /* Funcoes que devolvem JSX, e nao componentes: declarados aqui dentro,
     nasceriam diferentes a cada render e os campos perderiam o foco. */

  function passoCriancas() {
    return (
      <>
        <p className="campo__dica" style={{ marginTop: 0 }}>
          Busque pelo código da criança — várias de uma vez, separadas por
          vírgula.
          {soMinhaLista && " Você apadrinha só as crianças da sua lista."}
        </p>

        <div className="ficha__acao">
          <Entrada
            classe="campo--cresce"
            aria-label="Códigos das crianças"
            placeholder="SL03, SL04, SL06"
            value={texto}
            onChange={(e) => definirTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                procurar();
              }
            }}
          />
          <Button
            variant="ghost"
            size={tamanho}
            onClick={procurar}
            disabled={!texto.trim()}
            carregando={procurando}
          >
            Procurar
          </Button>
        </div>

        {resultados.length > 0 && listaDeCriancas()}
      </>
    );
  }

  function passoPagamento() {
    return (
      <div className="formulario-compacto">
        {/* O valor em cima: e o numero que se confere contra o comprovante. */}
        <div className="pagamento__soma passos__total">
          <span className="pagamento__valor">{dinheiro(total)}</span>
          <span className="pagamento__tipos">{resumoTipos(escolhas)}</span>
        </div>

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
              <option key={f} value={f}>
                {f}
              </option>
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
    );
  }

  function passoConfirmar() {
    return (
      <>
        <p className="campo__dica" style={{ marginTop: 0 }}>
          Confira antes de gravar. As crianças e o pagamento entram juntos.
        </p>

        <div className="ficha__lista">
          {escolhas.map((e) => (
            <div key={`${e.crianca.id}:${e.tipo}`} className="ficha__linha">
              <span className="ficha__linha-nome">
                <span className="ficha__linha-codigo">{e.crianca.codigo}</span>
                {e.crianca.nome}, {e.crianca.idade}
              </span>
              <span className="etiqueta etiqueta--neutra">{e.tipo}</span>
              <span className="pagamento__preco">{dinheiro(e.valor)}</span>
            </div>
          ))}
        </div>

        <dl
          className="ficha ficha--duas"
          style={{ marginTop: "var(--space-5)" }}
        >
          <dt>Total</dt>
          <dd>
            <strong>{dinheiro(total)}</strong> · {resumoTipos(escolhas)}
          </dd>
          <dt>Pagamento</dt>
          <dd>
            {forma} em {formatarData(data)}
          </dd>
          <dt>Comprovante</dt>
          <dd>{arquivo?.name}</dd>
          {observacoes.trim() && (
            <>
              <dt>Observação</dt>
              <dd>{observacoes.trim()}</dd>
            </>
          )}
        </dl>
      </>
    );
  }

  function listaDeCriancas() {
    return (
      <div className="ficha__lista" style={{ marginTop: "var(--space-4)" }}>
        {achadas.length > 1 && (
          <div className="ficha__linha ficha__linha--cabecalho">
            <span className="ficha__linha-nome">{achadas.length} crianças</span>
            <span className="ficha__linha-acoes apadrinhar__escolhas">
              {TIPOS.map((t) => (
                <button
                  key={t}
                  type="button"
                  className="link-conferir"
                  onClick={() => marcarTodas(t)}
                >
                  {t} em todas
                </button>
              ))}
            </span>
          </div>
        )}

        {resultados.map((r) => {
          const c = r.crianca;
          const fora = c && foraDaMinhaLista(c);
          return (
            <div key={r.codigo} className="ficha__linha">
              <span
                className="ficha__linha-nome"
                title={c ? c.instituicao : undefined}
              >
                {c ? (
                  <>
                    <span className="ficha__linha-codigo">{c.codigo}</span>
                    {c.nome}, {c.idade}
                  </>
                ) : (
                  <span className="celula--vazia">{r.codigo}</span>
                )}
              </span>

              <span className="ficha__linha-etiquetas">
                {c?.desistiu_em && <EtiquetaDesistente />}
                {fora && (
                  <span
                    className="etiqueta etiqueta--parado"
                    title={
                      c.comissario
                        ? `${c.nome} está na lista de ${c.comissario}. ` +
                          "Cada comissário apadrinha as crianças atribuídas a ele."
                        : `${c.nome} ainda não tem comissário responsável. ` +
                          "Fale com a coordenação para recebê-la na sua lista."
                    }
                  >
                    {c.comissario
                      ? `é de ${nomeCurto(c.comissario)}`
                      : "sem responsável"}
                  </span>
                )}
                {r.estado === "nao-encontrada" && (
                  <span className="etiqueta etiqueta--parado">
                    não encontrada
                  </span>
                )}
                {r.estado === "falhou" && (
                  <span className="etiqueta etiqueta--parado" title={r.erro}>
                    erro na busca
                  </span>
                )}
              </span>

              <span className="ficha__linha-acoes apadrinhar__escolhas">
                {/* Cesta e festa lado a lado, cada uma com o preco: o
                        padrinho escolhe uma, a outra ou as duas. O tipo ja
                        tomado aparece travado, com o motivo escrito. */}
                {c &&
                  !barrada(c) &&
                  TIPOS.map((t) => {
                    const motivo = bloqueio(c, t);
                    return (
                      <label
                        key={t}
                        className="marcavel"
                        title={motivo ? `${t}: ${motivo}` : undefined}
                        style={motivo ? { opacity: 0.5 } : undefined}
                      >
                        <input
                          type="checkbox"
                          disabled={Boolean(motivo)}
                          checked={marcadas.includes(`${c.id}:${t}`)}
                          onChange={() => alternar(c, t)}
                        />
                        {t} {motivo ? `· ${motivo}` : dinheiro(c[`valor_${t}`])}
                      </label>
                    );
                  })}
                <BotaoIcone
                  titulo={`Tirar ${c ? c.nome : r.codigo} da lista`}
                  tamanho={comoPagina ? "md" : "sm"}
                  onClick={() => tirar(r.codigo, c)}
                >
                  <Xis t={14} />
                </BotaoIcone>
              </span>
            </div>
          );
        })}
      </div>
    );
  }
}
