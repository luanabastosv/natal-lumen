import { NavLink } from "react-router-dom";
import { useSessao } from "../../contexts/useSessao.js";
import { itensVisiveis } from "./menu.js";

export default function MenuLateral({ aoNavegar, recolhida = false }) {
  const { pode, usuario, vinculoAtivo } = useSessao();
  const itens = itensVisiveis(pode, { usuario, vinculoAtivo });

  return (
    <nav className="menu" aria-label="Menu principal">
      {itens.map((item) => (
        <NavLink
          key={item.para}
          to={item.para}
          onClick={aoNavegar}
          className={({ isActive }) =>
            `menu__item ${isActive ? "menu__item--ativo" : ""}`
          }
          /* Na lateral recolhida o rotulo some, e a dica do mouse e o
             aria-label passam a dizer o nome do destino. */
          title={recolhida ? item.rotulo : undefined}
          aria-label={recolhida ? item.rotulo : undefined}
        >
          {item.Icone && <item.Icone t={18} />}
          <span className="menu__rotulo">{item.rotulo}</span>
        </NavLink>
      ))}
    </nav>
  );
}
