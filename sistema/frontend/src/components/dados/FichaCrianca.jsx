import { useEffect, useState } from "react";
import Button from "../core/Button.jsx";
import Carregando from "../feedback/Carregando.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import { detalharCrianca, marcarDesistencia } from "../../services/criancas.js";
import EtiquetaDia from "../core/EtiquetaDia.jsx";
import { dinheiro, formatarDataHora } from "../../utils/dinheiro.js";
import { linkWhatsapp } from "../../utils/whatsapp.js";

const TIPOS = { cesta: "Cesta", festa: "Festa" };

export default function FichaCrianca({ criancaId, aoFechar, podeEditar = false, aoMudar }) {
  const [ficha, definirFicha] = useState(null);
  const [erro, definirErro] = useState("");
  const [mudandoDesistencia, definirMudandoDesistencia] = useState(false);

  useEffect(() => {
    let vivo = true;
    detalharCrianca(criancaId)
      .then((d) => vivo && definirFicha(d))
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, [criancaId]);

  const desistiu = Boolean(ficha?.desistiu_em);

  /** Vai e volta: quem desistiu pode mudar de ideia ate a vespera. */
  async function alternarDesistencia() {
    definirErro("");
    definirMudandoDesistencia(true);
    try {
      const atualizada = await marcarDesistencia(criancaId, !desistiu);
      definirFicha((f) => ({ ...f, desistiu_em: atualizada.desistiu_em }));
      aoMudar?.(atualizada);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirMudandoDesistencia(false);
    }
  }

  return (
    <Modal
      rotulo="Nome da criança:"
      titulo={ficha ? ficha.nome : "Criança"}
      aoFechar={aoFechar}
      tamanho="grande"
      /* Ghost nos dois sentidos, e nao so na volta: solido, este botao ficava
         com a cara do CTA da ficha — e o que se vem fazer aqui e LER a ficha da
         crianca, nao tira-la do evento. Aparece so para quem pode editar
         crianca (coordenacao e administracao geral), a mesma regra que o
         backend cobra na rota. */
      rodape={
        podeEditar &&
        ficha && (
          <Button
            variant="ghost"
            size="sm"
            onClick={alternarDesistencia}
            carregando={mudandoDesistencia}
          >
            {desistiu ? "Vai ao evento de novo" : "Marcar como desistente"}
          </Button>
        )
      }
    >
      <Mensagem tipo="erro">{erro}</Mensagem>

      {!ficha && !erro && <Carregando>Carregando...</Carregando>}

      {ficha && (
        <>
          <dl className="ficha ficha--duas">
            <dt>Código</dt>
            <dd>{ficha.codigo}</dd>
            <dt>Idade</dt>
            <dd>{ficha.idade} anos</dd>
            <dt>Sexo</dt>
            <dd>{ficha.sexo === "F" ? "Feminino" : "Masculino"}</dd>
            <dt>Instituição</dt>
            <dd>{ficha.instituicao}</dd>
            <dt>Dia</dt>
            <dd>
              {ficha.dia_evento ? (
                <EtiquetaDia data={ficha.dia_evento} descricao={ficha.dia_evento_descricao} />
              ) : (
                "sem dia marcado"
              )}
            </dd>
            <dt>Comissário</dt>
            <dd>
              {ficha.comissario ?? "sem responsável"}
              {ficha.comissario_grupo && ` · ${ficha.comissario_grupo}`}
            </dd>
            <dt>Kit</dt>
            <dd>
              {ficha.kit_status}
              {ficha.kit_montado_em && ` · ${formatarDataHora(ficha.kit_montado_em)}`}
            </dd>
            <dt>Check-in</dt>
            <dd>{ficha.checkin_em ? formatarDataHora(ficha.checkin_em) : "não fez"}</dd>
            {ficha.observacoes && (
              <>
                <dt className="ficha__dt-largo">Observações</dt>
                <dd className="ficha__dd-largo">{ficha.observacoes}</dd>
              </>
            )}
          </dl>

          {/* A conta e dos CONFIRMADOS: promessa nao e apadrinhamento, e um
              "2 de 2" contando promessa diria que esta crianca esta pronta
              quando ainda ha dinheiro a entrar. As promessas aparecem logo
              abaixo, uma a uma, com a etiqueta delas. */}
          <div className="ficha__secao">
            Padrinhos ({ficha.padrinhos.filter((p) => p.pago).length} de 2)
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
                  <div key={p.apadrinhamento_id} className="ficha__vinculo">
                    <strong>{p.nome}</strong>
                    <span className="etiqueta etiqueta--neutra">{TIPOS[p.tipo] ?? p.tipo}</span>{" "}
                    {/* "a pagar" dizia pouco: parecia detalhe administrativo de
                        um apadrinhamento que ja valia. Nao vale — enquanto o
                        pagamento nao entra, isto e uma promessa, e a crianca
                        conta como sem padrinho no painel e na lista. */}
                    <span className={`etiqueta ${p.pago ? "etiqueta--ok" : "etiqueta--espera"}`}>
                      {p.pago ? "confirmado" : "promessa · falta pagar"}
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

              {ficha.padrinhos.every((p) => !p.pago) && (
                <Mensagem tipo="aviso">
                  Só há <strong>promessa</strong> aqui: enquanto o pagamento não for
                  registrado, esta criança continua contando como{" "}
                  <strong>sem padrinho</strong> no painel e nas listas, e o cartão de
                  agradecimento não sai.
                </Mensagem>
              )}

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
