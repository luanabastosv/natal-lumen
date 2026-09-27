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

export function Entrada({ rotulo, dica, erro, classe, tipo = "text", ...resto }) {
  const id = useId();
  return (
    <Campo rotulo={rotulo} dica={dica} erro={erro} classe={classe}>
      <input
        id={id}
        type={tipo}
        className={`campo__controle ${erro ? "campo__controle--erro" : ""}`}
        aria-invalid={erro ? true : undefined}
        {...resto}
      />
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
