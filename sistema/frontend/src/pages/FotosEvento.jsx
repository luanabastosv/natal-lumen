import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { useParams } from "react-router-dom";
import { cadastrarVisitante, conferirQrCode } from "../services/visitantes.js";
import "./FotosEvento.css";

const MASCOTE = "/acesso/images/mascote-festa.png";
const dorme = (ms) => new Promise((r) => setTimeout(r, ms));

function mascararCelular(valor) {
  const d = valor.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d;
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, d.length - 4)}-${d.slice(-4)}`;
}

/** A pagina do QR Code da pulseira: a Estrelinha pede nome e celular e
 *  entrega o link das fotos do dia.
 *
 * Fora da sessao — quem abre e o visitante, no celular. Uma tela so, sem
 * rolagem: a fala atual da Estrelinha e, quando ela pergunta, a caixa de
 * resposta. A altura acompanha a area visivel (visualViewport), para a
 * pergunta continuar a vista com o teclado aberto.
 *
 * O teclado: a caixa aparece com a pergunta do nome e ganha o foco (no
 * Android o teclado sobe; o Safari do iPhone so abre com um toque, e a caixa
 * pisca ate la). Do nome para o celular o foco muda dentro do proprio envio,
 * entao o teclado nao fecha. Ele so fecha no fim, com o botao das fotos.
 */
export default function FotosEvento() {
  const { codigo } = useParams();
  const [fase, definirFase] = useState("inicio"); // inicio | conversa | fim | invalido
  const [falas, definirFalas] = useState([]);
  const [digitando, definirDigitando] = useState(false);
  const [passo, definirPasso] = useState(null); // null | nome | celular
  const [nome, definirNome] = useState("");
  const [celular, definirCelular] = useState("");
  const [link, definirLink] = useState(undefined);
  const [teclado, definirTeclado] = useState(false);
  const ocupada = useRef(true);
  const nomeRef = useRef(null);
  const celRef = useRef(null);
  const telaRef = useRef(null);

  // O codigo pode ser de um QR antigo ou digitado errado.
  useEffect(() => {
    conferirQrCode(codigo).catch((e) => {
      if (e.status === 404) definirFase("invalido");
    });
  }, [codigo]);

  // A tela do tamanho da area visivel: com o teclado aberto, ela encolhe.
  useEffect(() => {
    const vv = window.visualViewport;
    function ajusta() {
      const h = vv ? vv.height : window.innerHeight;
      document.documentElement.style.setProperty("--fotos-vh", `${h}px`);
      if (telaRef.current) telaRef.current.style.top = `${vv ? vv.offsetTop : 0}px`;
      definirTeclado(h < window.innerHeight * 0.78 || h < 520);
    }
    ajusta();
    vv?.addEventListener("resize", ajusta);
    vv?.addEventListener("scroll", ajusta);
    window.addEventListener("resize", ajusta);
    document.body.classList.add("fotos-corpo");
    return () => {
      vv?.removeEventListener("resize", ajusta);
      vv?.removeEventListener("scroll", ajusta);
      window.removeEventListener("resize", ajusta);
      document.body.classList.remove("fotos-corpo");
    };
  }, []);

  async function fala(...textos) {
    for (const t of textos) {
      definirDigitando(true);
      await dorme(Math.min(450 + t.length * 18, 1300));
      definirDigitando(false);
      definirFalas((f) => [...f, t]);
      await dorme(220);
    }
  }

  async function limpa() {
    definirFalas([]);
    await dorme(180);
  }

  async function comecar() {
    definirFase("conversa");
    await fala("Oi! Eu sou a Estrelinha.", "Pra liberar suas fotos, só preciso de duas coisinhas.");
    await dorme(700);
    await limpa();
    await fala("Qual é o seu nome?");
    flushSync(() => definirPasso("nome"));
    ocupada.current = false;
    nomeRef.current?.focus({ preventScroll: true });
  }

  async function enviar(e) {
    e.preventDefault();
    if (ocupada.current) return;

    if (passo === "nome") {
      const v = nome.trim().replace(/\s+/g, " ");
      if (v.length < 2) {
        ocupada.current = true;
        await limpa();
        await fala("Me diz seu nome pra eu te chamar direitinho?");
        ocupada.current = false;
        return;
      }
      // Troca de campo AQUI, dentro do envio: e o que mantem o teclado aberto.
      // flushSync: a caixa do celular precisa existir na tela ANTES do foco.
      flushSync(() => definirPasso("celular"));
      celRef.current?.focus({ preventScroll: true });
      ocupada.current = true;
      await limpa();
      await fala(`Prazer, ${v.split(" ")[0]}!`, "Agora me passa seu celular com DDD?");
      ocupada.current = false;
      return;
    }

    const digitos = celular.replace(/\D/g, "");
    if (digitos.length !== 10 && digitos.length !== 11) {
      ocupada.current = true;
      await limpa();
      await fala("Confere o número com o DDD pra mim?");
      ocupada.current = false;
      return;
    }

    ocupada.current = true;
    celRef.current?.blur();
    definirPasso(null);
    await limpa();
    let resposta;
    try {
      resposta = await cadastrarVisitante(codigo, { nome, celular });
    } catch {
      await fala("Ops, a internet falhou aqui. Tenta enviar de novo?");
      definirPasso("celular");
      ocupada.current = false;
      return;
    }
    definirLink(resposta.link_fotos);
    const primeiro = nome.trim().split(/\s+/)[0];
    if (resposta.link_fotos) {
      await fala(`Prontinho, ${primeiro}! Obrigada por ter vindo ao Natal Lumen.`, "Suas fotos estão aqui:");
    } else {
      await fala(
        `Prontinho, ${primeiro}! Obrigada por ter vindo ao Natal Lumen.`,
        "As fotos ainda estão sendo preparadas. Volta por este mesmo QR Code daqui a uns dias que elas vão estar aqui.",
      );
    }
    definirFase("fim");
  }

  // A barra anda a cada resposta aceita: 0 no nome, 1 no celular, 2 no fim.
  const respondidas = fase === "fim" ? 2 : passo === "celular" ? 1 : 0;
  const rotuloProgresso =
    fase === "fim"
      ? "Prontinho!"
      : passo === "celular"
        ? "Pergunta 2 de 2 · última!"
        : passo === "nome"
          ? "Pergunta 1 de 2"
          : "São só 2 perguntas";

  if (fase === "invalido") {
    return (
      <div className="fotos">
        <section className="fotos__inicio">
          <img src={MASCOTE} alt="" className="fotos__mascote" />
          <p className="fotos__aviso">
            Esse QR Code não abriu nenhuma galeria. Confere se leu o da sua pulseira?
          </p>
        </section>
      </div>
    );
  }

  if (fase === "inicio") {
    return (
      <div className="fotos">
        <section className="fotos__inicio">
          <img src={MASCOTE} alt="" className="fotos__mascote fotos__mascote--pula" />
          <h1 className="fotos__marca">natal lumen</h1>
          <button type="button" className="fotos__cta" onClick={comecar}>
            Quero acessar minhas fotos
          </button>
          <p className="fotos__rapido">São só 2 perguntas rapidinhas.</p>
        </section>
      </div>
    );
  }

  return (
    <div className={`fotos__chat ${teclado ? "fotos__chat--teclado" : ""}`} ref={telaRef}>
      {/* No topo, para continuar a vista com o teclado aberto: quem sabe que
          sao so duas perguntas responde ate o fim. */}
      <div
        className="fotos__progresso"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={2}
        aria-valuenow={respondidas}
        aria-label="Perguntas respondidas"
      >
        <div className="fotos__progresso-texto">
          <span>{rotuloProgresso}</span>
          <span>{respondidas}/2</span>
        </div>
        <div className="fotos__progresso-trilho">
          <div className="fotos__progresso-barra" style={{ width: `${(respondidas / 2) * 100}%` }} />
        </div>
      </div>
      <div className="fotos__palco">
        <img src={MASCOTE} alt="Estrelinha" className="fotos__estrela" />
        <div className="fotos__falas" aria-live="polite">
          {falas.map((t, i) => (
            <div key={`${i}-${t}`} className="fotos__balao">
              {t}
            </div>
          ))}
          {digitando && (
            <div className="fotos__balao fotos__balao--digitando" aria-label="Estrelinha digitando">
              <i />
              <i />
              <i />
            </div>
          )}
        </div>
      </div>

      <div className="fotos__base">
        {fase === "conversa" && (
          <>
            <form
              className={`fotos__campo ${passo ? "" : "fotos__campo--oculto"}`}
              onSubmit={enviar}
            >
              <input
                ref={nomeRef}
                hidden={passo !== "nome"}
                aria-label="Seu nome"
                type="text"
                autoComplete="name"
                autoCapitalize="words"
                enterKeyHint="next"
                placeholder="Seu nome"
                maxLength={160}
                value={nome}
                onChange={(e) => definirNome(e.target.value)}
              />
              <input
                ref={celRef}
                hidden={passo !== "celular"}
                aria-label="Seu celular com DDD"
                type="tel"
                inputMode="numeric"
                autoComplete="tel-national"
                enterKeyHint="send"
                placeholder="(85) 9 0000-0000"
                value={celular}
                onChange={(e) => definirCelular(mascararCelular(e.target.value))}
              />
              <button
                type="submit"
                className="fotos__enviar"
                aria-label="Enviar"
                // O botao nao rouba o foco da caixa: o teclado fica aberto.
                onPointerDown={(e) => e.preventDefault()}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M5 12h13M13 6l6 6-6 6" />
                </svg>
              </button>
            </form>
            <p className="fotos__nota">
              {passo === "celular" ? "Seus dados ficam só com o Natal Lumen." : ""}
            </p>
          </>
        )}
        {fase === "fim" && link && (
          <a className="fotos__cta fotos__cta--largo" href={link} rel="noopener">
            Ver minhas fotos
          </a>
        )}
      </div>
    </div>
  );
}
