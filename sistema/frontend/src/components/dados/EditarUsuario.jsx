import { useState } from "react";
import Button from "../core/Button.jsx";
import { Entrada, Selecao } from "../core/Campo.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import { criarVinculo, editarUsuario, editarVinculo } from "../../services/usuarios.js";
import {
  PERFIL_COORDENACAO,
  pedeGrupo,
  pedeInstituicoes,
  rotuloDoPerfil,
  valeCidadeInteira,
} from "./perfis.js";

function mesmaLista(a, b) {
  return a.length === b.length && [...a].sort().join() === [...b].sort().join();
}

/** O recado que a tela precisa dar quando o tipo escolhido e coordenacao.
 *
 *  A tela pede uma edicao, como para todo mundo, mas a gravacao alcanca mais do
 *  que isso — e uma mudanca que acontece fora do campo que a pessoa mexeu.
 *  Escondido, o acesso apareceria sozinho em 2027 e ninguem saberia de onde.
 */
function AvisoCidadeInteira() {
  return (
    <span className="campo__dica">
      A coordenação é da <strong>cidade</strong>, não do ano: este acesso passa a
      valer em todas as edições ativas dela, e toda edição nova da cidade já
      nasce com a pessoa dentro. Suspender aqui suspende na cidade inteira.
    </span>
  );
}

/** Uma edicao em que a pessoa trabalha: o tipo dela ali e, se o tipo pedir, as
 *  instituicoes por que responde.
 *
 *  O tipo manda no resto do bloco. Trocar de Comissario para Coordenacao faz as
 *  instituicoes sumirem na hora — e nao e so a tela: coordenacao alcanca a
 *  edicao inteira, entao a lista deixa de querer dizer alguma coisa e vai
 *  embora na gravacao tambem.
 */
