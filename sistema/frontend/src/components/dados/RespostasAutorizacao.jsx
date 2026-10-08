import { useId } from "react";
import { PERGUNTAS, RESPOSTAS_PADRAO } from "./autorizacao.js";

/** As tres perguntas que o monitor responde olhando a foto da autorizacao.
 *
 * Mora na conferencia, ao lado da foto, e nao numa tela depois: e com a
 * autorizacao na frente que se le o que o responsavel escreveu. As tres vem
 * marcadas "Nao"; o "qual" e obrigatorio quando a resposta vira sim — o
 * servidor cobra a mesma regra (ver schemas/autorizacoes.py).
 */

function Pergunta({ pergunta, valor, qual, aoMudar }) {
  const id = useId();
  return (
    <div className="pergunta">
      <span className="pergunta__texto" id={id}>
        {pergunta}
      </span>
      {/* Dois botoes, Sim e Nao, com a resposta escrita no botao marcado. */}
      <div className="sim-nao" role="radiogroup" aria-labelledby={id}>
        {[
          [true, "Sim"],
          [false, "Não"],
        ].map(([v, rotulo]) => (
          <button
            key={rotulo}
            type="button"
            role="radio"
            aria-checked={valor === v}
            className={`sim-nao__opcao ${valor === v ? "sim-nao__opcao--ativa" : ""}`}
            onClick={() => aoMudar({ sim: v })}
          >
            {rotulo}
          </button>
        ))}
      </div>
      {valor === true && (
        <input
          className="campo__controle pergunta__qual"
          placeholder="Qual?"
          aria-label={`${pergunta} Qual?`}
          value={qual}
          onChange={(e) => aoMudar({ qual: e.target.value })}
          // Abrir o campo e ja poder escrever: quem marcou sim vai escrever.
          autoFocus
        />
      )}
    </div>
  );
}

export default function RespostasAutorizacao({ respostas, aoMudar }) {
  const r = respostas ?? RESPOSTAS_PADRAO;
  return (
    <div className="respostas-autorizacao">
      {PERGUNTAS.map((p) => (
        <Pergunta
          key={p.sim}
          pergunta={p.pergunta}
          valor={r[p.sim]}
          qual={r[p.qual]}
          aoMudar={({ sim, qual }) =>
            aoMudar({
              ...r,
              ...(sim !== undefined && { [p.sim]: sim }),
              ...(qual !== undefined && { [p.qual]: qual }),
            })
          }
        />
      ))}
    </div>
  );
}
