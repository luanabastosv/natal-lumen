import { useEffect, useMemo, useState } from "react";
import Rabisco from "../components/core/Rabisco.jsx";
import Button from "../components/core/Button.jsx";
import MenuAcoes from "../components/core/MenuAcoes.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import EditarUsuario from "../components/dados/EditarUsuario.jsx";
import {
  pedeGrupo as perfilPedeGrupo,
  pedeInstituicoes as perfilPedeInstituicoes,
  PERFIL_COORDENACAO,
  rotuloDoPerfil,
  valeCidadeInteira,
} from "../components/dados/perfis.js";
import Carregando from "../components/feedback/Carregando.jsx";
import ConfirmarExclusao from "../components/feedback/ConfirmarExclusao.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import { listarGrupos, listarInstituicoes, listarPerfis } from "../services/cadastros.js";
import {
  apagarUsuario,
  criarUsuario,
  dependenciasDoUsuario,
  editarUsuario,
  gerarLinkDeAcesso,
  listarUsuarios,
} from "../services/usuarios.js";
import { formatarDataHora, tempoDesde } from "../utils/dinheiro.js";

/* O que a janela de exclusao diz alem da conta. Desativar guarda o historico e
   e quase sempre o caminho certo; apagar existe para a conta que nunca deveria
   ter existido. */
const NOTA_USUARIO =
  "Se a pessoa apenas saiu da equipe, desative a conta em vez de apagar — isso " +
  "guarda quem fez o quê. As crianças que estavam no nome dela continuam " +
  "cadastradas, mas ficam sem responsável.";

const VAZIO = {
  nome: "",
  email: "",
  whatsapp: "",
  perfil_id: "",
  instituicoes: [],
  grupo: "",
};

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
        <Button variant="secondary" size="sm" onClick={copiar}>{copiado ? "Copiado!" : "Copiar"}</Button>
        <Button size="sm" variant="ghost" onClick={aoFechar}>Fechar</Button>
      </div>
    </div>
  );
}