function BlocoVinculo({
  titulo,
  rascunho,
  perfis,
  instituicoesDaCidade,
  // Os grupos ja usados nesta cidade. Sao sugestao, nao lista fechada: o
  // primeiro grupo de uma cidade precisa poder ser escrito do zero.
  gruposDaCidade,
  mudar,
  // So o vinculo novo escolhe a edicao: mudar a edicao de um que ja existe
  // seria apagar um acesso e criar outro, e nao uma edicao de campo.
  edicoesPossiveis,
  podeSuspender = true,
  // Vinculo que este gestor ve mas nao mexe. Mostrado assim mesmo, e nao
  // escondido: sumir com ele faria a equipe da edicao parecer menor do que e.
  travado = false,
  aoRemover,
}) {
  const perfil = perfis.find((p) => String(p.id) === String(rascunho.perfil_id));
  const mostraInstituicoes = pedeInstituicoes(perfil);
  const mostraGrupo = pedeGrupo(perfil);
  const valeCidade = valeCidadeInteira(perfil);

  function alternarInstituicao(id) {
    mudar(
      "instituicoes",
      rascunho.instituicoes.includes(id)
        ? rascunho.instituicoes.filter((x) => x !== id)
        : [...rascunho.instituicoes, id],
    );
  }

  if (travado) {
    return (
      <div className="painel">
        <h3 className="painel__titulo" style={{ margin: 0 }}>{titulo}</h3>
        <span className="campo__dica">
          {rotuloDoPerfil(perfil?.nome)} — a coordenação vale para a cidade
          inteira, e quem a define é a administração geral.
        </span>
      </div>
    );
  }

  return (
    <div className="painel">
      <div className="barra-acoes" style={{ marginBottom: "var(--space-3)" }}>
        <h3 className="painel__titulo" style={{ margin: 0 }}>{titulo}</h3>
        {aoRemover && (
          <div className="barra-acoes__ponta">
            <Button size="sm" variant="ghost" onClick={aoRemover}>Descartar</Button>
          </div>
        )}
      </div>

      <div className="linha-campos">
        {edicoesPossiveis && (
          <Selecao
            rotulo="Edição"
            value={rascunho.edicao_id}
            onChange={(e) => mudar("edicao_id", e.target.value)}
          >
            {edicoesPossiveis.map((e) => (
              <option key={e.id} value={e.id}>{e.cidade} {e.ano}</option>
            ))}
          </Selecao>
        )}

        <Selecao
          rotulo="Tipo"
          value={rascunho.perfil_id}
          onChange={(e) => mudar("perfil_id", e.target.value)}
          dica="O que a pessoa alcança nesta edição."
        >
          {perfis.map((p) => (
            <option key={p.id} value={p.id}>{rotuloDoPerfil(p.nome)}</option>
          ))}
        </Selecao>

        {podeSuspender && (
          <Selecao
            rotulo="Acesso a esta edição"
            value={rascunho.ativo ? "sim" : "nao"}
            onChange={(e) => mudar("ativo", e.target.value === "sim")}
            dica="Suspenso, a conta continua existindo e não alcança esta edição."
          >
            <option value="sim">Liberado</option>
            <option value="nao">Suspenso</option>
          </Selecao>
        )}
      </div>

      {valeCidade && <AvisoCidadeInteira />}

      {mostraInstituicoes && (
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
                    className={`marcavel ${rascunho.instituicoes.includes(i.id) ? "marcavel--marcado" : ""}`}
                  >
                    <input
                      type="checkbox"
                      checked={rascunho.instituicoes.includes(i.id)}
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

      {mostraGrupo && (
        <div className="linha-campos">
          <Entrada
            rotulo="Grupo na comunidade"
            value={rascunho.grupo}
            onChange={(e) => mudar("grupo", e.target.value)}
            sugestoes={gruposDaCidade}
            dica="Se o grupo já apareceu antes nesta cidade, escolha da lista — assim ele não vira dois."
          />
        </div>
      )}
    </div>
  );
}

/** Janela unica de edicao de um usuario: os dados da conta em cima, um bloco
 *  por edicao em que ele trabalha embaixo.
 *
 *  Tudo aqui dentro, e nao espalhado pela linha da tabela, porque as escolhas
 *  dependem umas das outras: o tipo decide se ha instituicoes, e a edicao
 *  decide QUAIS instituicoes existem para escolher. Separadas, cada uma pediria
 *  a outra de volta.
 *
 *  A gravacao manda so o que mudou, e em chamadas separadas — a conta numa
 *  rota, cada vinculo na sua. A ultima resposta e a que vale: todas devolvem o
 *  usuario inteiro, ja com o efeito das anteriores.
 */
export default function EditarUsuario({
  usuario,
  edicoes,
  // Todos os perfis, e os que ESTE gestor pode atribuir. Sao listas diferentes:
  // so a administracao geral define coordenadores de cidade.
  perfis,
  perfisPermitidos,
  instituicoes,
  grupos,
  aoSalvar,
  aoFechar,
}) {
  const [conta, definirConta] = useState(() => ({
    nome: usuario.nome,
    whatsapp: usuario.whatsapp ?? "",
    ativo: usuario.ativo,
  }));

  const [vinculos, definirVinculos] = useState(() =>
    usuario.vinculos.map((v) => ({
      id: v.id,
      edicao_id: v.edicao_id,
      perfil_id: v.perfil_id,
      ativo: v.ativo,
      instituicoes: [...v.instituicoes],
      grupo: v.grupo ?? "",
    })),
  );

  // Vinculo que ainda nao existe no servidor. Um de cada vez: duas edicoes
  // novas ao mesmo tempo so multiplicariam as formas de errar.
  const [novo, definirNovo] = useState(null);

  const [erro, definirErro] = useState("");
  const [salvando, definirSalvando] = useState(false);

  // Quem nao pode ATRIBUIR coordenacao tambem nao mexe num vinculo que ja e
  // de coordenacao: suspende-lo tiraria o acesso da cidade inteira. A lista de
  // perfis permitidos ja diz quem e quem — nao precisa de outra pergunta.
  const mexeNaCoordenacao = perfisPermitidos.some(
    (p) => p.nome === PERFIL_COORDENACAO,
  );

  function eDeCoordenacao(perfilId) {
    return perfis.find((p) => p.id === perfilId)?.nome === PERFIL_COORDENACAO;
  }

  const jaVinculadas = new Set(vinculos.map((v) => v.edicao_id));
  const edicoesLivres = edicoes.filter((e) => !jaVinculadas.has(e.id));
  // A escolhida continua na lista enquanto o bloco esta aberto; as outras sao
  // as que ainda nao tem vinculo.
  const edicoesParaONovo = edicoesLivres;

  function instituicoesDaEdicao(edicaoId) {
    const edicao = edicoes.find((e) => String(e.id) === String(edicaoId));
    return instituicoes.filter((i) => i.cidade_id === edicao?.cidade_id);
  }

  function gruposDaEdicao(edicaoId) {
    const edicao = edicoes.find((e) => String(e.id) === String(edicaoId));
    return grupos.filter((g) => g.cidade_id === edicao?.cidade_id).map((g) => g.nome);
  }

  function nomeDaEdicao(edicaoId) {
    const edicao = edicoes.find((e) => String(e.id) === String(edicaoId));
    return edicao ? `${edicao.cidade} ${edicao.ano}` : "Edição";
  }

  /** As opcoes do seletor de tipo deste vinculo.
   *
   *  O perfil que ele ja tem entra sempre, mesmo que este gestor nao pudesse
   *  atribui-lo: fora da lista, o seletor abriria numa opcao qualquer e salvar
   *  rebaixaria um coordenador sem ninguem ter pedido.
   */
  function opcoesDeTipo(perfilIdAtual) {
    if (perfisPermitidos.some((p) => p.id === perfilIdAtual)) return perfisPermitidos;
    const atual = perfis.find((p) => p.id === perfilIdAtual);
    return atual ? [atual, ...perfisPermitidos] : perfisPermitidos;
  }

  function mudarVinculo(id, campo, valor) {
    definirVinculos((lista) =>
      lista.map((v) => (v.id === id ? { ...v, [campo]: valor } : v)),
    );
  }

  function abrirNovo() {
    const edicao = edicoesLivres[0];
    if (!edicao) return;
    definirNovo({
      edicao_id: edicao.id,
      perfil_id: perfisPermitidos[0]?.id ?? "",
      ativo: true,
      instituicoes: [],
      grupo: "",
    });
  }

  /** O que mandar para esta edicao, ou null se nada mudou. */
  function mudancasDoVinculo(rascunho) {
    const antes = usuario.vinculos.find((v) => v.id === rascunho.id);
    const perfil = perfis.find((p) => String(p.id) === String(rascunho.perfil_id));
    // Tipo que nao e por instituicao nao guarda lista: manda vazia e o servidor
    // solta as criancas que estavam no nome dele.
    const lista = pedeInstituicoes(perfil) ? rascunho.instituicoes : [];
    // Mesma logica para o grupo: quem deixou de ser comissario nao guarda o
    // nome do grupo. O servidor ja limparia sozinho na troca de perfil — o
    // vazio aqui e para o pedido dizer a mesma coisa que a tela mostra.
    const grupo = pedeGrupo(perfil) ? rascunho.grupo.trim() : "";

    const mudancas = {};
    if (Number(rascunho.perfil_id) !== antes.perfil_id) {
      mudancas.perfil_id = Number(rascunho.perfil_id);
    }
    if (rascunho.ativo !== antes.ativo) mudancas.ativo = rascunho.ativo;
    if (!mesmaLista(lista, antes.instituicoes)) mudancas.instituicoes = lista;
    if (grupo !== (antes.grupo ?? "")) mudancas.grupo = grupo || null;

    return Object.keys(mudancas).length ? mudancas : null;
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);

    try {
      let atualizado = usuario;

      const mudancasDaConta = {};
      const nome = conta.nome.trim();
      const whatsapp = conta.whatsapp.trim() || null;
      if (nome !== usuario.nome) mudancasDaConta.nome = nome;
      if (whatsapp !== (usuario.whatsapp ?? null)) mudancasDaConta.whatsapp = whatsapp;
      if (conta.ativo !== usuario.ativo) mudancasDaConta.ativo = conta.ativo;

      if (Object.keys(mudancasDaConta).length) {
        atualizado = await editarUsuario(usuario.id, mudancasDaConta);
      }

      for (const rascunho of vinculos) {
        const mudancas = mudancasDoVinculo(rascunho);
        if (mudancas) {
          atualizado = await editarVinculo(usuario.id, rascunho.id, mudancas);
        }
      }

      if (novo) {
        const perfil = perfis.find((p) => String(p.id) === String(novo.perfil_id));
        atualizado = await criarVinculo(usuario.id, {
          edicao_id: Number(novo.edicao_id),
          perfil_id: Number(novo.perfil_id),
          instituicoes: pedeInstituicoes(perfil) ? novo.instituicoes : [],
          grupo: pedeGrupo(perfil) ? novo.grupo.trim() || null : null,
        });
      }

      aoSalvar(atualizado);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  return (
    <Modal
      rotulo="Usuário"
      titulo={usuario.nome}
      tamanho="grande"
      aoFechar={() => !salvando && aoFechar()}
      rodape={
        <div className="barra-acoes barra-acoes--fim" style={{ marginTop: 0 }}>
          <Button
            variant="secondary"
            onClick={salvar}
            carregando={salvando}
            disabled={!conta.nome.trim()}
          >
            {salvando ? "Salvando..." : "Salvar"}
          </Button>
          <Button variant="ghost" onClick={aoFechar} disabled={salvando}>
            Cancelar
          </Button>
        </div>
      }
    >
      <Mensagem tipo="erro">{erro}</Mensagem>

      <form onSubmit={salvar}>
        <div className="linha-campos">
          <Entrada
            rotulo="Nome"
            value={conta.nome}
            onChange={(e) => definirConta({ ...conta, nome: e.target.value })}
            required
          />
          <Entrada
            rotulo="WhatsApp"
            value={conta.whatsapp}
            onChange={(e) => definirConta({ ...conta, whatsapp: e.target.value })}
            dica="Opcional. É por onde o link de acesso costuma ser enviado."
          />
          <Selecao
            rotulo="Situação da conta"
            value={conta.ativo ? "sim" : "nao"}
            onChange={(e) => definirConta({ ...conta, ativo: e.target.value === "sim" })}
            dica="Desativada, a pessoa não consegue entrar no sistema."
          >
            <option value="sim">Ativa</option>
            <option value="nao">Desativada</option>
          </Selecao>
        </div>

        {/* O email nao se edita: e com ele que a pessoa entra, e trocar por
            aqui deixaria a conta sem dono se o endereco novo estivesse errado.
            Caso de email errado e conta nova. */}
        <p className="campo__dica">
          Entra com <strong>{usuario.email}</strong>. O email não muda — se estiver
          errado, apague esta conta e cadastre de novo.
        </p>

        {usuario.admin_geral ? (
          <Mensagem tipo="aviso">
            Administração geral alcança todas as cidades e edições, sem vínculo com
            nenhuma em particular.
          </Mensagem>
        ) : (
          <>
            {vinculos.length === 0 && !novo && (
              <p className="campo__dica">
                Esta conta não está em nenhuma edição — hoje ela entra no sistema e
                não alcança nada.
              </p>
            )}

            {vinculos.map((v) => (
              <BlocoVinculo
                key={v.id}
                titulo={nomeDaEdicao(v.edicao_id)}
                rascunho={v}
                perfis={opcoesDeTipo(v.perfil_id)}
                instituicoesDaCidade={instituicoesDaEdicao(v.edicao_id)}
                gruposDaCidade={gruposDaEdicao(v.edicao_id)}
                mudar={(campo, valor) => mudarVinculo(v.id, campo, valor)}
                travado={!mexeNaCoordenacao && eDeCoordenacao(v.perfil_id)}
              />
            ))}

            {novo && (
              <BlocoVinculo
                titulo="Novo vínculo"
                rascunho={novo}
                perfis={perfisPermitidos}
                instituicoesDaCidade={instituicoesDaEdicao(novo.edicao_id)}
                gruposDaCidade={gruposDaEdicao(novo.edicao_id)}
                edicoesPossiveis={edicoesParaONovo}
                mudar={(campo, valor) =>
                  definirNovo((atual) => ({
                    ...atual,
                    [campo]: valor,
                    // Instituicao pertence a cidade: trocar de edicao pode
                    // trocar de cidade, e a lista anterior deixa de existir.
                    ...(campo === "edicao_id" ? { instituicoes: [], grupo: "" } : {}),
                  }))
                }
                podeSuspender={false}
                aoRemover={() => definirNovo(null)}
              />
            )}

            {!novo && edicoesLivres.length > 0 && (
              <Button size="sm" variant="ghost" onClick={abrirNovo}>
                Adicionar a outra edição
              </Button>
            )}
          </>
        )}
      </form>
    </Modal>
  );
}
