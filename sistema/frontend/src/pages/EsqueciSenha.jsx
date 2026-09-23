import { useState } from "react";
import { Link } from "react-router-dom";
import Button from "../components/core/Button.jsx";
import { Entrada } from "../components/core/Campo.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { esqueciSenha } from "../services/auth.js";
import "./Login.css";

export default function EsqueciSenha() {
  const [email, definirEmail] = useState("");
  const [resposta, definirResposta] = useState(null);
  const [erro, definirErro] = useState("");
  const [enviando, definirEnviando] = useState(false);

  async function aoEnviar(evento) {
    evento.preventDefault();
    definirErro("");
    definirEnviando(true);

    try {
      definirResposta(await esqueciSenha(email.trim()));
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

        <h1 className="acesso__titulo">Esqueci minha senha</h1>

        {resposta ? (
          <>
            <Mensagem tipo="sucesso">{resposta.mensagem}</Mensagem>
            {/* Em producao o link vai por email; em desenvolvimento ele volta
                aqui, para dar para testar sem servidor de email. */}
            {resposta.link && (
              <Mensagem tipo="aviso">
                Modo de desenvolvimento — o link seria enviado por email:
                <br />
                <Link to={resposta.link.replace("/acesso", "")}>
                  {resposta.link}
                </Link>
              </Mensagem>
            )}
          </>
        ) : (
          <>
            <p className="acesso__lede">
              Escreva o email da sua conta. Se ela existir, enviamos um link para
              criar uma senha nova.
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
              <Button
                type="submit"
                larguraTotal
                carregando={enviando}
                disabled={!email}
              >
                {enviando ? "Enviando..." : "Enviar link"}
              </Button>
            </form>
          </>
        )}

        <p className="acesso__rodape">
          <Link to="/entrar">Voltar ao login</Link>
        </p>
      </div>
    </div>
  );
}
