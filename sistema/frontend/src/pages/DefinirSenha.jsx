import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import Button from "../components/core/Button.jsx";
import { Entrada } from "../components/core/Campo.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { definirSenha as enviarSenha } from "../services/auth.js";
import "./Login.css";

const TAMANHO_MINIMO = 8;

export default function DefinirSenha() {
  const [parametros] = useSearchParams();
  const token = parametros.get("token") ?? "";

  const [senha, definirSenhaCampo] = useState("");
  const [repetida, definirRepetida] = useState("");
  const [erro, definirErro] = useState("");
  const [pronto, definirPronto] = useState(false);
  const [enviando, definirEnviando] = useState(false);

  const naoConfere = repetida.length > 0 && senha !== repetida;
  const podeEnviar = senha.length >= TAMANHO_MINIMO && senha === repetida;

  async function aoEnviar(evento) {
    evento.preventDefault();
    definirErro("");
    definirEnviando(true);

    try {
      await enviarSenha(token, senha);
      definirPronto(true);
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

        {pronto ? (
          <>
            <h1 className="acesso__titulo">Senha definida</h1>
            <p className="acesso__lede">Já pode entrar no sistema com a senha nova.</p>
            <Button as="a" href="/acesso/entrar" larguraTotal>
              Ir para o login
            </Button>
          </>
        ) : !token ? (
          <>
            <h1 className="acesso__titulo">Link incompleto</h1>
            <Mensagem tipo="erro">
              Este endereço não traz o código de acesso. Abra o link exatamente como
              foi enviado, ou peça um novo à coordenação.
            </Mensagem>
            <p className="acesso__rodape">
              <Link to="/entrar">Voltar ao login</Link>
            </p>
          </>
        ) : (
          <>
            <h1 className="acesso__titulo">Definir sua senha</h1>
            <p className="acesso__lede">
              Escolha uma senha com pelo menos {TAMANHO_MINIMO} caracteres. Este link
              só pode ser usado uma vez.
            </p>

            <Mensagem tipo="erro">{erro}</Mensagem>

            <form onSubmit={aoEnviar} noValidate>
              <Entrada
                rotulo="Nova senha"
                tipo="password"
                value={senha}
                onChange={(e) => definirSenhaCampo(e.target.value)}
                autoComplete="new-password"
                dica={`Pelo menos ${TAMANHO_MINIMO} caracteres, e não só números.`}
                required
                disabled={enviando}
              />
              <Entrada
                rotulo="Repita a senha"
                tipo="password"
                value={repetida}
                onChange={(e) => definirRepetida(e.target.value)}
                autoComplete="new-password"
                erro={naoConfere ? "As senhas não são iguais." : ""}
                required
                disabled={enviando}
              />

              <Button
                type="submit"
                larguraTotal
                carregando={enviando}
                disabled={!podeEnviar}
              >
                {enviando ? "Salvando..." : "Definir senha"}
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
