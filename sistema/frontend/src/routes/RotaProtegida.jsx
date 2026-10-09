import { Navigate, useLocation } from "react-router-dom";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { eCoordenacaoGeral } from "../components/layout/menu.js";

/** Exige sessao e, opcionalmente, permissao.
 *
 * `permissao` exige aquela. `permissoes` exige QUALQUER uma da lista — e a
 * tela que junta assuntos de donos diferentes, como o financeiro, onde cada
 * aba tem a sua e a pessoa entra pela que alcanca.
 *
 * Esconder a rota e conveniencia de navegacao. A porta de verdade e o backend:
 * cada rota da API confere a permissao por conta propria.
 */
export default function RotaProtegida({
  permissao,
  permissoes,
  apenasAdmin = false,
  // So a coordenacao geral do evento (e a administracao geral).
  soCoordenacaoGeral = false,
  children,
}) {
  const { autenticado, carregando, pode, usuario, vinculoAtivo } = useSessao();
  const local = useLocation();

  if (carregando) {
    return <Carregando tela>Verificando sua sessão...</Carregando>;
  }

  if (!autenticado) {
    // Guarda de onde veio, para voltar para ca depois de entrar.
    return <Navigate to="/entrar" replace state={{ de: local.pathname }} />;
  }

  if (apenasAdmin && !usuario?.admin_geral) {
    return (
      <EmptyState
        titulo="Seção da administração geral"
        corpo="Cidades e edições são criadas pela administração geral do projeto."
      />
    );
  }

  if (soCoordenacaoGeral && !eCoordenacaoGeral(usuario, vinculoAtivo)) {
    return (
      <EmptyState
        titulo="Seção da coordenação geral"
        corpo="Esta lista é da coordenação geral do evento."
      />
    );
  }

  const exigidas = permissoes ?? (permissao ? [permissao] : []);

  if (exigidas.length > 0 && !exigidas.some((p) => pode(p))) {
    return (
      <EmptyState
        titulo="Você não tem acesso a esta seção"
        corpo="Se precisa dela para o seu trabalho, fale com a coordenação da sua cidade."
      />
    );
  }

  return children;
}
