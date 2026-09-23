import { useSessao } from "../../contexts/useSessao.js";

function primeiroNome(nome) {
  return nome?.trim().split(" ")[0] ?? "";
}

export default function CabecalhoSistema({ aoAbrirMenu, menuAberto }) {
  const { usuario, edicaoAtiva, escolherEdicao, sair } = useSessao();

  return (
    <header className="cabecalho">
      <button
        type="button"
        className="cabecalho__menu-botao"
        onClick={aoAbrirMenu}
        aria-label={menuAberto ? "Fechar menu" : "Abrir menu"}
        aria-expanded={menuAberto}
      >
        <span className="cabecalho__hamburguer" aria-hidden="true" />
      </button>

      <div className="cabecalho__marca">
        <img
          src="/acesso/images/star-mascot-outline.svg"
          alt=""
          className="cabecalho__mascote"
        />
        <span className="cabecalho__nome">Natal Lumen</span>
      </div>

      <div className="cabecalho__direita">
        {usuario?.vinculos.length > 1 && (
          <select
            className="cabecalho__edicao"
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
          <span className="cabecalho__edicao-fixa">
            {usuario.vinculos[0].cidade} {usuario.vinculos[0].ano}
          </span>
        )}

        <span className="cabecalho__usuario" title={usuario?.email}>
          {primeiroNome(usuario?.nome)}
        </span>

        <button type="button" className="cabecalho__sair" onClick={sair}>
          Sair
        </button>
      </div>
    </header>
  );
}
