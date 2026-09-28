import { useEffect, useState } from "react";
import Button from "../core/Button.jsx";
import { AreaTexto, Entrada, Selecao } from "../core/Campo.jsx";
import { Visto } from "../core/icones.jsx";
import Carregando from "../feedback/Carregando.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import {
  CATEGORIAS_QUE_SE_ESCOLHEM,
  criarRecebimento,
  eApadrinhamento,
  subirComprovanteDoRecebimento,
} from "../../services/financeiro.js";
import { criarPagamento, listarPadrinhos, subirComprovante } from "../../services/padrinhos.js";
import { dinheiro } from "../../utils/dinheiro.js";

const hoje = () => new Date().toISOString().slice(0, 10);
const FORMAS = ["Pix", "Dinheiro", "Transferência", "Cartão", "Boleto"];

/** Registra dinheiro que entrou na edição — e a CATEGORIA decide o quê.
 *
 * Escolher "apadrinhamento - cesta" ou "- festa" não cria um recebimento
 * solto: cria um PAGAMENTO do padrinho, ligado aos apadrinhamentos daquele
 * tipo que ele ainda não pagou. É o que garante que a categoria da linha nunca
 * divirja do que o dinheiro quitou — ela é derivada dali, não digitada.
 *
 * "Doação" e "Outros" são o dinheiro que chega sem padrinho do outro lado:
 * esses sim viram uma linha de `recebimentos`, com quem doou escrito à mão.
 *
 * O comprovante sobe DEPOIS, em requisição separada, nos dois caminhos: o
 * lançamento do dinheiro é a parte que não pode falhar, e um arquivo grande
 * demais não pode derrubá-la junto.
 *
 * **No apadrinhamento ele é obrigatório**, como na ficha do padrinho: sem
 * arquivo ninguém confere depois se aquele valor chegou. Na doação é opcional —
 * dinheiro que alguém deixa na caixinha às vezes não tem recibo nenhum, e
 * recusar o lançamento faria a edição perder o registro do dinheiro em vez de
 * ganhar a prova dele. A linha fica com a etiqueta "falta" até o arquivo vir.
 */
