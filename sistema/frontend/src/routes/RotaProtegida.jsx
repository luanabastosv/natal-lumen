import { Navigate, useLocation } from "react-router-dom";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import { useSessao } from "../contexts/useSessao.js";

/** Exige sessao e, opcionalmente, uma permissao.
 *
 * Esconder a rota e conveniencia de navegacao. A porta de verdade e o backend:
 * cada rota da API confere a permissao por conta propria.
 */
export default function RotaProtegida({ permissao, children }) {
  const { autenticado, carregando, pode } = useSessao();
  const local = useLocation();

  if (carregando) {
    return <Carregando tela>Verificando sua sessão...</Carregando>;
  }

  if (!autenticado) {
    // Guarda de onde veio, para voltar para ca depois de entrar.
    return <Navigate to="/entrar" replace state={{ de: local.pathname }} />;
  }

  if (permissao && !pode(permissao)) {
    return (
      <EmptyState
        titulo="Você não tem acesso a esta seção"
        corpo="Se precisa dela para o seu trabalho, fale com a coordenação da sua cidade."
      />
    );
  }

  return children;
}
