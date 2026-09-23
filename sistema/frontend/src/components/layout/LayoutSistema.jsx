import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import CabecalhoSistema from "./CabecalhoSistema.jsx";
import MenuLateral from "./MenuLateral.jsx";
import RodapeSistema from "./RodapeSistema.jsx";

export default function LayoutSistema() {
  const [menuAberto, definirMenuAberto] = useState(false);
  const local = useLocation();

  // Trocar de pagina fecha a gaveta no celular. Ajustado durante o render, e
  // nao por efeito: evita um segundo render so para fechar o menu.
  const [ultimoCaminho, definirUltimoCaminho] = useState(local.pathname);
  if (local.pathname !== ultimoCaminho) {
    definirUltimoCaminho(local.pathname);
    definirMenuAberto(false);
  }

  // Esc fecha a gaveta.
  useEffect(() => {
    if (!menuAberto) return;

    const aoTeclar = (e) => {
      if (e.key === "Escape") definirMenuAberto(false);
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [menuAberto]);

  return (
    <div className="layout">
      <CabecalhoSistema
        menuAberto={menuAberto}
        aoAbrirMenu={() => definirMenuAberto((aberto) => !aberto)}
      />

      <div className="layout__corpo">
        <aside className={`layout__menu ${menuAberto ? "layout__menu--aberto" : ""}`}>
          <MenuLateral aoNavegar={() => definirMenuAberto(false)} />
        </aside>

        {menuAberto && (
          <button
            type="button"
            className="layout__fundo"
            aria-label="Fechar menu"
            onClick={() => definirMenuAberto(false)}
          />
        )}

        <main className="layout__conteudo">
          <Outlet />
        </main>
      </div>

      <RodapeSistema />
    </div>
  );
}
