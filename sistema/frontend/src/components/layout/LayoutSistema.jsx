import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import ConviteDeOracao from "../feedback/ConviteDeOracao.jsx";
import BarraLateral from "./BarraLateral.jsx";
import BarraMobile from "./BarraMobile.jsx";
import RodapeSistema from "./RodapeSistema.jsx";

// A preferencia de lateral recolhida e da pessoa, e nao da tela: lembrada
// neste navegador, e so isso. Se o armazenamento falhar (janela anonima,
// bloqueio), a lateral simplesmente abre aberta.
const CHAVE_RECOLHIDA = "natal-lumen:lateral-recolhida";

function lerRecolhida() {
  try {
    return localStorage.getItem(CHAVE_RECOLHIDA) === "1";
  } catch {
    return false;
  }
}

export default function LayoutSistema() {
  const [menuAberto, definirMenuAberto] = useState(false);
  const [recolhida, definirRecolhida] = useState(lerRecolhida);

  function alternarRecolhida() {
    definirRecolhida((atual) => {
      const nova = !atual;
      try {
        localStorage.setItem(CHAVE_RECOLHIDA, nova ? "1" : "0");
      } catch {
        // Sem armazenamento, vale so ate recarregar.
      }
      return nova;
    });
  }
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
    <div className={`layout ${recolhida ? "layout--recolhida" : ""}`}>
      {/* Fica aqui, e nao numa pagina: no primeiro acesso do dia a pessoa entra
          por onde o trabalho dela pede, e muita gente nunca passa pelo painel.
          Ele mesmo decide se aparece. */}
      <ConviteDeOracao />

      <BarraMobile
        menuAberto={menuAberto}
        aoAbrirMenu={() => definirMenuAberto((aberto) => !aberto)}
      />

      <aside className={`layout__lateral ${menuAberto ? "layout__lateral--aberta" : ""}`}>
        <BarraLateral
          aoNavegar={() => definirMenuAberto(false)}
          recolhida={recolhida}
          aoAlternar={alternarRecolhida}
        />
      </aside>

      {menuAberto && (
        <button
          type="button"
          className="layout__fundo"
          aria-label="Fechar menu"
          onClick={() => definirMenuAberto(false)}
        />
      )}

      <div className="layout__coluna">
        <main className="layout__conteudo">
          <Outlet />
        </main>
        <RodapeSistema />
      </div>
    </div>
  );
}
