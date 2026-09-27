import { useSessao } from "../../contexts/useSessao.js";
import MenuLateral from "./MenuLateral.jsx";

/** "Maria da Silva Souza" -> "Maria Souza": nome e sobrenome, sem os ligadores. */
function nomeCurto(nome) {
  const partes = (nome ?? "").trim().split(/\s+/).filter(Boolean);
  if (partes.length <= 1) return partes[0] ?? "";
  return `${partes[0]} ${partes[partes.length - 1]}`;
}

function iniciais(nome) {
  return nomeCurto(nome)
    .split(" ")
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

/** A barra lateral e a casca inteira da navegacao: marca no topo, destinos no
 *  meio, quem esta logado na base. Nao ha cabecalho no topo da pagina — com 11
 *  destinos, o layout do DS e este. */
export default function BarraLateral({ aoNavegar }) {
  const { usuario, edicaoAtiva, escolherEdicao, sair } = useSessao();

  return (
    <div className="lateral">
      <div className="lateral__marca">
        <img
          src="/acesso/images/star-mascot-amarelo.svg"
          alt=""
          className="lateral__mascote"
        />
        <span className="lateral__nome">Natal Lumen</span>
      </div>

      <MenuLateral aoNavegar={aoNavegar} />

      <div className="lateral__base">
        {usuario?.vinculos.length > 1 && (
          <select
            className="lateral__edicao"
            value={edicaoAtiva ?? ""}
            onChange={(e) => escolherEdicao(Number(e.target.value))}
            aria-label="Edição ativa"
          >
            {usuario.vinculos.map((v) => (
              <option key={v.edicao_id} value={v.edicao_id}>
                {v.cidade} {v.ano}
              </option>
            ))}
          </select>
        )}

        {usuario?.vinculos.length === 1 && (
          <span className="lateral__edicao-fixa">
            {usuario.vinculos[0].cidade} {usuario.vinculos[0].ano}
          </span>
        )}

        <div className="lateral__usuario">
          <span className="lateral__avatar" aria-hidden="true">
            {iniciais(usuario?.nome)}
          </span>
          <span className="lateral__usuario-nome" title={usuario?.email}>
            {nomeCurto(usuario?.nome)}
          </span>

          {/* Sair e a acao menos importante daqui: icone, sem amarelo — o
              amarelo e do CTA da pagina. */}
          <button
            type="button"
            className="lateral__sair"
            onClick={sair}
            title="Sair"
            aria-label="Sair"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
              <path
                d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l-5-5 5-5M5 12h11"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
