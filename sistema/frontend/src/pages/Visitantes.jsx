import { useCallback, useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada } from "../components/core/Campo.jsx";
import Rabisco from "../components/core/Rabisco.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Modal from "../components/feedback/Modal.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import {
  baixarPlanilhaVisitantes,
  baixarQrCode,
  imagemQrCode,
  listarVisitantes,
  salvarLinkFotos,
} from "../services/visitantes.js";
import "./Visitantes.css";

/** Visitantes do evento: quem leu o QR Code da pulseira e deixou o contato
 *  para ver as fotos.
 *
 * Uma lista so, da edicao inteira: o QR Code e o mesmo nos dois dias (a
 * pulseira que sobra no sabado serve no domingo), entao nao ha como — nem
 * por que — separar por dia. O QR Code e o link da galeria ficam numa janela
 * a parte: sao preparados uma vez, e a tela do dia a dia e a lista.
 *
 * So a coordenacao geral do evento e a administracao geral (o backend
 * confere de novo): e contato de gente de fora.
 */
export default function Visitantes() {
  const { edicaoAtiva } = useSessao();
  const [dados, definirDados] = useState(null);
  const [erro, definirErro] = useState("");
  const [preparando, definirPreparando] = useState(false);
  const [baixando, definirBaixando] = useState(false);

  const carregar = useCallback(() => {
    if (!edicaoAtiva) return;
    listarVisitantes(edicaoAtiva)
      .then((r) => {
        definirDados(r);
        definirErro("");
      })
      .catch((e) => definirErro(e.message));
  }, [edicaoAtiva]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function exportar() {
    definirBaixando(true);
    try {
      await baixarPlanilhaVisitantes(edicaoAtiva);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirBaixando(false);
    }
  }

  const visitantes = dados?.visitantes ?? [];
  const n = visitantes.length;

  return (
    <div>
      <div className="pagina__cabecalho">
        <div className="pagina__texto">
          <div className="pagina__eyebrow">Coordenação</div>
          <h1 className="pagina__titulo">Visitantes do evento</h1>
          <Rabisco className="pagina__onda" />
          <p className="pagina__lede">
            {dados && n > 0
              ? `${n} ${n === 1 ? "pessoa leu" : "pessoas leram"} o QR Code da pulseira e ${n === 1 ? "deixou" : "deixaram"} o contato para ver as fotos.`
              : "Quem leu o QR Code da pulseira e deixou o contato para ver as fotos."}
          </p>
        </div>
        <div className="pagina__acoes">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => definirPreparando(true)}
            disabled={!dados}
          >
            QR Code e fotos
          </Button>
          <Button size="sm" onClick={exportar} carregando={baixando} disabled={!n}>
            Exportar planilha
          </Button>
        </div>
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {preparando && dados && (
        <PrepararQrCode
          edicaoId={edicaoAtiva}
          dados={dados}
          aoFechar={() => definirPreparando(false)}
          aoSalvar={carregar}
        />
      )}

      {dados === null ? (
        erro ? null : <Carregando tela>Buscando os visitantes...</Carregando>
      ) : n === 0 ? (
        <EmptyState
          titulo="Ninguém por aqui ainda"
          corpo="Quando alguém ler o QR Code da pulseira e deixar nome e celular, aparece nesta lista."
        />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela tabela--densa visitantes__tabela">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Celular</th>
                <th>Cadastro</th>
              </tr>
            </thead>
            <tbody>
              {visitantes.map((v) => (
                <tr key={v.id}>
                  <td className="visitantes__nome">{v.nome}</td>
                  <td className="visitantes__fixo">{v.celular}</td>
                  <td className="visitantes__fixo">{v.criado_em}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** A janela do QR Code das pulseiras e do link da galeria. */
function PrepararQrCode({ edicaoId, dados, aoFechar, aoSalvar }) {
  const notificar = useNotificar();
  const [link, definirLink] = useState(dados.link_fotos ?? "");
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState("");
  const mudou = (link.trim() || null) !== (dados.link_fotos ?? null);

  async function salvar(e) {
    e.preventDefault();
    definirSalvando(true);
    definirErro("");
    try {
      await salvarLinkFotos(edicaoId, link.trim());
      notificar(link.trim() ? "Link das fotos salvo." : "Link das fotos removido.");
      aoSalvar();
    } catch (err) {
      definirErro(err.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function baixar(formato) {
    try {
      await baixarQrCode(edicaoId, formato);
    } catch (err) {
      definirErro(err.message);
    }
  }

  return (
    <Modal titulo="QR Code e fotos" aoFechar={aoFechar}>
      <p className="visitantes__explica">
        Um QR Code só, para as pulseiras dos dois dias desta edição. No ano que vem o sistema gera
        outro. O link da galeria pode ser colado depois e trocado quando quiser, sem mudar o QR.
      </p>
      <section className="visitantes__bloco">
        <img className="visitantes__qr" src={imagemQrCode(edicaoId)} alt="QR Code das pulseiras" />
        <div>
          <code className="visitantes__endereco">
            {dados.endereco_qr.replace(/^https:\/\//, "")}
          </code>
          <div className="visitantes__botoes">
            <Button size="sm" variant="secondary" onClick={() => baixar("png")}>
              Baixar PNG
            </Button>
            <Button size="sm" variant="secondary" onClick={() => baixar("svg")}>
              Baixar SVG
            </Button>
            <Button size="sm" variant="ghost" as="a" href={dados.endereco_qr}>
              Testar
            </Button>
          </div>
        </div>
      </section>
      <form className="visitantes__link" onSubmit={salvar}>
        <Entrada
          rotulo="Link da galeria de fotos"
          tipo="url"
          placeholder="https://..."
          value={link}
          onChange={(e) => definirLink(e.target.value)}
          erro={erro}
          dica={
            dados.link_fotos
              ? "Liberado: quem se cadastra vê o botão das fotos."
              : "Vazio: a Estrelinha avisa que as fotos ainda estão sendo preparadas."
          }
        />
        <Button size="sm" type="submit" carregando={salvando} disabled={!mudou}>
          Salvar
        </Button>
      </form>
    </Modal>
  );
}
