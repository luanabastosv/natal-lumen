import { useCallback, useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { listarEdicoes } from "../services/cadastros.js";
import {
  analisarCartao,
  confirmarCartao,
  listarCartoes,
  marcarEnviados,
  urlDaImagem,
} from "../services/cartoes.js";
import { formatarDataHora } from "../utils/dinheiro.js";

export default function Cartoes() {
  const { pode, edicaoAtiva } = useSessao();

  const [edicoes, definirEdicoes] = useState([]);
  const [edicaoId, definirEdicaoId] = useState(edicaoAtiva ?? "");
  const [cartoes, definirCartoes] = useState({ itens: [], total: 0 });
  const [situacao, definirSituacao] = useState("");

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");

  // Fluxo de digitalizacao
  const [codigo, definirCodigo] = useState("");
  const [arquivo, definirArquivo] = useState(null);
  const [analise, definirAnalise] = useState(null);
  const [tipo, definirTipo] = useState("cesta");
  const [nome, definirNome] = useState("");
  const [analisando, definirAnalisando] = useState(false);
  const [salvando, definirSalvando] = useState(false);

  const [marcados, definirMarcados] = useState([]);

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

  const buscar = useCallback(async () => {
    try {
      definirCartoes(await listarCartoes({ situacao }));
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [situacao]);

  useEffect(() => {
    if (edicaoId) buscar();
  }, [edicaoId, buscar]);

  async function analisar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSucesso("");
    definirAnalisando(true);
    try {
      const resultado = await analisarCartao({
        arquivo,
        codigo: codigo.trim(),
        edicaoId,
      });
      definirAnalise(resultado);
      definirNome(resultado.nome_sugerido);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirAnalisando(false);
    }
  }

  async function salvar() {
    definirErro("");
    definirSalvando(true);
    try {
      await confirmarCartao({
        id: analise.id,
        crianca_id: analise.crianca_id,
        tipo,
        texto_ocr: nome.trim() || null,
      });
      definirSucesso(`Cartão de ${tipo} de ${analise.crianca_nome} guardado.`);
      limpar();
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  function limpar() {
    definirAnalise(null);
    definirArquivo(null);
    definirCodigo("");
    definirNome("");
  }

  async function enviar() {
    definirErro("");
    try {
      const enviados = await marcarEnviados(marcados);
      definirSucesso(`${enviados.length} cartão(ões) marcado(s) como enviado(s).`);
      definirMarcados([]);
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  function alternar(id) {
    definirMarcados((atual) =>
      atual.includes(id) ? atual.filter((x) => x !== id) : [...atual, id],
    );
  }

  const podeMarcar = pode("enviar_cartoes");

  return (
    <div>
      <div className="pagina__eyebrow">Monitoria</div>
      <h1 className="pagina__titulo">Cartões</h1>
      <p className="pagina__lede">
        Cada criança escreve dois cartões, um para cada padrinho. Fotografe o cartão,
        confira o nome lido e guarde — o sistema corrige a perspectiva da foto.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      {pode("subir_cartoes") && (
        <>
          {!analise ? (
            <form className="painel" onSubmit={analisar}>
              <h2 className="painel__titulo">Digitalizar um cartão</h2>
              <div className="linha-campos">
                <Selecao
                  rotulo="Edição"
                  value={edicaoId}
                  onChange={(e) => definirEdicaoId(e.target.value)}
                >
                  {edicoes.map((e) => (
                    <option key={e.id} value={e.id}>{e.nome}</option>
                  ))}
                </Selecao>
                <Entrada
                  rotulo="Código da criança"
                  value={codigo}
                  onChange={(e) => definirCodigo(e.target.value)}
                  dica="O mesmo código da lista da instituição."
                  required
                />
              </div>

              <label className="campo">
                <span className="campo__rotulo">Foto do cartão</span>
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="campo__controle"
                  onChange={(e) => definirArquivo(e.target.files?.[0] ?? null)}
                  required
                />
                <span className="campo__dica">
                  Fotografe o cartão inteiro, sobre uma superfície de cor diferente da
                  dele. Pelo celular, abre a câmera direto.
                </span>
              </label>

              <Button
                type="submit"
                carregando={analisando}
                disabled={!arquivo || !codigo.trim()}
              >
                {analisando ? "Lendo o cartão..." : "Analisar"}
              </Button>
            </form>
          ) : (
            <div className="painel painel--destaque">
              <h2 className="painel__titulo">
                {analise.crianca_nome} · {analise.instituicao}
              </h2>

              {analise.aviso && (
                <Mensagem tipo="aviso">
                  Não foi possível detectar as bordas do cartão. A foto vai ser guardada
                  como está, sem correção de perspectiva.
                </Mensagem>
              )}

              <div className="linha-campos">
                <div>
                  <Selecao rotulo="Tipo" value={tipo} onChange={(e) => definirTipo(e.target.value)}>
                    <option value="cesta">Cesta</option>
                    <option value="festa">Festa</option>
                  </Selecao>
                  <Entrada
                    rotulo="Nome lido no cartão"
                    value={nome}
                    onChange={(e) => definirNome(e.target.value)}
                    dica="Guardado junto com a imagem, para busca depois."
                  />

                  {analise.textos.length > 0 && (
                    <div className="campo">
                      <span className="campo__rotulo">Outros textos detectados</span>
                      <div className="marcaveis">
                        {analise.textos.map((t, i) => (
                          <button
                            type="button"
                            key={`${t.texto}-${i}`}
                            className={`marcavel ${t.texto === nome ? "marcavel--marcado" : ""}`}
                            onClick={() => definirNome(t.texto)}
                          >
                            {t.texto}
                            <small style={{ opacity: 0.6 }}>
                              {Math.round(t.confianca * 100)}%
                            </small>
                          </button>
                        ))}
                      </div>
                      <span className="campo__dica">Clique para usar como nome.</span>
                    </div>
                  )}
                </div>

                <div>
                  <span className="campo__rotulo">Cartão digitalizado</span>
                  <img
                    src={`data:image/jpeg;base64,${analise.imagem_base64}`}
                    alt="Cartão digitalizado"
                    style={{
                      width: "100%",
                      borderRadius: "var(--radius-md)",
                      border: "var(--stroke-hairline) solid var(--border-default)",
                    }}
                  />
                </div>
              </div>

              <div className="barra-acoes barra-acoes--fim">
                <Button onClick={salvar} carregando={salvando}>Guardar cartão</Button>
                <Button variant="ghost" onClick={limpar} disabled={salvando}>Descartar</Button>
              </div>
            </div>
          )}
        </>
      )}

      <div className="barra-acoes">
        <Selecao value={situacao} onChange={(e) => definirSituacao(e.target.value)}>
          <option value="">Todos</option>
          <option value="digitalizado">A enviar</option>
          <option value="enviado">Enviados</option>
        </Selecao>
        {podeMarcar && marcados.length > 0 && (
          <Button size="sm" onClick={enviar}>
            Marcar {marcados.length} como enviado(s)
          </Button>
        )}
        <span className="campo__dica" style={{ marginTop: 0 }}>
          {cartoes.total} cartão(ões)
        </span>
      </div>

      {carregando ? (
        <Carregando>Carregando cartões...</Carregando>
      ) : cartoes.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhum cartão ainda"
          corpo="Os cartões aparecem aqui conforme os monitores os digitalizam."
        />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                {podeMarcar && <th />}
                <th>Criança</th>
                <th>Tipo</th>
                <th>Padrinho</th>
                <th>Situação</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {cartoes.itens.map((c) => (
                <tr key={c.id}>
                  {podeMarcar && (
                    <td>
                      <input
                        type="checkbox"
                        checked={marcados.includes(c.id)}
                        onChange={() => alternar(c.id)}
                        disabled={c.status === "enviado" || !c.padrinho_id}
                        aria-label={`Marcar cartão de ${c.crianca_nome}`}
                      />
                    </td>
                  )}
                  <td>
                    {c.crianca_nome}
                    <br />
                    <span className="campo__dica">{c.instituicao}</span>
                  </td>
                  <td>{c.tipo}</td>
                  <td>
                    {c.padrinho_nome ?? (
                      <span className="etiqueta etiqueta--espera">sem padrinho</span>
                    )}
                    {c.padrinho_whatsapp && <><br />{c.padrinho_whatsapp}</>}
                  </td>
                  <td>
                    <span className={`etiqueta ${c.status === "enviado" ? "etiqueta--ok" : "etiqueta--espera"}`}>
                      {c.status === "enviado" ? "Enviado" : "A enviar"}
                    </span>
                    {c.enviado_em && (
                      <><br /><span className="campo__dica">{formatarDataHora(c.enviado_em)}</span></>
                    )}
                  </td>
                  <td>
                    {/* Abre noutra aba: a imagem so sai por rota autenticada,
                        entao o cookie da sessao precisa ir junto. */}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => window.open(urlDaImagem(c.id), "_blank", "noopener")}
                    >
                      Ver imagem
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