export default function Usuarios() {
  // A edicao vem da lateral: a conta nasce na edicao que esta sendo vista, e a
  // lista mostra a equipe dessa mesma edicao.
  const { usuario: eu, edicoes, edicao, edicaoAtiva } = useSessao();

  const [usuarios, definirUsuarios] = useState([]);
  const [perfis, definirPerfis] = useState([]);
  const [instituicoes, definirInstituicoes] = useState([]);
  const [grupos, definirGrupos] = useState([]);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const notificar = useNotificar();
  const [link, definirLink] = useState(null);

  const [formAberto, definirFormAberto] = useState(false);
  const [campos, definirCampos] = useState(VAZIO);
  const [salvando, definirSalvando] = useState(false);
  const [editando, definirEditando] = useState(null);

  // A exclusao em curso: { registro, dependencias, erro, apagando }. Num estado
  // so porque as quatro coisas andam juntas.
  const [exclusao, definirExclusao] = useState(null);

  useEffect(() => {
    let vivo = true;
    Promise.all([listarUsuarios(), listarPerfis(), listarInstituicoes(), listarGrupos()])
      .then(([us, pfs, insts, grps]) => {
        if (!vivo) return;
        definirUsuarios(us);
        definirPerfis(pfs);
        definirInstituicoes(insts);
        definirGrupos(grps);
      })
      .catch((e) => vivo && definirErro(e.message))
      .finally(() => vivo && definirCarregando(false));
    return () => {
      vivo = false;
    };
  }, []);

  // Só a administração geral define coordenadores de cidade — a coordenação é
  // o perfil que alcança a cidade inteira, e quem o distribui é quem está acima
  // dela. O servidor confere o mesmo; aqui é só não oferecer o que seria negado.
  const perfisDisponiveis = useMemo(
    () => perfis.filter((p) => eu?.admin_geral || p.nome !== PERFIL_COORDENACAO),
    [perfis, eu],
  );

  const perfilEscolhido = perfis.find((p) => String(p.id) === String(campos.perfil_id));
  const pedeInstituicoes = perfilPedeInstituicoes(perfilEscolhido);

  const pedeGrupo = perfilPedeGrupo(perfilEscolhido);

  // Coordenacao e da cidade: a gravacao alcanca as outras edicoes ativas dela,
  // e a tela tem de dizer isso antes de o botao ser apertado.
  const valeCidade = valeCidadeInteira(perfilEscolhido);

  const instituicoesDaCidade = instituicoes.filter(
    (i) => i.cidade_id === edicao?.cidade_id,
  );

  // Sugestoes do campo de grupo: os que ja existem NESTA cidade. O grupo e da
  // cidade e atravessa os anos, entao a edicao nova ja abre com os de sempre.
  const gruposDaCidade = grupos
    .filter((g) => g.cidade_id === edicao?.cidade_id)
    .map((g) => g.nome);

  /** Guarda na lista de sugestoes o grupo que acabou de nascer.
   *
   *  O grupo e criado pelo servidor junto com o vinculo, e volta na resposta.
   *  Sem isto, o proximo comissario cadastrado na mesma sessao nao veria a
   *  sugestao e escreveria o nome de novo — que e exatamente o caminho para as
   *  duas grafias do mesmo grupo. */
  function guardarGrupos(atualizado) {
    const novos = atualizado.vinculos.filter((v) => v.grupo_id && v.grupo);
    if (!novos.length) return;
    definirGrupos((lista) => {
      const conhecidos = new Set(lista.map((g) => g.id));
      const faltando = novos
        .filter((v) => !conhecidos.has(v.grupo_id))
        .map((v) => ({
          id: v.grupo_id,
          nome: v.grupo,
          cidade_id: edicoes.find((e) => e.id === v.edicao_id)?.cidade_id,
        }));
      return faltando.length
        ? [...lista, ...faltando].sort((a, b) => a.nome.localeCompare(b.nome))
        : lista;
    });
  }

  // A equipe DESTA edicao. As contas de administracao geral ficam sempre a
  // vista: elas alcancam todas as cidades e nao tem vinculo com nenhuma, entao
  // filtrar por edicao as faria sumir da tela de quem precisa gerencia-las.
  const daEdicao = useMemo(
    () =>
      usuarios.filter(
        (u) => u.admin_geral || u.vinculos.some((v) => v.edicao_id === edicaoAtiva),
      ),
    [usuarios, edicaoAtiva],
  );

  function abrirNovo() {
    definirCampos({ ...VAZIO, perfil_id: perfisDisponiveis[0]?.id ?? "" });
    definirFormAberto(true);
    definirErro("");
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
          edicao_id: Number(edicaoAtiva),
          perfil_id: Number(campos.perfil_id),
          instituicoes: pedeInstituicoes ? campos.instituicoes : [],
          grupo: pedeGrupo ? campos.grupo.trim() || null : null,
        },
      );

      definirUsuarios((l) =>
        [...l, resultado.usuario].sort((a, b) => a.nome.localeCompare(b.nome)),
      );
      guardarGrupos(resultado.usuario);
      definirLink(resultado.link);
      notificar(`${resultado.usuario.nome} cadastrado.`);
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
      notificar(`Link novo gerado para ${u.nome}.`);
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

  function abrirEdicao(u) {
    definirErro("");
    definirEditando(u);
  }

  function guardarEdicao(atualizado) {
    definirUsuarios((l) => l.map((x) => (x.id === atualizado.id ? atualizado : x)));
    guardarGrupos(atualizado);
    definirEditando(null);
    notificar(`${atualizado.nome} atualizado.`);
  }

  /** Abre a janela e ja pergunta ao servidor o que vai junto. */
  async function pedirExclusao(u) {
    definirErro("");
    definirExclusao({ registro: u, dependencias: null, erro: "", apagando: false });
    try {
      const conta = await dependenciasDoUsuario(u.id);
      definirExclusao((atual) =>
        atual && atual.registro.id === u.id ? { ...atual, dependencias: conta } : atual,
      );
    } catch (e) {
      definirExclusao((atual) => (atual ? { ...atual, erro: e.message } : atual));
    }
  }

  async function confirmarExclusao() {
    const u = exclusao.registro;
    definirExclusao((atual) => ({ ...atual, apagando: true, erro: "" }));
    try {
      await apagarUsuario(u.id);
      definirUsuarios((l) => l.filter((x) => x.id !== u.id));
      notificar(`${u.nome} apagado.`);
      definirExclusao(null);
    } catch (e) {
      definirExclusao((atual) =>
        atual ? { ...atual, apagando: false, erro: e.message } : atual,
      );
    }
  }

  /** Os nomes das instituicoes de um vinculo, para a linha de baixo da coluna
   *  Equipe. Comissario sem nenhuma nao alcanca crianca alguma — isso precisa
   *  aparecer, e nao como uma celula vazia que se le como "ainda nao vi". */
  function instituicoesDoVinculo(vinculo) {
    if (vinculo.instituicoes.length === 0) return "Nenhuma instituição atribuída";
    return vinculo.instituicoes
      .map((id) => instituicoes.find((i) => i.id === id)?.nome)
      .filter(Boolean)
      .join(" · ");
  }

  function situacao(u) {
    if (!u.ativo) return ["parado", "Desativado"];
    if (u.bloqueado) return ["parado", "Bloqueado"];
    if (!u.tem_senha) return ["espera", "Aguardando 1º acesso"];
    return ["ok", "Ativo"];
  }

  /* A linha de apoio da coluna Situacao. A etiqueta diz se a conta funciona;
     esta linha diz se a pessoa anda entrando — sao duas perguntas diferentes
     sobre a mesma conta, e a segunda e a que revela quem nunca comecou.

     Volta nulo quando a etiqueta ja respondeu: "Aguardando 1º acesso" nao
     precisa de um "Nunca acessou" logo embaixo dizendo o mesmo. */
  function ultimoAcesso(u) {
    if (u.ultimo_login) return `Entrou ${tempoDesde(u.ultimo_login)}`;
    return u.tem_senha ? "Nunca acessou" : null;
  }

  if (carregando) return <Carregando tela>Carregando usuários...</Carregando>;

  return (
    <div>
      <div className="pagina__cabecalho">
        <div className="pagina__texto">
          <div className="pagina__eyebrow">Equipe</div>
          <h1 className="pagina__titulo">Usuários</h1>
          <Rabisco className="pagina__onda" />
          <p className="pagina__lede">
            A equipe da edição escolhida na lateral. Cada pessoa define a própria senha
            pelo link de primeiro acesso; comissários e monitores só alcançam as
            instituições atribuídas a eles.
          </p>
        </div>

        <div className="pagina__acoes">
          <Button onClick={abrirNovo} disabled={!edicaoAtiva}>
            Novo usuário
          </Button>
        </div>
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {link && <LinkDeAcesso link={link} aoFechar={() => definirLink(null)} />}

      {/* So no caso em que o botao esta desligado. */}
      {!edicaoAtiva && (
        <div className="barra-acoes">
          <span className="campo__dica">
            É preciso ter uma edição antes de cadastrar a equipe.
          </span>
        </div>
      )}

      {formAberto && (
        <form className="painel" onSubmit={salvar}>
          <h2 className="painel__titulo">
            Novo usuário{edicao && <> · {edicao.cidade} {edicao.ano}</>}
          </h2>

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
              rotulo="Tipo"
              value={campos.perfil_id}
              onChange={(e) => mudar("perfil_id", e.target.value)}
              required
            >
              {perfisDisponiveis.map((p) => (
                <option key={p.id} value={p.id}>{rotuloDoPerfil(p.nome)}</option>
              ))}
            </Selecao>
          </div>

          {valeCidade && (
            <span className="campo__dica">
              A coordenação é da <strong>cidade</strong>, não do ano: a pessoa
              passa a alcançar todas as edições ativas de {edicao?.cidade}, e toda
              edição nova da cidade já nasce com ela dentro.
            </span>
          )}

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

          {pedeGrupo && (
            <div className="linha-campos">
              <Entrada
                rotulo="Grupo na comunidade"
                value={campos.grupo}
                onChange={(e) => mudar("grupo", e.target.value)}
                sugestoes={gruposDaCidade}
                dica="O grupo do comissário na comunidade. Se ele já apareceu antes nesta cidade, escolha da lista — assim não vira dois."
              />
            </div>
          )}

          <div className="barra-acoes barra-acoes--fim">
            <Button
              variant="secondary"
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

      {daEdicao.length === 0 ? (
        <EmptyState
          titulo="Nenhum usuário nesta edição"
          corpo="Cadastre a equipe: coordenação, comissários, monitores e estrutura."
        />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Contato</th>
                <th>Equipe</th>
                <th>Edição vinculada</th>
                <th>Situação</th>
                <th className="tabela__acoes" />
              </tr>
            </thead>
            <tbody>
              {daEdicao.map((u) => {
                const [tom, rotulo] = situacao(u);
                const acesso = ultimoAcesso(u);
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
                    {/* Equipe e edicao sao duas colunas, e cada vinculo e uma
                        linha dentro das duas — o que a pessoa faz de um lado,
                        onde ela faz do outro. */}
                    <td>
                      {u.admin_geral ? (
                        <div className="vinculo-linha">
                          <span className="vinculo-linha__titulo">Administração geral</span>
                          <span className="vinculo-linha__detalhe">
                            Alcança todas as cidades
                          </span>
                        </div>
                      ) : u.vinculos.length === 0 ? (
                        "—"
                      ) : (
                        u.vinculos.map((v) => (
                          <div key={v.id} className="vinculo-linha">
                            <span className="vinculo-linha__titulo">
                              {rotuloDoPerfil(v.perfil)}
                              {!v.ativo && (
                                <span className="etiqueta etiqueta--parado">Suspenso</span>
                              )}
                            </span>
                            {v.filtrado_por_instituicao && (
                              <span className="vinculo-linha__detalhe">
                                {instituicoesDoVinculo(v)}
                              </span>
                            )}
                            {v.usa_grupo && (
                              <span className="vinculo-linha__detalhe">
                                {v.grupo ? `Grupo ${v.grupo}` : "Sem grupo nomeado"}
                              </span>
                            )}
                          </div>
                        ))
                      )}
                    </td>

                    <td>
                      {u.admin_geral ? (
                        <div className="vinculo-linha">
                          <span className="vinculo-linha__titulo">Todas as edições</span>
                        </div>
                      ) : u.vinculos.length === 0 ? (
                        "—"
                      ) : (
                        u.vinculos.map((v) => (
                          <div key={v.id} className="vinculo-linha">
                            <span className="vinculo-linha__titulo">
                              {v.cidade} {v.ano}
                            </span>
                          </div>
                        ))
                      )}
                    </td>

                    <td>
                      <div className="situacao">
                        <span className={`etiqueta etiqueta--${tom}`}>{rotulo}</span>
                        {acesso && (
                          <span
                            className="situacao__acesso"
                            title={
                              u.ultimo_login ? formatarDataHora(u.ultimo_login) : undefined
                            }
                          >
                            {acesso}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="tabela__acoes">
                      <MenuAcoes
                        titulo={`Ações de ${u.nome}`}
                        itens={[
                          { rotulo: "Editar", aoEscolher: () => abrirEdicao(u) },
                          { rotulo: "Gerar link", aoEscolher: () => novoLink(u) },
                          // Ninguem se desativa nem se apaga: quem fizesse isso
                          // se trancaria para fora do sistema no clique seguinte.
                          u.id !== eu?.id && {
                            rotulo: u.ativo ? "Desativar" : "Ativar",
                            aoEscolher: () => alternarAtivo(u),
                          },
                          u.id !== eu?.id && {
                            rotulo: "Apagar",
                            perigo: true,
                            aoEscolher: () => pedirExclusao(u),
                          },
                        ]}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {editando && (
        <EditarUsuario
          usuario={editando}
          edicoes={edicoes}
          perfis={perfis}
          perfisPermitidos={perfisDisponiveis}
          instituicoes={instituicoes}
          grupos={grupos}
          aoSalvar={guardarEdicao}
          aoFechar={() => definirEditando(null)}
        />
      )}

      {exclusao && (
        <ConfirmarExclusao
          rotulo="Usuário"
          nome={exclusao.registro.nome}
          dependencias={exclusao.dependencias}
          nota={NOTA_USUARIO}
          erro={exclusao.erro}
          apagando={exclusao.apagando}
          aoConfirmar={confirmarExclusao}
          aoFechar={() => definirExclusao(null)}
        />
      )}
    </div>
  );
}
