import { useEffect, useRef, useState } from "react";

/** Celula de planilha: mostra o valor, e vira campo ao clicar.
 *
 * Enter salva e desce para a celula de baixo; Esc desfaz. E o comportamento
 * que quem vem do Excel espera.
 */
export default function CelulaEditavel({
  valor,
  aoSalvar,
  tipo = "text",
  opcoes,
  vazio = "—",
  largura,
}) {
  const [editando, definirEditando] = useState(false);
  const [rascunho, definirRascunho] = useState(valor ?? "");
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState(false);
  const campo = useRef(null);

  // Quando o valor vem de fora mudado (a linha foi recarregada), o rascunho
  // acompanha. Ajustado durante o render, e nao por efeito: evita um segundo
  // render so para sincronizar.
  const [valorAnterior, definirValorAnterior] = useState(valor);
  if (valor !== valorAnterior) {
    definirValorAnterior(valor);
    definirRascunho(valor ?? "");
  }

  useEffect(() => {
    if (editando) campo.current?.focus();
  }, [editando]);

  async function salvar() {
    definirEditando(false);

    const limpo = typeof rascunho === "string" ? rascunho.trim() : rascunho;
    if (String(limpo) === String(valor ?? "")) return;

    definirSalvando(true);
    definirErro(false);
    try {
      await aoSalvar(limpo);
    } catch {
      definirErro(true);
      definirRascunho(valor ?? "");
      setTimeout(() => definirErro(false), 2500);
    } finally {
      definirSalvando(false);
    }
  }

  function aoTeclar(evento) {
    if (evento.key === "Enter") {
      evento.preventDefault();
      salvar();
      // Desce para a mesma coluna da linha seguinte.
      const linha = evento.target.closest("tr")?.nextElementSibling;
      const indice = [...evento.target.closest("tr").children].indexOf(
        evento.target.closest("td"),
      );
      linha?.children[indice]?.querySelector(".celula")?.focus();
    }
    if (evento.key === "Escape") {
      definirRascunho(valor ?? "");
      definirEditando(false);
    }
  }

  const classe = [
    "celula",
    editando && "celula--editando",
    salvando && "celula--salvando",
    erro && "celula--erro",
    !editando && (valor === null || valor === "") && "celula--vazia",
  ]
    .filter(Boolean)
    .join(" ");

  if (editando && opcoes) {
    return (
      <select
        ref={campo}
        className={classe}
        value={rascunho ?? ""}
        onChange={(e) => definirRascunho(e.target.value)}
        onBlur={salvar}
        onKeyDown={aoTeclar}
        style={{ width: largura }}
      >
        {opcoes.map((o) => (
          <option key={String(o.valor)} value={o.valor ?? ""}>
            {o.rotulo}
          </option>
        ))}
      </select>
    );
  }

  if (editando) {
    return (
      <input
        ref={campo}
        type={tipo}
        className={classe}
        value={rascunho}
        onChange={(e) => definirRascunho(e.target.value)}
        onBlur={salvar}
        onKeyDown={aoTeclar}
        style={{ width: largura }}
      />
    );
  }

  const mostrado = opcoes
    ? (opcoes.find((o) => String(o.valor ?? "") === String(valor ?? ""))?.rotulo ?? vazio)
    : (valor ?? "") === ""
      ? vazio
      : valor;

  return (
    <button
      type="button"
      className={classe}
      onClick={() => definirEditando(true)}
      onFocus={() => definirEditando(true)}
      style={{ width: largura }}
      title="Clique para editar"
    >
      {salvando ? "..." : mostrado}
    </button>
  );
}
