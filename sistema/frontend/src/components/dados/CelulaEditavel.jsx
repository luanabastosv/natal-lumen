import { useEffect, useRef, useState } from "react";

/** Celula de planilha: mostra o valor, e vira campo ao clicar.
 *
 * Enter salva e desce para a celula de baixo; Esc desfaz. E o comportamento
 * que quem vem do Excel espera.
 *
 * Se salvar falha, o que foi digitado FICA na celula, marcado em vermelho ate
 * a pessoa tentar de novo (clicar e Enter) ou desistir (Esc). Antes a celula
 * piscava e voltava ao valor antigo — e quem ja estava na linha de baixo nem
 * via que tinha perdido o que digitou, coisa comum com internet ruim.
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
  // A mensagem da ultima falha, ou null. Enquanto houver, o rascunho e o que
  // a celula mostra: e o que a pessoa quis gravar e ainda nao esta gravado.
  const [falha, definirFalha] = useState(null);
  const campo = useRef(null);

  // Quando o valor vem de fora mudado (a linha foi recarregada), o rascunho
  // acompanha. Ajustado durante o render, e nao por efeito: evita um segundo
  // render so para sincronizar.
  const [valorAnterior, definirValorAnterior] = useState(valor);
  if (valor !== valorAnterior) {
    definirValorAnterior(valor);
    // Com uma falha pendente o rascunho e a unica copia do que foi digitado:
    // recarregar a linha nao pode apaga-lo.
    if (!falha) definirRascunho(valor ?? "");
  }

  useEffect(() => {
    if (editando) campo.current?.focus();
  }, [editando]);

  async function salvar() {
    definirEditando(false);

    const limpo = typeof rascunho === "string" ? rascunho.trim() : rascunho;
    if (String(limpo) === String(valor ?? "")) {
      definirFalha(null);
      return;
    }

    definirSalvando(true);
    try {
      await aoSalvar(limpo);
      definirFalha(null);
    } catch (e) {
      definirFalha(e?.message || "Não foi possível salvar.");
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
      definirFalha(null);
      definirEditando(false);
    }
  }

  const classe = [
    "celula",
    editando && "celula--editando",
    salvando && "celula--salvando",
    falha && "celula--erro",
    !editando && !falha && (valor === null || valor === "") && "celula--vazia",
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

  const atual = falha ? rascunho : valor;
  const mostrado = opcoes
    ? (opcoes.find((o) => String(o.valor ?? "") === String(atual ?? ""))?.rotulo ?? vazio)
    : (atual ?? "") === ""
      ? vazio
      : atual;

  return (
    <button
      type="button"
      className={classe}
      onClick={() => definirEditando(true)}
      onFocus={() => definirEditando(true)}
      style={{ width: largura }}
      title={
        falha
          ? `Não salvou: ${falha} Clique e aperte Enter para tentar de novo, ou Esc para desfazer.`
          : "Clique para editar"
      }
    >
      {salvando ? "..." : mostrado}
    </button>
  );
}
