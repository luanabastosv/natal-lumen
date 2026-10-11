import { useEffect, useState } from "react";
import Carregando from "../feedback/Carregando.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import { fichaDaInstituicao } from "../../services/cadastros.js";
import { rotuloDia } from "../../utils/dinheiro.js";
import { linkWhatsapp } from "../../utils/whatsapp.js";

/** Telefone com link para a conversa, quando da para abrir uma. */
function Contato({ numero }) {
  if (!numero) return <span className="celula--vazia">sem telefone</span>;
  const link = linkWhatsapp(numero);
  return link ? (
    <a href={link} target="_blank" rel="noreferrer">
      {numero}
    </a>
  ) : (
    <span>{numero}</span>
  );
}

function Equipe({ titulo, pessoas, vazio }) {
  return (
    <>
      <h3 className="ficha__secao">{titulo}</h3>
      {pessoas.length === 0 ? (
        <p className="campo__dica">{vazio}</p>
      ) : (
        <ul className="ficha-inst__pessoas">
          {pessoas.map((p) => (
            <li key={p.email}>
              <strong>{p.nome}</strong>
              <span>
                <Contato numero={p.whatsapp} />
                {" · "}
                <a href={`mailto:${p.email}`}>{p.email}</a>
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/** "Ver informações da instituição", na lista de criancas: o cadastro, o dia,
 *  o nucleo e a bata, quantas criancas, e quem responde por ela — o
 *  responsavel da instituicao e os monitores e comissarios da equipe. */
export default function FichaInstituicao({ instituicaoId, edicaoId, aoFechar }) {
  const [f, definirF] = useState(null);
  const [erro, definirErro] = useState("");

  useEffect(() => {
    let vivo = true;
    fichaDaInstituicao(instituicaoId, edicaoId)
      .then((r) => vivo && definirF(r))
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, [instituicaoId, edicaoId]);

  return (
    <Modal rotulo="Instituição" titulo={f?.nome ?? "Carregando..."} tamanho="largo" aoFechar={aoFechar}>
      <Mensagem tipo="erro">{erro}</Mensagem>
      {!f && !erro && <Carregando>Buscando a instituição...</Carregando>}
      {f && (
        <>
          <dl className="ficha ficha--duas">
            <dt>Sigla</dt>
            <dd>{f.sigla ?? "—"}</dd>
            <dt>Crianças</dt>
            <dd>
              {f.criancas}
              {f.desistentes > 0 && ` (+${f.desistentes} desistente${f.desistentes === 1 ? "" : "s"})`}
            </dd>
            <dt>Dia do evento</dt>
            <dd>{f.dia_evento ? rotuloDia(f.dia_evento, f.dia_evento_descricao) : "sem dia"}</dd>
            <dt>Ônibus</dt>
            <dd>{f.onibus}</dd>
            <dt>Núcleo</dt>
            <dd>{f.nucleo ? `Núcleo ${f.nucleo}` : "ainda não definido"}</dd>
            <dt>Bata</dt>
            <dd>
              {f.cor_bata_hex ? (
                <>
                  <span className="amostra-bata" style={{ background: f.cor_bata_hex }} />
                  {f.cor_bata_nome ?? f.cor_bata_hex}
                </>
              ) : (
                "ainda não definida"
              )}
            </dd>
            <dt className="ficha__dt-largo">Endereço</dt>
            <dd className="ficha__dd-largo">{f.endereco ?? "—"}</dd>
          </dl>

          <h3 className="ficha__secao">Responsável na instituição</h3>
          {f.responsavel || f.telefone ? (
            <ul className="ficha-inst__pessoas">
              <li>
                <strong>{f.responsavel ?? "Sem nome cadastrado"}</strong>
                <span>
                  <Contato numero={f.telefone} />
                </span>
              </li>
            </ul>
          ) : (
            <p className="campo__dica">Nenhum responsável cadastrado. Cadastre em Instituições.</p>
          )}

          <Equipe
            titulo="Monitores"
            pessoas={f.monitores}
            vazio="Nenhum monitor atribuído a esta instituição. A atribuição é feita em Usuários."
          />
          <Equipe
            titulo="Comissários"
            pessoas={f.comissarios}
            vazio="Nenhum comissário atribuído a esta instituição."
          />
        </>
      )}
    </Modal>
  );
}
