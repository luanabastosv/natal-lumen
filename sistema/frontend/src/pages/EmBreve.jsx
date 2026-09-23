import { useLocation } from "react-router-dom";
import EmptyState from "../components/feedback/EmptyState.jsx";
import { ITENS_MENU } from "../components/layout/menu.js";

/** Espaco reservado das secoes que chegam nas proximas fases. */
export default function EmBreve() {
  const local = useLocation();
  const item = ITENS_MENU.find((i) => i.para === local.pathname);

  return (
    <div>
      <div className="pagina__eyebrow">Em construção</div>
      <h1 className="pagina__titulo">{item?.rotulo ?? "Seção"}</h1>
      <EmptyState
        titulo="Esta parte ainda está sendo construída"
        corpo="A estrutura do sistema já está de pé. Esta seção entra numa das próximas etapas."
      />
    </div>
  );
}
