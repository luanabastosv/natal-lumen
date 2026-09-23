import { NavLink } from "react-router-dom";
import { useSessao } from "../../contexts/useSessao.js";
import { itensVisiveis } from "./menu.js";

export default function MenuLateral({ aoNavegar }) {
  const { pode, usuario } = useSessao();
  const itens = itensVisiveis(pode, Boolean(usuario?.admin_geral));

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
        >
          {item.rotulo}
        </NavLink>
      ))}
    </nav>
  );
}