export default function NovoRecebimento({ edicaoId, aoFechar, aoRegistrar }) {
  const [categoria, definirCategoria] = useState(CATEGORIAS_QUE_SE_ESCOLHEM[0].valor);
  const escolhida = CATEGORIAS_QUE_SE_ESCOLHEM.find((c) => c.valor === categoria);
  const dePadrinho = eApadrinhamento(categoria);

  const [data, definirData] = useState(hoje);
  const [forma, definirForma] = useState(FORMAS[0]);
  const [valor, definirValor] = useState("");
  const [arquivo, definirArquivo] = useState(null);

  // Só do lado do apadrinhamento.
  const [padrinhos, definirPadrinhos] = useState(null);
  const [padrinhoId, definirPadrinhoId] = useState("");
  const [marcados, definirMarcados] = useState([]);

  // Só do lado da doação.
  const [descricao, definirDescricao] = useState("");
  const [doador, definirDoador] = useState("");
  const [observacoes, definirObservacoes] = useState("");

  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState("");

  // A lista de padrinhos só é buscada se ela for usada: quem vem lançar uma
  // doação não precisa esperar por ela.
  useEffect(() => {
    if (!dePadrinho || padrinhos !== null) return;

    let vivo = true;
    listarPadrinhos({ por_pagina: 200 })
      .then((r) => vivo && definirPadrinhos(r.itens))
      .catch((e) => vivo && definirErro(e.message));

    return () => {
      vivo = false;
    };
  }, [dePadrinho, padrinhos]);

  const padrinho = padrinhos?.find((p) => String(p.id) === String(padrinhoId));

  // Só os do tipo escolhido, e só os que ainda não foram pagos: é isso que
  // mantém a linha de "apadrinhamento - cesta" sendo de cesta mesmo.
  const aPagar =
    padrinho?.apadrinhamentos.filter((a) => !a.pago && a.tipo === escolhida?.tipo) ?? [];

  const somaMarcada = aPagar
    .filter((a) => marcados.includes(a.id))
    .reduce((soma, a) => soma + Number(a.valor), 0);

  function trocarCategoria(nova) {
    definirCategoria(nova);
    definirErro("");
    // O que foi marcado era de outro tipo: manter a marcação faria um
    // pagamento de festa nascer quitando cestas.
    definirMarcados([]);
    definirValor("");
  }

  function alternar(id) {
    definirMarcados((atual) =>
      atual.includes(id) ? atual.filter((x) => x !== id) : [...atual, id],
    );
  }

  function marcarTodos() {
    definirMarcados(marcados.length === aPagar.length ? [] : aPagar.map((a) => a.id));
  }

  /** Sobe o comprovante e diz a verdade se só ele falhar. */
  async function anexar(subir, id) {
    if (!arquivo) return true;
    try {
      await subir(id, arquivo);
      return true;
    } catch (e) {
      definirErro(
        `O dinheiro foi registrado, mas o comprovante não subiu: ${e.message} ` +
          "Envie o arquivo pela linha dele na lista.",
      );
      await aoRegistrar();
      return false;
    }
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);

    try {
      if (dePadrinho) {
        const pagamento = await criarPagamento({
          padrinho_id: Number(padrinhoId),
          valor: valor || somaMarcada.toFixed(2),
          data,
          forma: forma || null,
          observacoes: observacoes.trim() || null,
          apadrinhamentos: marcados,
        });
        if (!(await anexar(subirComprovante, pagamento.id))) return;
      } else {
        const recebimento = await criarRecebimento({
          edicao_id: Number(edicaoId),
          descricao: descricao.trim(),
          categoria,
          valor,
          data,
          doador: doador.trim() || null,
          forma: forma.trim() || null,
          observacoes: observacoes.trim() || null,
        });
        if (!(await anexar(subirComprovanteDoRecebimento, recebimento.id))) return;
      }

      await aoRegistrar();
      aoFechar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  const podeSalvar = dePadrinho
    ? Boolean(padrinhoId) && (Boolean(valor) || somaMarcada > 0) && Boolean(arquivo)
    : descricao.trim().length > 1 && Number(valor) > 0;

  return (
    <form onSubmit={salvar}>
      <Mensagem tipo="erro">{erro}</Mensagem>

      {/* Primeiro campo, e o que decide a forma do resto: o que entrou. */}
      <Selecao
        rotulo="O que entrou"
        value={categoria}
        onChange={(e) => trocarCategoria(e.target.value)}
      >
        {CATEGORIAS_QUE_SE_ESCOLHEM.map((c) => (
          <option key={c.valor} value={c.valor}>{c.rotulo}</option>
        ))}
      </Selecao>

      {dePadrinho ? (
        <>
          {padrinhos === null ? (
            <Carregando>Buscando os padrinhos...</Carregando>
          ) : (
            <Selecao
              rotulo="Padrinho"
              value={padrinhoId}
              onChange={(e) => {
                definirPadrinhoId(e.target.value);
                definirMarcados([]);
                definirValor("");
              }}
              required
            >
              <option value="">Escolha</option>
              {padrinhos.map((p) => (
                <option key={p.id} value={p.id}>{p.nome}</option>
              ))}
            </Selecao>
          )}

          {padrinho && (
            <div className="campo">
              <span className="campo__rotulo">
                {escolhida.tipo === "cesta" ? "Cestas" : "Festas"} que este dinheiro quita
              </span>
              {aPagar.length === 0 ? (
                <span className="campo__dica">
                  Este padrinho não tem {escolhida.tipo} em aberto. Ou já está tudo
                  pago, ou o apadrinhamento ainda não foi registrado na ficha dele.
                </span>
              ) : (
                <div className="pagamento__lista">
                  <label className="pagamento__linha pagamento__linha--cabecalho">
                    <input
                      type="checkbox"
                      checked={marcados.length === aPagar.length}
                      onChange={marcarTodos}
                      aria-label="Marcar todos"
                    />
                    <span className="pagamento__nome">
                      {aPagar.length} em aberto · {marcados.length} marcado(s)
                    </span>
                    <span className="pagamento__preco">{dinheiro(somaMarcada)}</span>
                  </label>

                  {aPagar.map((a) => (
                    <label key={a.id} className="pagamento__linha">
                      <input
                        type="checkbox"
                        checked={marcados.includes(a.id)}
                        onChange={() => alternar(a.id)}
                      />
                      {/* Código na frente, nome completo em seguida: é pelo
                          código que se casa com a planilha. */}
                      <span
                        className="pagamento__nome"
                        title={`${a.crianca_codigo} · ${a.crianca_nome}`}
                      >
                        <span className="ficha__linha-codigo">{a.crianca_codigo}</span>
                        {a.crianca_nome}, {a.crianca_idade}
                      </span>
                      <span className="pagamento__preco">{dinheiro(a.valor)}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      ) : (
        <>
          <Entrada
            rotulo="O que foi"
            value={descricao}
            onChange={(e) => definirDescricao(e.target.value)}
            dica="Ex.: doação da padaria, rifa da comunidade, patrocínio do buffet"
            required
          />
          <Entrada
            rotulo="Quem doou"
            value={doador}
            onChange={(e) => definirDoador(e.target.value)}
            dica="Pessoa ou empresa. Opcional."
          />
        </>
      )}

      <div className="linha-campos">
        <Entrada
          rotulo="Valor"
          tipo="number"
          step="0.01"
          min="0.01"
          value={valor}
          onChange={(e) => definirValor(e.target.value)}
          dica={
            dePadrinho
              ? somaMarcada > 0
                ? `Em branco usa a soma marcada: ${dinheiro(somaMarcada)}`
                : "Em branco usa a soma do que for marcado acima."
              : undefined
          }
          required={!dePadrinho}
        />
        <Entrada
          rotulo="Data"
          tipo="date"
          value={data}
          onChange={(e) => definirData(e.target.value)}
          required
        />
        {dePadrinho ? (
          <Selecao rotulo="Forma" value={forma} onChange={(e) => definirForma(e.target.value)}>
            {FORMAS.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </Selecao>
        ) : (
          <Entrada
            rotulo="Forma"
            value={forma}
            onChange={(e) => definirForma(e.target.value)}
            sugestoes={FORMAS}
            dica="Pix, dinheiro, transferência..."
          />
        )}
      </div>

      <AreaTexto
        rotulo="Observação"
        linhas={2}
        value={observacoes}
        onChange={(e) => definirObservacoes(e.target.value)}
        dica={
          dePadrinho
            ? "O que este dinheiro tem de diferente. Aparece na linha dele na lista."
            : "Número do recibo, o que foi combinado com quem doou..."
        }
      />

      {/* Mesmo controle da ficha do padrinho: o bloco inteiro e o alvo do
          clique e muda de estado quando o arquivo entra. */}
      <label className={`arquivo ${arquivo ? "arquivo--cheio" : ""}`}>
        <span className="arquivo__rotulo">
          {arquivo && <Visto t={14} />}
          Comprovante
          {!arquivo && dePadrinho && <span className="arquivo__exigido">obrigatório</span>}
        </span>
        <input
          type="file"
          accept="image/jpeg,image/png,application/pdf"
          onChange={(e) => definirArquivo(e.target.files?.[0] ?? null)}
        />
        <span className="arquivo__estado">
          {arquivo
            ? arquivo.name
            : dePadrinho
              ? "Foto do Pix, print ou PDF do banco. Sem ele não há como conferir o valor depois."
              : "Foto ou PDF. Opcional — pode subir depois, pela linha da lista."}
        </span>
      </label>

      <div className="barra-acoes barra-acoes--fim">
        <Button variant="secondary" type="submit" carregando={salvando} disabled={!podeSalvar}>
          Salvar
        </Button>
        <Button variant="ghost" onClick={aoFechar} disabled={salvando}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
