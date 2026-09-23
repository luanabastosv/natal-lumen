import { Link } from "react-router-dom";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Button from "../components/core/Button.jsx";

export default function NaoEncontrada() {
  return (
    <EmptyState
      titulo="Página não encontrada"
      corpo="O endereço não existe ou foi movido."
      acao={
        <Link to="/painel">
          <Button variant="ghost">Ir para o painel</Button>
        </Link>
      }
    />
  );
}
