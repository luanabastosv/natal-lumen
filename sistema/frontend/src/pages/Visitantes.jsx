import { useCallback, useEffect, useMemo, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada } from "../components/core/Campo.jsx";
import FaixaDeAbas from "../components/core/FaixaDeAbas.jsx";
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
import { rotuloDia } from "../utils/dinheiro.js";
import "./Visitantes.css";

const TODOS = "todos";

/** Visitantes do evento: quem leu o QR Code da pulseira e deixou o contato
 *  para ver as fotos.
 *
 * A planilha, com uma aba por dia. Os QR Codes das pulseiras e o link da
 * galeria de cada dia ficam numa janela a parte: sao preparados uma vez, e a
 * tela do dia a dia e a lista.
 *
 * So a coordenacao geral do evento e a administracao geral (o backend
 * confere de novo): e contato de gente de fora.
 */
export default function Visitantes() {
  const { edicaoAtiva } = useSessao();
  const [dados, definirDados] = useState(null);
  const [erro, definirErro] = useState("");
  const [aba, definirAba] = useState(TODOS);
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

  const nomeDia = useMemo(() => {
    const m = new Map();
    for (const d of dados?.dias ?? []) m.set(d.id, rotuloDia(d.data, d.descricao));
    return m;
  }, [dados]);

  // A aba de um dia que nao e desta edicao (trocou a edicao) volta a Todos.
  const abaValida = dados?.dias.some((d) => d.id === aba) ? aba : TODOS;
  const linhas = useMemo(
    () =>
      (dados?.visitantes ?? []).filter(
        (v) => abaValida === TODOS || v.dia_evento_id === abaValida,
      ),
    [dados, abaValida],
  );

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

  const total = dados?.visitantes.length ?? 0;

  return (
    <div>
      <div className="pagina__cabecalho">
        <div className="pagina__texto">
          <div className="pagina__eyebrow">Coordenação</div>
          <h1 className="pagina__titulo">Visitantes do evento</h1>
          <Rabisco className="pagina__onda" />
          <p className="pagina__lede">
            Quem leu o QR Code da pulseira e deixou o contato para ver as fotos.
          </p>
        </div>
        <div className="pagina__acoes">
          <Button size="sm" variant="secondary" onClick={() => definirPreparando(true)} disabled={!dados}>
            QR Codes e fotos
          </Button>
          <Button size="sm" onClick={exportar} carregando={baixando} disabled={!total}>
            Exportar planilha
          </Button>
        </div>
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {preparando && dados && (
        <PrepararDias
          dias={dados.dias}
          aoFechar={() => definirPreparando(false)}
          aoSalvar={carregar}
        />
      )}

      {dados === null ? (
        erro ? null : <Carregando tela>Buscando os visitantes...</Carregando>
      ) : dados.dias.length === 0 ? (
        <EmptyState
          titulo="A edição ainda não tem dias do evento"
          corpo="Cadastre os dias em Configurações para gerar os QR Codes das pulseiras."
        />
      ) : (
        <>
          <FaixaDeAbas reiniciarEm={edicaoAtiva}>
            {[{ id: TODOS, rotulo: "Todos", total }, ...dados.dias.map((d) => ({
              id: d.id,
              rotulo: rotuloDia(d.data, d.descricao),
              total: d.total,
            }))].map((a) => (
              <button
                key={a.id}
                type="button"
                role="tab"
                aria-selected={a.id === abaValida}
                className={`aba ${a.id === abaValida ? "aba--ativa" : ""}`}
                onClick={() => definirAba(a.id)}
              >
                <span>{a.rotulo}</span>
                <span className="aba__contagem">
                  {a.total} {a.total === 1 ? "visitante" : "visitantes"}
                </span>
              </button>
            ))}
          </FaixaDeAbas>

          {linhas.length === 0 ? (
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
                    <th>Dia</th>
                    <th>Cadastro</th>
                  </tr>
                </thead>
                <tbody>
                  {linhas.map((v) => (
                    <tr key={v.id}>
                      <td className="visitantes__nome">{v.nome}</td>
                      <td className="visitantes__fixo">{v.celular}</td>
                      <td>{nomeDia.get(v.dia_evento_id) ?? "—"}</td>
                      <td className="visitantes__fixo">{v.criado_em}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** A janela dos QR Codes e do link das fotos, um bloco por dia. */
function PrepararDias({ dias, aoFechar, aoSalvar }) {
  return (
    <Modal titulo="QR Codes e fotos" aoFechar={aoFechar} tamanho="grande">
      <p className="visitantes__explica">
        Cada dia tem o seu QR Code, só desta edição: no ano que vem o sistema gera outros. O link
        da galeria pode ser colado depois e trocado quando quiser, sem mudar o QR.
      </p>
      <div className="visitantes__dias">
        {dias.map((d) => (
          <BlocoDia key={d.id} dia={d} aoSalvar={aoSalvar} />
        ))}
      </div>
    </Modal>
  );
}

function BlocoDia({ dia, aoSalvar }) {
  const notificar = useNotificar();
  const [link, definirLink] = useState(dia.link_fotos ?? "");
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState("");
  const mudou = (link.trim() || null) !== (dia.link_fotos ?? null);

  async function salvar(e) {
    e.preventDefault();
    definirSalvando(true);
    definirErro("");
    try {
      await salvarLinkFotos(dia.id, link.trim());
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
      await baixarQrCode(dia.id, formato);
    } catch (err) {
      definirErro(err.message);
    }
  }

  return (
    <section className="visitantes__dia">
      <img className="visitantes__qr" src={imagemQrCode(dia.id)} alt={`QR Code de ${rotuloDia(dia.data, dia.descricao)}`} />
      <div className="visitantes__dia-texto">
        <h3>{rotuloDia(dia.data, dia.descricao)}</h3>
        <code className="visitantes__endereco">{dia.endereco_qr.replace(/^https:\/\//, "")}</code>
        <div className="visitantes__botoes">
          <Button size="sm" variant="secondary" onClick={() => baixar("png")}>
            Baixar PNG
          </Button>
          <Button size="sm" variant="secondary" onClick={() => baixar("svg")}>
            Baixar SVG
          </Button>
          <Button size="sm" variant="ghost" as="a" href={dia.endereco_qr}>
            Testar
          </Button>
        </div>
        <form className="visitantes__link" onSubmit={salvar}>
          <Entrada
            rotulo="Link da galeria de fotos"
            tipo="url"
            placeholder="https://..."
            value={link}
            onChange={(e) => definirLink(e.target.value)}
            erro={erro}
            dica={dia.link_fotos ? "Liberado: quem se cadastra vê o botão das fotos." : "Vazio: a Estrelinha avisa que as fotos ainda estão sendo preparadas."}
          />
          <Button size="sm" type="submit" carregando={salvando} disabled={!mudou}>
            Salvar
          </Button>
        </form>
      </div>
    </section>
  );
}
