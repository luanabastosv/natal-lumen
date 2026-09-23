import { useSessao } from "../contexts/useSessao.js";
import { itensVisiveis } from "../components/layout/menu.js";
import { Link } from "react-router-dom";
import EmptyState from "../components/feedback/EmptyState.jsx";

function primeiroNome(nome) {
  return nome?.trim().split(" ")[0] ?? "";
}

export default function Painel() {
  const { usuario, pode, vinculoAtivo } = useSessao();

  // O proprio painel ja esta aberto: nao faz sentido apontar para ele.
  const atalhos = itensVisiveis(pode, Boolean(usuario?.admin_geral)).filter(
    (i) => i.para !== "/painel",
  );

  return (
    <div>
      <div className="pagina__eyebrow">
        {vinculoAtivo
          ? `${vinculoAtivo.cidade} ${vinculoAtivo.ano} · ${vinculoAtivo.perfil}`
          : usuario?.admin_geral
            ? "Administração geral"
            : "Sem edição vinculada"}
      </div>
      <h1 className="pagina__titulo">Olá, {primeiroNome(usuario?.nome)}</h1>

      {!vinculoAtivo && !usuario?.admin_geral ? (
        <EmptyState
          titulo="Você ainda não está numa edição"
          corpo="Sua conta existe, mas a coordenação ainda não a vinculou a uma edição. Assim que isso acontecer, o menu aparece aqui."
        />
      ) : (
        <>
          <p className="pagina__lede">
            Escolha por onde começar. O menu à esquerda mostra apenas o que o seu
            perfil alcança.
          </p>

          <div className="atalhos">
            {atalhos.map((item) => (
              <Link key={item.para} to={item.para} className="atalho">
                <span className="atalho__rotulo">{item.rotulo}</span>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
