import { useState } from "react";
import Button from "../core/Button.jsx";
import { AreaTexto, Entrada, Selecao } from "../core/Campo.jsx";
import { Visto } from "../core/icones.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import {
  CATEGORIAS_QUE_SE_ESCOLHEM,
  criarRecebimento,
  subirComprovanteDoRecebimento,
} from "../../services/financeiro.js";

const hoje = () => new Date().toISOString().slice(0, 10);
const FORMAS = ["Pix", "Dinheiro", "Transferência", "Cartão", "Boleto"];

/** Registra dinheiro que entrou na edição sem padrinho do outro lado: doação
 * ou outros, com quem doou escrito à mão.
 *
 * Pagamento de apadrinhamento NÃO se lança aqui. Ele se registra na ficha do
 * padrinho, na página de padrinhos, onde nasce ligado às crianças que quita —
 * e aparece na lista do financeiro sozinho. Lançado daqui, seria dinheiro de
 * padrinho sem criança nenhuma ligada a ele.
 *
 * O comprovante sobe DEPOIS, em requisição separada: o lançamento do dinheiro
 * é a parte que não pode falhar, e um arquivo grande demais não pode derrubá-la
 * junto. Aqui ele é opcional — dinheiro que alguém deixa na caixinha às vezes
 * não tem recibo nenhum, e recusar o lançamento faria a edição perder o
 * registro do dinheiro em vez de ganhar a prova dele. A linha fica com a
 * etiqueta "falta" até o arquivo vir.
 */
export default function NovoRecebimento({ edicaoId, aoFechar, aoRegistrar }) {
  const [categoria, definirCategoria] = useState(CATEGORIAS_QUE_SE_ESCOLHEM[0].valor);

  const [data, definirData] = useState(hoje);
  const [forma, definirForma] = useState(FORMAS[0]);
  const [valor, definirValor] = useState("");
  const [arquivo, definirArquivo] = useState(null);
  const [descricao, definirDescricao] = useState("");
  const [doador, definirDoador] = useState("");
  const [observacoes, definirObservacoes] = useState("");

  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState("");

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);

    try {
      const recebimento = await criarRecebimento({
        edicao_id: Number(edicaoId),
        // So "outros" tem o campo; a doacao vai sem, e o servidor a chama
        // de "Doação".
        descricao: categoria === "outros" ? descricao.trim() : null,
        categoria,
        valor,
        data,
        doador: doador.trim() || null,
        forma: forma.trim() || null,
        observacoes: observacoes.trim() || null,
      });

      if (arquivo) {
        try {
          await subirComprovanteDoRecebimento(recebimento.id, arquivo);
        } catch (e) {
          // O dinheiro ja esta registrado: diz a verdade sobre o que falhou.
          definirErro(
            `O dinheiro foi registrado, mas o comprovante não subiu: ${e.message} ` +
              "Envie o arquivo pela linha dele na lista.",
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

  const podeSalvar =
    (categoria !== "outros" || descricao.trim().length > 1) && Number(valor) > 0;

  return (
    <form onSubmit={salvar}>
      <Mensagem tipo="erro">{erro}</Mensagem>

      <Selecao
        rotulo="O que entrou"
        value={categoria}
        onChange={(e) => {
          definirCategoria(e.target.value);
          definirErro("");
        }}
        dica="Pagamento de padrinho se registra na ficha dele, na página de padrinhos."
      >
        {CATEGORIAS_QUE_SE_ESCOLHEM.map((c) => (
          <option key={c.valor} value={c.valor}>{c.rotulo}</option>
        ))}
      </Selecao>

      {/* So em "outros": doacao ja diz o que e, e quem doou vai no campo de
          baixo. */}
      {categoria === "outros" && (
        <Entrada
          rotulo="O que foi"
          value={descricao}
          onChange={(e) => definirDescricao(e.target.value)}
          dica="Ex.: rifa da comunidade, patrocínio do buffet, venda de camisetas"
          required
        />
      )}
      <Entrada
        rotulo="Quem doou"
        value={doador}
        onChange={(e) => definirDoador(e.target.value)}
        dica="Pessoa ou empresa. Opcional."
      />

      <div className="linha-campos">
        <Entrada
          rotulo="Valor"
          tipo="number"
          step="0.01"
          min="0.01"
          value={valor}
          onChange={(e) => definirValor(e.target.value)}
          required
        />
        <Entrada
          rotulo="Data"
          tipo="date"
          value={data}
          onChange={(e) => definirData(e.target.value)}
          required
        />
        <Entrada
          rotulo="Forma"
          value={forma}
          onChange={(e) => definirForma(e.target.value)}
          sugestoes={FORMAS}
          dica="Pix, dinheiro, transferência..."
        />
      </div>

      <AreaTexto
        rotulo="Observação"
        linhas={2}
        value={observacoes}
        onChange={(e) => definirObservacoes(e.target.value)}
        dica="Número do recibo, o que foi combinado com quem doou..."
      />

      {/* Mesmo controle da ficha do padrinho: o bloco inteiro e o alvo do
          clique e muda de estado quando o arquivo entra. */}
      <label className={`arquivo ${arquivo ? "arquivo--cheio" : ""}`}>
        <span className="arquivo__rotulo">
          {arquivo && <Visto t={14} />}
          Comprovante
        </span>
        <input
          type="file"
          accept="image/jpeg,image/png,application/pdf"
          onChange={(e) => definirArquivo(e.target.files?.[0] ?? null)}
        />
        <span className="arquivo__estado">
          {arquivo ? arquivo.name : "Foto ou PDF. Opcional — pode subir depois, pela linha da lista."}
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
