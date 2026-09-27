import { useId } from "react";

// O site nao tem nenhum formulario, entao nao havia padrao de campo para
// reaproveitar. Este segue os tokens e combina com os botoes: borda de 2px,
// raio md e foco em navy.

export function Campo({ rotulo, dica, erro, classe = "", children }) {
  return (
    <label className={`campo ${classe}`.trim()}>
      {rotulo && <span className="campo__rotulo">{rotulo}</span>}
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
export function Entrada({ rotulo, dica, erro, classe, tipo = "text", sugestoes, ...resto }) {
  const id = useId();
  const listaId = `${id}-sugestoes`;
  return (
    <Campo rotulo={rotulo} dica={dica} erro={erro} classe={classe}>
      <input
        id={id}
        type={tipo}
        className={`campo__controle ${erro ? "campo__controle--erro" : ""}`}
        aria-invalid={erro ? true : undefined}
        list={sugestoes?.length ? listaId : undefined}
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

export function Selecao({ rotulo, dica, erro, classe, children, ...resto }) {
  const id = useId();
  return (
    <Campo rotulo={rotulo} dica={dica} erro={erro} classe={classe}>
      <select
        id={id}
        className={`campo__controle campo__controle--selecao ${erro ? "campo__controle--erro" : ""}`}
        aria-invalid={erro ? true : undefined}
        {...resto}
      >
        {children}
      </select>
    </Campo>
  );
}
