import { useId } from "react";

// O site nao tem nenhum formulario, entao nao havia padrao de campo para
// reaproveitar. Este segue os tokens e combina com os botoes: borda de 2px,
// raio md e foco em navy.

/* `obrigatorio` poe o asterisco vermelho no rotulo E o `required` no
   controle, juntos: assim o asterisco e a validacao do navegador nunca dizem
   coisas diferentes. E opcional de proposito — o login, por exemplo, usa so
   `required`, e um asterisco em "Senha" seria ruido. O asterisco e so visual:
   quem usa leitor de tela ja ouve "obrigatorio" pelo `required`. */
export function Campo({ rotulo, dica, erro, classe = "", obrigatorio = false, children }) {
  return (
    <label className={`campo ${classe}`.trim()}>
      {rotulo && (
        <span className="campo__rotulo">
          {rotulo}
          {obrigatorio && (
            <span className="campo__obrigatorio" aria-hidden="true">
              *
            </span>
          )}
        </span>
      )}
      {children}
      {erro ? (
        <span className="campo__erro">{erro}</span>
      ) : (
        dica && <span className="campo__dica">{dica}</span>
      )}
    </label>
  );
}

/** Campo de texto. Com `sugestoes`, continua aceitando qualquer valor: a lista
 *  e um atalho para o que ja existe, nao um seletor — o primeiro grupo de uma
 *  cidade precisa poder ser escrito do zero.
 */
export function Entrada({
  rotulo,
  dica,
  erro,
  classe,
  tipo = "text",
  sugestoes,
  obrigatorio = false,
  ...resto
}) {
  const id = useId();
  const listaId = `${id}-sugestoes`;
  return (
    <Campo rotulo={rotulo} dica={dica} erro={erro} classe={classe} obrigatorio={obrigatorio}>
      <input
        id={id}
        type={tipo}
        className={`campo__controle ${erro ? "campo__controle--erro" : ""}`}
        aria-invalid={erro ? true : undefined}
        list={sugestoes?.length ? listaId : undefined}
        required={obrigatorio || undefined}
        {...resto}
      />
      {sugestoes?.length > 0 && (
        <datalist id={listaId}>
          {sugestoes.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      )}
    </Campo>
  );
}

/** Caixa de texto de varias linhas.
 *
 * Existe para o que e escrito em frase, e nao em palavra: a observacao de um
 * pagamento ("pagou 200 e pediu para descontar da festa da irma") nao cabe numa
 * linha de campo, e num `input` a pessoa perde de vista o comeco do que
 * escreveu. A altura vem de `linhas`, e nao do conteudo: um campo que estica
 * empurra o botao de salvar para baixo enquanto se digita.
 */
export function AreaTexto({ rotulo, dica, erro, classe, linhas = 3, obrigatorio = false, ...resto }) {
  const id = useId();
  return (
    <Campo rotulo={rotulo} dica={dica} erro={erro} classe={classe} obrigatorio={obrigatorio}>
      <textarea
        id={id}
        rows={linhas}
        className={`campo__controle ${erro ? "campo__controle--erro" : ""}`}
        aria-invalid={erro ? true : undefined}
        required={obrigatorio || undefined}
        {...resto}
      />
    </Campo>
  );
}

export function Selecao({ rotulo, dica, erro, classe, children, obrigatorio = false, ...resto }) {
  const id = useId();
  return (
    <Campo rotulo={rotulo} dica={dica} erro={erro} classe={classe} obrigatorio={obrigatorio}>
      <select
        id={id}
        className={`campo__controle campo__controle--selecao ${erro ? "campo__controle--erro" : ""}`}
        aria-invalid={erro ? true : undefined}
        required={obrigatorio || undefined}
        {...resto}
      >
        {children}
      </select>
    </Campo>
  );
}
