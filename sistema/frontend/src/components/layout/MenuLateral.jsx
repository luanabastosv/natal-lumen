import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { ChevronDireita } from "../core/icones.jsx";
import { useSessao } from "../../contexts/useSessao.js";
import { menuVisivel } from "./menu.js";

function Destino({ item, aoNavegar, recolhida, sub = false }) {
  const rotulo = sub ? (item.rotuloMenu ?? item.rotulo) : item.rotulo;
  return (
    <NavLink
      to={item.para}
      onClick={aoNavegar}
      className={({ isActive }) =>
        `menu__item ${sub ? "menu__item--sub" : ""} ${isActive ? "menu__item--ativo" : ""}`
      }
      /* Na lateral recolhida o rotulo some, e a dica do mouse e o
         aria-label passam a dizer o nome do destino. */
      title={recolhida ? rotulo : undefined}
      aria-label={recolhida ? rotulo : undefined}
    >
      {/* No grupo aberto o subitem vai sem icone, recuado: o icone e o do
          grupo. Recolhida, cada um precisa do seu — e so o que se ve. */}
      {item.Icone && (!sub || recolhida) && <item.Icone t={18} />}
      <span className="menu__rotulo">{rotulo}</span>
    </NavLink>
  );
}

/** Um grupo da lateral (Criancas, Configuracoes): abre e fecha, e nasce
 *  aberto quando a pagina atual e um dos destinos dele. */
function Grupo({ grupo, aoNavegar, recolhida }) {
  const { pathname } = useLocation();
  const dentro = grupo.itens.some((i) => pathname.startsWith(i.para));
  const [aberto, definirAberto] = useState(dentro);
  const [ultimoDentro, definirUltimoDentro] = useState(dentro);
  // Navegou para dentro do grupo por outro caminho (um link no painel): abre.
  if (dentro !== ultimoDentro) {
    definirUltimoDentro(dentro);
    if (dentro) definirAberto(true);
  }

  // Recolhida nao ha onde mostrar um titulo de grupo: os destinos aparecem
  // soltos, cada um com o seu icone.
  if (recolhida) {
    return grupo.itens.map((item) => (
      <Destino key={item.para} item={item} aoNavegar={aoNavegar} recolhida sub />
    ));
  }

  return (
    <div className="menu__grupo">
      <button
        type="button"
        className={`menu__item menu__grupo-titulo ${dentro && !aberto ? "menu__item--ativo" : ""}`}
        aria-expanded={aberto}
        onClick={() => definirAberto((a) => !a)}
      >
        <grupo.Icone t={18} />
        <span className="menu__rotulo">{grupo.grupo}</span>
        <span className={`menu__seta ${aberto ? "menu__seta--aberta" : ""}`} aria-hidden="true">
          <ChevronDireita t={14} />
        </span>
      </button>
      {aberto && (
        <div className="menu__subitens">
          {grupo.itens.map((item) => (
            <Destino key={item.para} item={item} aoNavegar={aoNavegar} recolhida={false} sub />
          ))}
        </div>
      )}
    </div>
  );
}

export default function MenuLateral({ aoNavegar, recolhida = false }) {
  const { pode, usuario, vinculoAtivo } = useSessao();
  const entradas = menuVisivel(pode, { usuario, vinculoAtivo });

  return (
    <nav className="menu" aria-label="Menu principal">
      {entradas.map((e) =>
        e.grupo ? (
          <Grupo key={e.grupo} grupo={e} aoNavegar={aoNavegar} recolhida={recolhida} />
        ) : (
          <Destino key={e.para} item={e} aoNavegar={aoNavegar} recolhida={recolhida} />
        ),
      )}
    </nav>
  );
}
