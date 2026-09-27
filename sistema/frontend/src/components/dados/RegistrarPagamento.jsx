import { useState } from "react";
import Button from "../core/Button.jsx";
import { Entrada, Selecao } from "../core/Campo.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import { criarPagamento, subirComprovante } from "../../services/padrinhos.js";
import { dinheiro } from "../../utils/dinheiro.js";

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

/** Registra um pagamento do padrinho e guarda o comprovante.
 *
 * O valor NAO e digitado: ele e a soma do que foi marcado. Cada
 * apadrinhamento ja tem o proprio valor (cesta e festa custam diferente, e o
 * preco vem da edicao da crianca), entao digitar de novo so criaria
 * divergencia entre o que a base diz que foi quitado e o que o pagamento diz
 * que custou. Pagamento de valor diferente da soma — desconto, arredondamento
 * — continua na tela de Pagamentos, que edita o valor solto.
 */
export default function RegistrarPagamento({ padrinho, aoFechar, aoRegistrar }) {
  const aPagar = padrinho.apadrinhamentos.filter((a) => !a.pago);

  const [marcados, definirMarcados] = useState([]);
  const [data, definirData] = useState(() => new Date().toISOString().slice(0, 10));
  const [forma, definirForma] = useState(FORMAS[0]);
  const [arquivo, definirArquivo] = useState(null);
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState("");

  const escolhidos = aPagar.filter((a) => marcados.includes(a.id));
  const total = escolhidos.reduce((soma, a) => soma + Number(a.valor), 0);

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
        apadrinhamentos: marcados,
      });

      // O comprovante vem depois e em separado: se ele falhar, a quitacao ja
      // esta gravada e o arquivo pode ser reenviado pela tela de Pagamentos.
      if (arquivo) {
        try {
          await subirComprovante(pagamento.id, arquivo);
        } catch (e) {
          definirErro(
            `Pagamento registrado, mas o comprovante não subiu: ${e.message} ` +
              "Envie o arquivo de novo pela tela de Pagamentos.",
          );
          await aoRegistrar();
          return;
        }
      }

      await aoRegistrar();
      aoFechar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  // A aba existe mesmo assim: "tudo quitado" e uma resposta, e some-la faria a
  // faixa de abas mudar de tamanho — o defeito que as abas vieram resolver.
  if (aPagar.length === 0) {
    return (
      <Mensagem tipo="sucesso">
        Todos os apadrinhamentos deste padrinho já estão <strong>quitados</strong>.
      </Mensagem>
    );
  }

  return (
    <div className="pagamento">
      <Mensagem tipo="erro">{erro}</Mensagem>

      {/* O total e as acoes ficam no ALTO: com vinte criancas para marcar, um
          botao no pe da lista fica longe de onde a pessoa esta olhando. */}
      <div className="pagamento__topo">
        <div className="pagamento__soma">
          <span className="pagamento__valor">{dinheiro(total)}</span>
          <span className="pagamento__tipos">
            {escolhidos.length === 0 ? "nada marcado ainda" : resumoTipos(escolhidos)}
          </span>
        </div>

        <Entrada
          tipo="date"
          aria-label="Data do pagamento"
          value={data}
          onChange={(e) => definirData(e.target.value)}
        />
        <Selecao
          aria-label="Forma de pagamento"
          value={forma}
          onChange={(e) => definirForma(e.target.value)}
        >
          {FORMAS.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </Selecao>

        <Button
          variant="secondary"
          size="sm"
          onClick={registrar}
          disabled={marcados.length === 0}
          carregando={salvando}
        >
          Registrar
        </Button>
        <Button size="sm" variant="ghost" onClick={aoFechar} disabled={salvando}>
          Cancelar
        </Button>
      </div>

      <label className="pagamento__comprovante">
        <span className="pagamento__comprovante-rotulo">Comprovante</span>
        <input
          type="file"
          accept="image/jpeg,image/png,application/pdf"
          onChange={(e) => definirArquivo(e.target.files?.[0] ?? null)}
        />
        <span className="campo__dica" style={{ marginTop: 0 }}>
          Foto ou PDF. Opcional — pode subir depois.
        </span>
      </label>

      <div className="pagamento__lista">
        <label className="pagamento__linha pagamento__linha--cabecalho">
          <input
            type="checkbox"
            checked={marcados.length === aPagar.length}
            onChange={marcarTodos}
            aria-label="Marcar todos os apadrinhamentos a pagar"
          />
          <span className="pagamento__nome">
            {aPagar.length} a pagar · {marcados.length} marcado(s)
          </span>
        </label>

        {aPagar.map((a) => (
          <label key={a.id} className="pagamento__linha">
            <input
              type="checkbox"
              checked={marcados.includes(a.id)}
              onChange={() => alternar(a.id)}
            />
            {/* Mesmo par de sempre: codigo na frente, nome completo em
                seguida. Quem confere um comprovante contra a planilha procura
                pelo codigo, nao pelo primeiro nome. */}
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
  );
}
