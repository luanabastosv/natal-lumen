import { useState } from "react";
import Button from "../core/Button.jsx";
import { Entrada, Selecao } from "../core/Campo.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import { listarCriancas } from "../../services/criancas.js";
import { criarApadrinhamento } from "../../services/padrinhos.js";

// Busca por codigo e o "escape" que alcanca qualquer instituicao das edicoes
// do usuario, e cada uma fica registrada em log. Uma busca por codigo, uma
// linha de log — por isso o teto: colar uma lista de duzentos codigos nao
// pode virar duzentas consultas de uma tacada.
const TETO = 20;

/** Separa "SL03, SL04 SL06;SL13" em codigos, sem repetir. */
function separarCodigos(texto) {
  const partes = texto
    .split(/[\s,;]+/)
    .map((c) => c.trim())
    .filter(Boolean);
  return [...new Set(partes.map((c) => c.toUpperCase()))];
}

/** Liga este padrinho a uma ou varias criancas, buscadas pelo codigo.
 *
 * Duas coisas que a primeira versao errava:
 *
 * 1. "Procurar" virava "Confirmar" no mesmo lugar. O botao mudava de funcao
 *    debaixo do ponteiro — quem clicasse duas vezes rapido confirmava sem ter
 *    lido o nome. Agora "Procurar" fica onde esta e o "Confirmar" nasce ao
 *    lado do nome da crianca, que e o que se precisa ler antes de confirmar.
 * 2. Um codigo por vez. Na pratica um padrinho leva cinco, dez criancas de
 *    uma vez, e a lista chega colada de uma planilha.
 */
