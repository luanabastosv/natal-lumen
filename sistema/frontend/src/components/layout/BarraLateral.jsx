import { NavLink } from "react-router-dom";
import { Configuracoes, MenuRecolher } from "../core/icones.jsx";
import { useSessao } from "../../contexts/useSessao.js";
import MenuLateral from "./MenuLateral.jsx";
import { ITEM_ADMIN } from "./menu.js";
import { nomeCurto } from "../../utils/nomes.js";

function iniciais(nome) {
  return nomeCurto(nome)
    .split(" ")
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

/** A barra lateral e a casca inteira da navegacao: marca no topo, destinos no
 *  meio, quem esta logado na base. Nao ha cabecalho no topo da pagina — com 11
 *  destinos, o layout do DS e este. */
export default function BarraLateral({ aoNavegar, recolhida = false, aoAlternar }) {
  const { usuario, edicoes, edicao: edicaoAtual, edicaoAtiva, escolherEdicao, sair } =
    useSessao();

  // A administracao geral escolhe; quem tem vinculo em mais de uma edicao
  // tambem. Os demais so leem.
  const podeTrocar = Boolean(usuario?.admin_geral) || edicoes.length > 1;

  return (
    <div className="lateral">
      <div className="lateral__marca">
        <img
          src="/acesso/images/star-mascot-amarelo.svg"
          alt=""
          className="lateral__mascote"
        />
        <span className="lateral__nome">Natal Lumen</span>
        {/* Recolher a lateral: so no computador (no celular ela ja e uma
            gaveta). Recolhida, ficam os icones dos destinos e a lista ganha a
            largura que o menu ocupava. */}
        <button
          type="button"
          className="lateral__recolher"
          onClick={aoAlternar}
          title={recolhida ? "Abrir o menu" : "Recolher o menu"}
          aria-label={recolhida ? "Abrir o menu" : "Recolher o menu"}
          aria-expanded={!recolhida}
        >
          <MenuRecolher t={18} aberto={!recolhida} />
        </button>
      </div>

      <MenuLateral aoNavegar={aoNavegar} recolhida={recolhida} />

      <div className="lateral__base">
        {/* A edicao ativa vale para o sistema inteiro: escolhida uma vez aqui,
            nenhuma pagina volta a perguntar.

            Quem manda no formato e o usuario, e nao quantas edicoes existem: a
            administracao geral alcanca todas e precisa poder trocar mesmo
            quando so ha uma cadastrada — a lista cresce em cima da tela dela.
            Os demais ficam presos ao vinculo que a administracao deu, entao
            ali a edicao e informacao, nao escolha. */}
        <div className="lateral__edicao-bloco">
          <span className="lateral__edicao-rotulo" id="rotulo-edicao-ativa">
            Edição
          </span>

          {podeTrocar ? (
            <select
              className="lateral__edicao"
              value={edicaoAtiva ?? ""}
              onChange={(e) => escolherEdicao(Number(e.target.value))}
              aria-labelledby="rotulo-edicao-ativa"
              disabled={edicoes.length === 0}
            >
              {edicoes.length === 0 ? (
                <option value="">Nenhuma edição cadastrada</option>
              ) : (
                edicoes.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.cidade} {e.ano}
                  </option>
                ))
              )}
            </select>
          ) : (
            <span className="lateral__edicao-fixa">
              {edicaoAtual ? `${edicaoAtual.cidade} ${edicaoAtual.ano}` : "Sem edição"}
            </span>
          )}
        </div>

        <div className="lateral__usuario">
          <span
            className="lateral__avatar"
            aria-hidden="true"
            title={
              recolhida
                ? `${nomeCurto(usuario?.nome)}${edicaoAtual ? ` · ${edicaoAtual.cidade} ${edicaoAtual.ano}` : ""}`
                : undefined
            }
          >
            {iniciais(usuario?.nome)}
          </span>
          <span className="lateral__usuario-nome" title={usuario?.email}>
            {nomeCurto(usuario?.nome)}
          </span>

          <span className="lateral__acoes">
            {/* Cadastrar cidades e edicoes mora aqui, junto de quem esta
                logado, e nao no menu: e o unico destino que trabalha ACIMA da
                edicao escolhida, e so a administracao geral o enxerga. */}
            {usuario?.admin_geral && (
              <NavLink
                to={ITEM_ADMIN.para}
                onClick={aoNavegar}
                className={({ isActive }) =>
                  `lateral__acao ${isActive ? "lateral__acao--ativo" : ""}`
                }
                title={ITEM_ADMIN.rotulo}
                aria-label={ITEM_ADMIN.rotulo}
              >
                <Configuracoes t={18} />
              </NavLink>
            )}

            {/* Sair e a acao menos importante daqui: icone, sem amarelo — o
                amarelo e do CTA da pagina. */}
            <button
              type="button"
              className="lateral__acao"
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
          </span>
        </div>
      </div>
    </div>
  );
}
