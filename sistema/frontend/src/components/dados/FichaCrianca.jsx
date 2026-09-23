import { useEffect, useState } from "react";
import Carregando from "../feedback/Carregando.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import { detalharCrianca } from "../../services/criancas.js";
import { dinheiro, formatarData, formatarDataHora } from "../../utils/dinheiro.js";

const TIPOS = { cesta: "Cesta", festa: "Festa" };

/** Só dígitos: é o que o link do WhatsApp aceita. */
function linkWhatsapp(numero) {
  const so = (numero ?? "").replace(/\D/g, "");
  if (so.length < 10) return null;
  return `https://wa.me/${so.startsWith("55") ? so : `55${so}`}`;
}

export default function FichaCrianca({ criancaId, aoFechar }) {
  const [ficha, definirFicha] = useState(null);
  const [erro, definirErro] = useState("");

  useEffect(() => {
    let vivo = true;
    detalharCrianca(criancaId)
      .then((d) => vivo && definirFicha(d))
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, [criancaId]);

  return (
    <Modal titulo={ficha ? ficha.nome : "Criança"} aoFechar={aoFechar}>
      <Mensagem tipo="erro">{erro}</Mensagem>

      {!ficha && !erro && <Carregando>Carregando...</Carregando>}

      {ficha && (
        <>
          <dl className="ficha">
            <dt>Código</dt>
            <dd>{ficha.codigo}</dd>
            <dt>Idade</dt>
            <dd>{ficha.idade} anos</dd>
            <dt>Sexo</dt>
            <dd>{ficha.sexo === "F" ? "Feminino" : "Masculino"}</dd>
            <dt>Instituição</dt>
            <dd>{ficha.instituicao}</dd>
            <dt>Dia</dt>
            <dd>{ficha.dia_evento ? formatarData(ficha.dia_evento) : "sem dia marcado"}</dd>
            <dt>Kit</dt>
            <dd>
              {ficha.kit_status}
              {ficha.kit_entregue_em && ` · ${formatarDataHora(ficha.kit_entregue_em)}`}
            </dd>
            <dt>Check-in</dt>
            <dd>{ficha.checkin_em ? formatarDataHora(ficha.checkin_em) : "não fez"}</dd>
            {ficha.observacoes && (
              <>
                <dt>Observações</dt>
                <dd>{ficha.observacoes}</dd>
              </>
            )}
          </dl>

          <div className="ficha__secao">
            Padrinhos ({ficha.padrinhos.length} de 2)
          </div>

          {ficha.padrinhos.length === 0 ? (
            <Mensagem tipo="aviso">
              Esta criança ainda <strong>não tem padrinho</strong>.
            </Mensagem>
          ) : (
            <>
              {ficha.padrinhos.map((p) => {
                const zap = linkWhatsapp(p.whatsapp);
                return (
                  <div key={p.apadrinhamento_id} className="ficha__padrinho">
                    <strong>{p.nome}</strong>
                    <span className="etiqueta etiqueta--neutra">{TIPOS[p.tipo] ?? p.tipo}</span>{" "}
                    <span className={`etiqueta ${p.pago ? "etiqueta--ok" : "etiqueta--espera"}`}>
                      {p.pago ? "pago" : "a pagar"}
                    </span>{" "}
                    <span className="etiqueta etiqueta--neutra">{dinheiro(p.valor)}</span>
                    {ficha.pode_ver_contato && (p.whatsapp || p.email) && (
                      <div style={{ marginTop: 6 }}>
                        {p.whatsapp &&
                          (zap ? (
                            <a href={zap} target="_blank" rel="noopener noreferrer">
                              {p.whatsapp}
                            </a>
                          ) : (
                            p.whatsapp
                          ))}
                        {p.whatsapp && p.email && " · "}
                        {p.email && <a href={`mailto:${p.email}`}>{p.email}</a>}
                      </div>
                    )}
                  </div>
                );
              })}

              {!ficha.pode_ver_contato && (
                <p className="campo__dica" style={{ marginTop: 0 }}>
                  O nome e o contato do padrinho só aparecem para quem tem permissão de
                  ver padrinhos.
                </p>
              )}
            </>
          )}

          <div className="ficha__secao">Cartões ({ficha.cartoes.length} de 2)</div>

          {ficha.cartoes.length === 0 ? (
            <p className="campo__dica" style={{ marginTop: 0 }}>
              Nenhum cartão digitalizado ainda.
            </p>
          ) : (
            <dl className="ficha">
              {ficha.cartoes.map((c) => (
                <div key={c.id} style={{ display: "contents" }}>
                  <dt>{TIPOS[c.tipo] ?? c.tipo}</dt>
                  <dd>
                    <span
                      className={`etiqueta ${c.status === "enviado" ? "etiqueta--ok" : "etiqueta--espera"}`}
                    >
                      {c.status}
                    </span>
                    {c.enviado_em && ` · ${formatarDataHora(c.enviado_em)}`}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </>
      )}
    </Modal>
  );
}