export default function ApadrinharCriancas({ padrinho, aoMudar, aoTerminar }) {
  const [texto, definirTexto] = useState("");
  const [tipo, definirTipo] = useState("cesta");
  const [procurando, definirProcurando] = useState(false);
  const [erro, definirErro] = useState("");

  // Um item por codigo procurado, na ordem em que foi escrito.
  const [resultados, definirResultados] = useState([]);

  /** Ja tem padrinho do tipo escolhido? O banco recusa o segundo com 409, e
   *  a tela tem de dizer isso ANTES do clique, nao depois do erro.
   *
   *  Depende do `tipo` selecionado, entao e calculado no render: trocar de
   *  cesta para festa pode liberar uma crianca que estava barrada. */
  function jaApadrinhada(crianca) {
    if (!crianca) return false;
    return tipo === "cesta" ? crianca.tem_padrinho_cesta : crianca.tem_padrinho_festa;
  }

  /** O outro tipo ja estar tomado nao impede nada — mas e bom saber. */
  function jaTemOutro(crianca) {
    if (!crianca) return false;
    return tipo === "cesta" ? crianca.tem_padrinho_festa : crianca.tem_padrinho_cesta;
  }

  const pendentes = resultados.filter(
    (r) => r.estado === "pendente" && !jaApadrinhada(r.crianca),
  );

  function mudarItem(codigo, mudanca) {
    definirResultados((atual) =>
      atual.map((r) => (r.codigo === codigo ? { ...r, ...mudanca } : r)),
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
    definirResultados([]);
    try {
      // Em paralelo: sao consultas independentes e pequenas, e em serie uma
      // lista de dez codigos teria dez idas e voltas em fila.
      const achados = await Promise.all(
        codigos.map(async (codigo) => {
          try {
            const { itens } = await listarCriancas({ codigo });
            return itens.length
              ? { codigo, crianca: itens[0], estado: "pendente" }
              : { codigo, crianca: null, estado: "nao-encontrada" };
          } catch (e) {
            return { codigo, crianca: null, estado: "falhou", erro: e.message };
          }
        }),
      );
      definirResultados(achados);
    } finally {
      definirProcurando(false);
    }
  }

  async function ligar(item) {
    mudarItem(item.codigo, { estado: "salvando" });
    try {
      aoMudar(
        await criarApadrinhamento({
          crianca_id: item.crianca.id,
          padrinho_id: padrinho.id,
          tipo,
        }),
      );
      mudarItem(item.codigo, { estado: "apadrinhada" });
      return true;
    } catch (e) {
      mudarItem(item.codigo, { estado: "pendente", erro: e.message });
      return false;
    }
  }

  /** Em serie, nao em paralelo: cada POST devolve o padrinho inteiro, e
   *  dispara-los juntos faria respostas fora de ordem sobrescreverem umas as
   *  outras — a ultima a chegar apagaria as anteriores da tela. */
  async function ligarTodas() {
    for (const item of pendentes) {
      await ligar(item);
    }
  }

  return (
    <>
      <p className="campo__dica" style={{ marginTop: 0 }}>
        Busque pelo código da criança — várias de uma vez, separadas por vírgula. A
        busca alcança qualquer instituição das suas edições e fica registrada.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>

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
        <Selecao
          aria-label="Tipo de apadrinhamento"
          value={tipo}
          onChange={(e) => definirTipo(e.target.value)}
        >
          <option value="cesta">Cesta</option>
          <option value="festa">Festa</option>
        </Selecao>
        {/* Contorno, nao cheio: o unico botao cheio da janela e o de
            confirmar, que e o que tem consequencia. Procurar e busca — a
            mesma familia de filtrar e paginar. */}
        <Button
          variant="ghost"
          size="sm"
          onClick={procurar}
          disabled={!texto.trim()}
          carregando={procurando}
        >
          Procurar
        </Button>
        <Button size="sm" variant="ghost" onClick={aoTerminar}>
          Fechar
        </Button>
      </div>

      {resultados.length > 0 && (
        <div className="ficha__lista" style={{ marginTop: "var(--space-4)" }}>
          <div className="ficha__linha ficha__linha--cabecalho">
            <span className="ficha__linha-nome">
              {resultados.length} código(s) · {pendentes.length} a confirmar
            </span>
            {pendentes.length > 0 && (
              <span className="ficha__linha-acoes">
                <Button variant="secondary" size="sm" onClick={ligarTodas}>
                  {pendentes.length === 1
                    ? "Confirmar"
                    : `Confirmar todas (${pendentes.length})`}
                </Button>
              </span>
            )}
          </div>

          {resultados.map((r) => {
            const barrada = jaApadrinhada(r.crianca);
            return (
              <div key={r.codigo} className="ficha__linha">
                <span
                  className="ficha__linha-nome"
                  title={r.crianca ? r.crianca.instituicao : undefined}
                >
                  {r.crianca ? (
                    <>
                      {/* Codigo na frente: e por ele que se procurou, e e ele
                          que amarra a linha ao que estava na planilha. */}
                      <span className="ficha__linha-codigo">{r.crianca.codigo}</span>
                      {r.crianca.nome}, {r.crianca.idade}
                    </>
                  ) : (
                    <span className="celula--vazia">{r.codigo}</span>
                  )}
                </span>

                <span className="ficha__linha-etiquetas">
                  {barrada && (
                    <span
                      className="etiqueta etiqueta--parado"
                      title={`Esta criança já tem padrinho de ${tipo}`}
                    >
                      já apadrinhada
                    </span>
                  )}
                  {!barrada && jaTemOutro(r.crianca) && (
                    <span
                      className="etiqueta etiqueta--neutra"
                      title="Já tem padrinho do outro tipo; este ainda está livre"
                    >
                      já tem {tipo === "cesta" ? "festa" : "cesta"}
                    </span>
                  )}
                  {r.estado === "nao-encontrada" && (
                    <span className="etiqueta etiqueta--parado">não encontrada</span>
                  )}
                  {r.estado === "falhou" && (
                    <span className="etiqueta etiqueta--parado" title={r.erro}>
                      erro na busca
                    </span>
                  )}
                  {r.estado === "apadrinhada" && (
                    <span className="etiqueta etiqueta--ok">apadrinhada</span>
                  )}
                  {r.erro && r.estado === "pendente" && (
                    <span className="etiqueta etiqueta--parado" title={r.erro}>
                      não deu
                    </span>
                  )}
                </span>

                {/* Contorno: o botao cheio da janela e o "Confirmar todas" la
                    em cima. Aqui e o atalho para ligar so esta. */}
                {!barrada && (r.estado === "pendente" || r.estado === "salvando") && (
                  <span className="ficha__linha-acoes">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => ligar(r)}
                      carregando={r.estado === "salvando"}
                    >
                      Confirmar
                    </Button>
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
