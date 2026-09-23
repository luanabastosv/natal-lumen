import { useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import Button from "../components/core/Button.jsx";
import { Entrada } from "../components/core/Campo.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import "./Login.css";

export default function Login() {
  const { autenticado, entrar } = useSessao();
  const local = useLocation();

  const [email, definirEmail] = useState("");
  const [senha, definirSenha] = useState("");
  const [erro, definirErro] = useState("");
  const [enviando, definirEnviando] = useState(false);

  if (autenticado) {
    // Volta para a pagina que a pessoa tentou abrir antes de entrar.
    return <Navigate to={local.state?.de ?? "/painel"} replace />;
  }

  async function aoEnviar(evento) {
    evento.preventDefault();
    definirErro("");
    definirEnviando(true);

    try {
      await entrar(email.trim(), senha);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirEnviando(false);
    }
  }

  return (
    <div className="acesso">
      <div className="acesso__cartao">
        <div className="acesso__marca">
          <img
            src="/acesso/images/star-mascot-outline.svg"
            alt=""
            className="acesso__mascote"
          />
          <span className="acesso__nome">Natal Lumen</span>
        </div>

        <h1 className="acesso__titulo">Entrar no sistema</h1>
        <p className="acesso__lede">
          Acesso restrito à equipe. Se ainda não tem conta, fale com a coordenação da
          sua cidade.
        </p>

        <Mensagem tipo="erro">{erro}</Mensagem>

        <form onSubmit={aoEnviar} noValidate>
          <Entrada
            rotulo="Email"
            tipo="email"
            value={email}
            onChange={(e) => definirEmail(e.target.value)}
            autoComplete="username"
            required
            disabled={enviando}
          />
          <Entrada
            rotulo="Senha"
            tipo="password"
            value={senha}
            onChange={(e) => definirSenha(e.target.value)}
            autoComplete="current-password"
            required
            disabled={enviando}
          />

          <Button
            type="submit"
            larguraTotal
            carregando={enviando}
            disabled={!email || !senha}
          >
            {enviando ? "Entrando..." : "Entrar"}
          </Button>
        </form>

        <p className="acesso__rodape">
          <Link to="/esqueci-senha">Esqueci minha senha</Link>
        </p>
      </div>
    </div>
  );
}
