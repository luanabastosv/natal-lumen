import { useEffect, useState } from "react";
import Button from "../core/Button.jsx";
import Carregando from "../feedback/Carregando.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import { detalharCrianca, marcarDesistencia } from "../../services/criancas.js";
import EtiquetaDia from "../core/EtiquetaDia.jsx";
import { dinheiro, formatarDataHora } from "../../utils/dinheiro.js";
import { linkWhatsapp } from "../../utils/whatsapp.js";
import { useSessao } from "../../contexts/useSessao.js";
import EtiquetaDesistente from "../core/EtiquetaDesistente.jsx";

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
  // A coordenacao geral do evento (e a administracao geral): sao as unicas
  // que leem, na ficha, o recado que o comissario deixou sobre a crianca.
  const { usuario, vinculoAtivo } = useSessao();
  const coordenacaoGeral = Boolean(usuario?.admin_geral) || vinculoAtivo?.perfil === "Coordenacao";

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
          {/* Em cima de tudo: e a primeira coisa que muda o que se faz com ela. */}
          {desistiu && (
            <p className="ficha__desistente">
              <EtiquetaDesistente /> Desistiu de ir ao evento em{" "}
              {new Date(ficha.desistiu_em).toLocaleDateString("pt-BR")}.
            </p>
          )}

          {/* Uma ave-maria por vez que ela apareceu no convite de oracao do
              dia, somando todo mundo. Sem nenhuma, a etiqueta nem existe. */}
          {ficha.ave_marias > 0 && (
            <p className="ficha__oracao">
              {ficha.ave_marias === 1
                ? "1 ave-maria já foi rezada por este coração"
                : `${ficha.ave_marias} ave-marias já foram rezadas por este coração`}
              <img src="/acesso/images/adesivo-oracao.png" alt="" />
            </p>
          )}

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
            {/* Quem responde pela crianca e assunto da captacao, e so chega a
                quem capta — para a monitoria e para a estrutura o campo vem
                nulo e a linha nem existe. Quem manda e o servidor: `pode_ver_
                contato` e a MESMA pergunta que decidiu o que veio, e por isso
                a tela nao a refaz por conta propria. */}
            {ficha.ve_captacao && (
              <>
                <dt>Comissário</dt>
                <dd>
                  {ficha.comissario ?? "sem responsável"}
                  {ficha.comissario_grupo && ` · ${ficha.comissario_grupo}`}
                </dd>
              </>
            )}
            {/* Nulo aqui nao e "kit pendente": e "este perfil nao monta kit".
                Pendente viria escrito. */}
            {ficha.kit_status !== null && (
              <>
                <dt>Kit</dt>
                <dd>
                  {ficha.kit_status}
                  {ficha.kit_montado_em && ` · ${formatarDataHora(ficha.kit_montado_em)}`}
                </dd>
              </>
            )}
            <dt>Autorização</dt>
            <dd>
              {ficha.autorizacao_em
                ? `recebida · ${formatarDataHora(ficha.autorizacao_em)}`
                : "ainda não chegou"}
            </dd>
            <dt>Check-in</dt>
            <dd>{ficha.checkin_em ? formatarDataHora(ficha.checkin_em) : "não fez"}</dd>
            {/* O que o monitor marcou ao conferir a autorizacao. So existe
                depois que ela subiu; nas antigas, sem resposta, a linha some. */}
            {ficha.autorizacao_em &&
              [
                ["Necessidade especial", ficha.necessidade_especial, ficha.necessidade_especial_qual],
                ["Alergia ou restrição", ficha.restricao_alimentar, ficha.restricao_alimentar_qual],
                ["Obs. da autorização", ficha.tem_observacao, ficha.observacao_autorizacao],
              ]
                .filter(([, sim]) => sim !== null)
                .map(([rotulo, sim, qual]) => (
                  <div key={rotulo} style={{ display: "contents" }}>
                    <dt className="ficha__dt-largo">{rotulo}</dt>
                    <dd className="ficha__dd-largo">{sim ? `Sim · ${qual}` : "Não"}</dd>
                  </div>
                ))}
            {ficha.observacoes && (
              <>
                <dt className="ficha__dt-largo">Observações</dt>
                <dd className="ficha__dd-largo">{ficha.observacoes}</dd>
              </>
            )}
            {/* O recado do comissario: so a coordenacao geral le aqui. O
                comissario o escreve e le na coluna da lista dele. */}
            {coordenacaoGeral && ficha.observacao_comissario && (
              <>
                <dt className="ficha__dt-largo">Observação do comissário</dt>
                <dd className="ficha__dd-largo">{ficha.observacao_comissario}</dd>
              </>
            )}
          </dl>

          {/* A secao inteira some para quem nao capta — nem a conta aparece.
              "0 de 2" ja seria informacao sobre o apadrinhamento desta crianca,
              e e justamente isso que a monitoria e a estrutura nao recebem.

              A conta e dos CONFIRMADOS: promessa nao e apadrinhamento, e um
              "2 de 2" contando promessa diria que esta crianca esta pronta
              quando ainda ha dinheiro a entrar. As promessas aparecem logo
              abaixo, uma a uma, com a etiqueta delas. */}
          {ficha.ve_captacao && (
            <>
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
                    {ficha.ve_captacao && (p.whatsapp || p.email) && (
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
                  <strong>sem padrinho</strong> no painel e nas listas, e o agradecimento
                  não sai.
                </Mensagem>
              )}

            </>
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
