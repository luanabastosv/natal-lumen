import { useEffect, useRef, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { listarEdicoes } from "../services/cadastros.js";
import { fazerCheckin } from "../services/logistica.js";
import { formatarData, formatarDataHora } from "../utils/dinheiro.js";

export default function Checkin() {
  const { edicaoAtiva } = useSessao();

  const [edicoes, definirEdicoes] = useState([]);
  const [edicaoId, definirEdicaoId] = useState(edicaoAtiva ?? "");
  const [codigo, definirCodigo] = useState("");
  const [resultado, definirResultado] = useState(null);
  const [historico, definirHistorico] = useState([]);
  const [erro, definirErro] = useState("");
  const [enviando, definirEnviando] = useState(false);

  const campoCodigo = useRef(null);

  useEffect(() => {
    let vivo = true;
    listarEdicoes()
      .then((eds) => {
        if (!vivo) return;
        definirEdicoes(eds);
        if (!edicaoId && eds.length) definirEdicaoId(eds[0].id);
      })
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function registrar(evento) {
    evento.preventDefault();
    definirErro("");
    definirEnviando(true);

    // O QR do crachá traz "edicao:codigo"; digitado, vem só o código.
    const lido = codigo.trim();
    const soCodigo = lido.includes(":") ? lido.split(":").pop() : lido;

    try {
      const entrada = await fazerCheckin(soCodigo, Number(edicaoId));
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
      <div className="pagina__eyebrow">Dia do evento</div>
      <h1 className="pagina__titulo">Check-in</h1>
      <p className="pagina__lede">
        Leia o QR do crachá ou digite o código. O check-in nunca é recusado — o que
        estiver estranho aparece como aviso.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>

      <form className="painel" onSubmit={registrar}>
        <div className="linha-campos">
          <Selecao rotulo="Edição" value={edicaoId} onChange={(e) => definirEdicaoId(e.target.value)}>
            {edicoes.map((e) => (
              <option key={e.id} value={e.id}>{e.nome}</option>
            ))}
          </Selecao>
          <Entrada
            rotulo="Código da criança"
            value={codigo}
            onChange={(e) => definirCodigo(e.target.value)}
            ref={campoCodigo}
            autoFocus
            dica="O leitor de QR digita sozinho e confirma."
          />
        </div>
        <Button type="submit" carregando={enviando} disabled={!codigo.trim() || !edicaoId}>
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
            {resultado.dia_evento && <> · dia {formatarData(resultado.dia_evento)}</>}
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
                <tr><th>Criança</th><th>Instituição</th><th>Hora</th><th>Avisos</th></tr>
              </thead>
              <tbody>
                {historico.map((h, i) => (
                  <tr key={`${h.crianca_id}-${i}`}>
                    <td>{h.nome}</td>
                    <td>{h.instituicao}</td>
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
