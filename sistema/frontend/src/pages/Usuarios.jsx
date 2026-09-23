import { useEffect, useMemo, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { listarEdicoes, listarInstituicoes, listarPerfis } from "../services/cadastros.js";
import {
  criarUsuario,
  editarUsuario,
  editarVinculo,
  gerarLinkDeAcesso,
  listarUsuarios,
} from "../services/usuarios.js";

// Estes perfis respondem por instituicoes especificas; os outros alcancam a
// edicao inteira. O backend usa a mesma regra — aqui e so para mostrar o campo.
const PERFIS_POR_INSTITUICAO = ["Comissario", "Monitor"];

const VAZIO = { nome: "", email: "", whatsapp: "", edicao_id: "", perfil_id: "", instituicoes: [] };

function LinkDeAcesso({ link, aoFechar }) {
  const [copiado, definirCopiado] = useState(false);
  const completo = `${window.location.origin}${link}`;

  async function copiar() {
    try {
      await navigator.clipboard.writeText(completo);
      definirCopiado(true);
      setTimeout(() => definirCopiado(false), 2000);
    } catch {
      // Navegador sem permissao para a area de transferencia: o link fica
      // visivel na tela para copiar a mao.
    }
  }

  return (
    <div className="painel painel--destaque">
      <h2 className="painel__titulo">Link de primeiro acesso</h2>
      <p className="campo__dica" style={{ marginTop: 0 }}>
        Envie este link à pessoa (por WhatsApp, por exemplo). Ele vale 72 horas e só
        pode ser usado uma vez. Não é possível vê-lo de novo depois de fechar — se
        perder, gere outro.
      </p>
      <div className="link-copiavel">
        <code>{completo}</code>
        <Button size="sm" onClick={copiar}>{copiado ? "Copiado!" : "Copiar"}</Button>
        <Button size="sm" variant="ghost" onClick={aoFechar}>Fechar</Button>
      </div>
    </div>
  );
}

export default function Usuarios() {
  const { usuario: eu } = useSessao();

  const [usuarios, definirUsuarios] = useState([]);
  const [edicoes, definirEdicoes] = useState([]);
  const [perfis, definirPerfis] = useState([]);
  const [instituicoes, definirInstituicoes] = useState([]);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");
  const [link, definirLink] = useState(null);

  const [formAberto, definirFormAberto] = useState(false);
  const [campos, definirCampos] = useState(VAZIO);
  const [salvando, definirSalvando] = useState(false);
  const [vinculoAberto, definirVinculoAberto] = useState(null);

  useEffect(() => {
    let vivo = true;
    Promise.all([listarUsuarios(), listarEdicoes(), listarPerfis(), listarInstituicoes()])
      .then(([us, eds, pfs, insts]) => {
        if (!vivo) return;
        definirUsuarios(us);
        definirEdicoes(eds);
        definirPerfis(pfs);
        definirInstituicoes(insts);
      })
      .catch((e) => vivo && definirErro(e.message))
      .finally(() => vivo && definirCarregando(false));
    return () => {
      vivo = false;
    };
  }, []);

  // Só a administração geral define coordenadores de cidade.
  const perfisDisponiveis = useMemo(
    () => perfis.filter((p) => eu?.admin_geral || p.nome !== "Coordenacao"),
    [perfis, eu],
  );

  const perfilEscolhido = perfis.find((p) => String(p.id) === String(campos.perfil_id));
  const pedeInstituicoes = PERFIS_POR_INSTITUICAO.includes(perfilEscolhido?.nome);

  const edicaoEscolhida = edicoes.find((e) => String(e.id) === String(campos.edicao_id));
  const instituicoesDaCidade = instituicoes.filter(
    (i) => i.cidade_id === edicaoEscolhida?.cidade_id,
  );

  function abrirNovo() {
    definirCampos({
      ...VAZIO,
      edicao_id: edicoes[0]?.id ?? "",
      perfil_id: perfisDisponiveis[0]?.id ?? "",
    });
    definirFormAberto(true);
    definirErro("");
    definirSucesso("");
    definirLink(null);
  }

  function mudar(campo, valor) {
    definirCampos((atual) => ({ ...atual, [campo]: valor }));
  }

  function alternarInstituicao(id) {
    definirCampos((atual) => ({
      ...atual,
      instituicoes: atual.instituicoes.includes(id)
        ? atual.instituicoes.filter((x) => x !== id)
        : [...atual.instituicoes, id],
    }));
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);

    try {
      const resultado = await criarUsuario(
        {
          nome: campos.nome.trim(),
          email: campos.email.trim(),
          whatsapp: campos.whatsapp.trim() || null,
        },
        {
          edicao_id: Number(campos.edicao_id),
          perfil_id: Number(campos.perfil_id),
          instituicoes: pedeInstituicoes ? campos.instituicoes : [],
        },
      );

      definirUsuarios((l) =>
        [...l, resultado.usuario].sort((a, b) => a.nome.localeCompare(b.nome)),
      );
      definirLink(resultado.link);
      definirSucesso(`${resultado.usuario.nome} cadastrado.`);
      definirFormAberto(false);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function novoLink(u) {
    definirErro("");
    try {
      const resultado = await gerarLinkDeAcesso(u.id);
      definirUsuarios((l) => l.map((x) => (x.id === u.id ? resultado.usuario : x)));
      definirLink(resultado.link);
      definirSucesso(`Link novo gerado para ${u.nome}.`);
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function alternarAtivo(u) {
    definirErro("");
    try {
      const atualizado = await editarUsuario(u.id, { ativo: !u.ativo });
      definirUsuarios((l) => l.map((x) => (x.id === u.id ? atualizado : x)));
    } catch (e) {
      definirErro(e.message);
    }
  }

  async function salvarInstituicoesDoVinculo(u, vinculo, ids) {
    definirErro("");
    try {
      const atualizado = await editarVinculo(u.id, vinculo.id, { instituicoes: ids });
      definirUsuarios((l) => l.map((x) => (x.id === u.id ? atualizado : x)));
      definirVinculoAberto(null);
      definirSucesso("Instituições atualizadas.");
    } catch (e) {
      definirErro(e.message);
    }
  }

  function situacao(u) {
    if (!u.ativo) return ["parado", "Desativado"];
    if (u.bloqueado) return ["parado", "Bloqueado"];
    if (!u.tem_senha) return ["espera", "Aguardando 1º acesso"];
    return ["ok", "Ativo"];
  }

  if (carregando) return <Carregando tela>Carregando usuários...</Carregando>;

  return (
    <div>
      <div className="pagina__eyebrow">Equipe</div>
      <h1 className="pagina__titulo">Usuários</h1>
      <p className="pagina__lede">
        As contas são criadas aqui e a pessoa define a própria senha pelo link de
        primeiro acesso. Comissários e monitores só alcançam as crianças das
        instituições atribuídas a eles.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      {link && <LinkDeAcesso link={link} aoFechar={() => definirLink(null)} />}

      <div className="barra-acoes">
        <Button onClick={abrirNovo} disabled={edicoes.length === 0}>
          Novo usuário
        </Button>
        {edicoes.length === 0 && (
          <span className="campo__dica">
            É preciso ter uma edição antes de cadastrar a equipe.
          </span>
        )}
      </div>

      {formAberto && (
        <form className="painel" onSubmit={salvar}>
          <h2 className="painel__titulo">Novo usuário</h2>

          <div className="linha-campos">
            <Entrada
              rotulo="Nome"
              value={campos.nome}
              onChange={(e) => mudar("nome", e.target.value)}
              required
            />
            <Entrada
              rotulo="Email"
              tipo="email"
              value={campos.email}
              onChange={(e) => mudar("email", e.target.value)}
              required
            />
            <Entrada
              rotulo="WhatsApp"
              value={campos.whatsapp}
              onChange={(e) => mudar("whatsapp", e.target.value)}
              dica="Opcional. É por onde o link costuma ser enviado."
            />
            <Selecao
              rotulo="Edição"
              value={campos.edicao_id}
              onChange={(e) => mudar("edicao_id", e.target.value)}
              required
            >
              {edicoes.map((e) => (
                <option key={e.id} value={e.id}>{e.nome}</option>
              ))}
            </Selecao>
            <Selecao
              rotulo="Perfil"
              value={campos.perfil_id}
              onChange={(e) => mudar("perfil_id", e.target.value)}
              required
            >
              {perfisDisponiveis.map((p) => (
                <option key={p.id} value={p.id}>{p.nome}</option>
              ))}
            </Selecao>
          </div>

          {pedeInstituicoes && (
            <div className="campo">
              <span className="campo__rotulo">Instituições sob responsabilidade</span>
              {instituicoesDaCidade.length === 0 ? (
                <span className="campo__dica">
                  Esta cidade ainda não tem instituições cadastradas.
                </span>
              ) : (
                <>
                  <div className="marcaveis">
                    {instituicoesDaCidade.map((i) => (
                      <label
                        key={i.id}
                        className={`marcavel ${campos.instituicoes.includes(i.id) ? "marcavel--marcado" : ""}`}
                      >
                        <input
                          type="checkbox"
                          checked={campos.instituicoes.includes(i.id)}
                          onChange={() => alternarInstituicao(i.id)}
                        />
                        {i.nome}
                      </label>
                    ))}
                  </div>
                  <span className="campo__dica">
                    Sem nenhuma marcada, a pessoa não alcança nenhuma criança.
                  </span>
                </>
              )}
            </div>
          )}

          <div className="barra-acoes barra-acoes--fim">
            <Button
              type="submit"
              carregando={salvando}
              disabled={!campos.nome.trim() || !campos.email.trim()}
            >
              {salvando ? "Criando..." : "Criar e gerar link"}
            </Button>
            <Button variant="ghost" onClick={() => definirFormAberto(false)} disabled={salvando}>
              Cancelar
            </Button>
          </div>
        </form>
      )}

      {usuarios.length === 0 ? (
        <EmptyState
          titulo="Nenhum usuário cadastrado"
          corpo="Cadastre a equipe: coordenação, comissários, monitores e estrutura."
        />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Contato</th>
                <th>Vínculos</th>
                <th>Situação</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {usuarios.map((u) => {
                const [tom, rotulo] = situacao(u);
                return (
                  <tr key={u.id}>
                    <td>
                      {u.nome}
                      {u.admin_geral && (
                        <>
                          {" "}
                          <span className="etiqueta etiqueta--neutra">Admin geral</span>
                        </>
                      )}
                    </td>
                    <td>
                      {u.email}
                      {u.whatsapp && <><br />{u.whatsapp}</>}
                    </td>
                    <td>
                      {u.vinculos.length === 0 ? (
                        "—"
                      ) : (
                        u.vinculos.map((v) => (
                          <div key={v.id} className="detalhe-vinculo">
                            <span className="detalhe-vinculo__edicao">
                              {v.cidade} {v.ano}
                            </span>
                            <span className="etiqueta etiqueta--neutra">{v.perfil}</span>
                            {v.filtrado_por_instituicao && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() =>
                                  definirVinculoAberto(
                                    vinculoAberto?.vinculo.id === v.id
                                      ? null
                                      : { usuario: u, vinculo: v, ids: [...v.instituicoes] },
                                  )
                                }
                              >
                                {v.instituicoes.length} instituição(ões)
                              </Button>
                            )}
                          </div>
                        ))
                      )}

                      {vinculoAberto?.usuario.id === u.id && (
                        <div className="painel" style={{ marginTop: "var(--space-3)" }}>
                          <div className="marcaveis">
                            {instituicoes
                              .filter((i) => {
                                const ed = edicoes.find(
                                  (e) => e.id === vinculoAberto.vinculo.edicao_id,
                                );
                                return i.cidade_id === ed?.cidade_id;
                              })
                              .map((i) => (
                                <label
                                  key={i.id}
                                  className={`marcavel ${vinculoAberto.ids.includes(i.id) ? "marcavel--marcado" : ""}`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={vinculoAberto.ids.includes(i.id)}
                                    onChange={() =>
                                      definirVinculoAberto((atual) => ({
                                        ...atual,
                                        ids: atual.ids.includes(i.id)
                                          ? atual.ids.filter((x) => x !== i.id)
                                          : [...atual.ids, i.id],
                                      }))
                                    }
                                  />
                                  {i.nome}
                                </label>
                              ))}
                          </div>
                          <div className="barra-acoes barra-acoes--fim">
                            <Button
                              size="sm"
                              onClick={() =>
                                salvarInstituicoesDoVinculo(
                                  u,
                                  vinculoAberto.vinculo,
                                  vinculoAberto.ids,
                                )
                              }
                            >
                              Salvar
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => definirVinculoAberto(null)}>
                              Cancelar
                            </Button>
                          </div>
                        </div>
                      )}
                    </td>
                    <td>
                      <span className={`etiqueta etiqueta--${tom}`}>{rotulo}</span>
                    </td>
                    <td>
                      <div className="barra-acoes" style={{ margin: 0 }}>
                        <Button size="sm" variant="ghost" onClick={() => novoLink(u)}>
                          Gerar link
                        </Button>
                        {u.id !== eu?.id && (
                          <Button size="sm" variant="ghost" onClick={() => alternarAtivo(u)}>
                            {u.ativo ? "Desativar" : "Ativar"}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
