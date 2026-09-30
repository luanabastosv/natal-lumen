import { useRef, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import { Entrada } from "../components/core/Campo.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { fazerCheckin } from "../services/logistica.js";
import EtiquetaDia from "../components/core/EtiquetaDia.jsx";
import { formatarDataHora } from "../utils/dinheiro.js";

export default function Checkin() {
  // A edicao vem da lateral: e a mesma para o sistema inteiro.
  const { edicaoAtiva } = useSessao();

  const [codigo, definirCodigo] = useState("");
  const [resultado, definirResultado] = useState(null);
  const [historico, definirHistorico] = useState([]);
  const [erro, definirErro] = useState("");
  const [enviando, definirEnviando] = useState(false);

  const campoCodigo = useRef(null);

  async function registrar(evento) {
    evento.preventDefault();
    definirErro("");
    definirEnviando(true);

    // O QR do crachá traz "edicao:codigo"; digitado, vem só o código.
    const lido = codigo.trim();
    const soCodigo = lido.includes(":") ? lido.split(":").pop() : lido;

    try {
      const entrada = await fazerCheckin(soCodigo, Number(edicaoAtiva));
      definirResultado(entrada);
      definirHistorico((h) => [entrada, ...h].slice(0, 15));
      definirCodigo("");
    } catch (e) {
      definirErro(e.message);
      definirResultado(null);
    } finally {
      definirEnviando(false);
      // Devolve o foco para o campo: na porta, um check-in vem atrás do outro.
      campoCodigo.current?.focus();
    }
  }

  return (
    <div>
      {/* Abertura de dominio: a cena da area a direita do titulo. Uma por
          pagina, e so na tela que abre a area — nao se repete la dentro. */}
      <div className="abertura-dominio">
        <div>
          <div className="pagina__eyebrow">Dia do evento</div>
          <h1 className="pagina__titulo">Check-in</h1>
          <Rabisco className="pagina__onda" />
          <p className="pagina__lede">
            Leia o QR do crachá ou digite o código. O check-in nunca é recusado — o que
            estiver estranho aparece como aviso.
          </p>
        </div>
        <img className="abertura-dominio__cena" src="/acesso/images/cena-onibus.png" alt="" />
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      <form className="painel" onSubmit={registrar}>
        <div className="linha-campos">
          <Entrada
            rotulo="Código da criança"
            value={codigo}
            onChange={(e) => definirCodigo(e.target.value)}
            ref={campoCodigo}
            autoFocus
            dica="O leitor de QR digita sozinho e confirma."
          />
        </div>
        <Button type="submit" carregando={enviando} disabled={!codigo.trim() || !edicaoAtiva}>
          Registrar entrada
        </Button>
      </form>

      {resultado && (
        <div className={`painel ${resultado.avisos.length ? "painel--destaque" : ""}`}>
          <h2 className="painel__titulo">
            {resultado.nome}, {resultado.idade} anos
          </h2>
          <p style={{ margin: "0 0 var(--space-4)", fontSize: "var(--size-body-sm)" }}>
            {resultado.instituicao}
            {resultado.dia_evento && (
              <>
                {" · "}
                <EtiquetaDia
                  data={resultado.dia_evento}
                  descricao={resultado.dia_evento_descricao}
                />
              </>
            )}
            {" · "}
            <span className={`etiqueta etiqueta--${resultado.kit_status === "entregue" ? "ok" : "espera"}`}>
              kit {resultado.kit_status}
            </span>
          </p>

          {resultado.avisos.length === 0 ? (
            <Mensagem tipo="sucesso">Tudo certo. Pode entrar!</Mensagem>
          ) : (
            <Mensagem tipo="aviso">
              <strong>Atenção:</strong>
              <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                {resultado.avisos.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </Mensagem>
          )}
        </div>
      )}

      {historico.length > 0 && (
        <>
          <h2 className="painel__titulo">Últimas entradas</h2>
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Criança</th>
                  {/* No celular a instituicao desce para debaixo do nome em vez
                      de virar coluna: sao quatro colunas e a tela do check-in e
                      quase sempre um celular na porta do onibus. Uma janela
                      para esconder um dado so custaria um toque por linha numa
                      lista que se le de relance. */}
                  <th className="so-no-monitor">Instituição</th>
                  <th>Hora</th>
                  <th>Avisos</th>
                </tr>
              </thead>
              <tbody>
                {historico.map((h, i) => (
                  <tr key={`${h.crianca_id}-${i}`}>
                    <td>
                      {h.nome}
                      <span className="so-no-celular">
                        <br />
                        <span className="campo__dica">{h.instituicao}</span>
                      </span>
                    </td>
                    <td className="so-no-monitor">{h.instituicao}</td>
                    <td>{formatarDataHora(h.checkin_em)}</td>
                    <td>
                      {h.avisos.length === 0 ? (
                        <span className="etiqueta etiqueta--ok">ok</span>
                      ) : (
                        <span className="etiqueta etiqueta--espera">
                          {h.avisos.length} aviso(s)
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
