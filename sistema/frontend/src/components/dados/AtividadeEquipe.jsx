import { useEffect, useState } from "react";
import Button from "../core/Button.jsx";
import Carregando from "../feedback/Carregando.jsx";
import EmptyState from "../feedback/EmptyState.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import useTelaEstreita from "../../hooks/useTelaEstreita.js";
import { buscarAtividade, buscarAtividadeDaPessoa } from "../../services/painel.js";
import { tempoDesde } from "../../utils/dinheiro.js";

/* Dias sem acessar a partir dos quais a pessoa aparece como parada. */
const PARADO_DIAS = 3;

const hora = (iso) =>
  new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

/** Dias de calendario desde `iso` — a mesma conta do "há N dias" ao lado, para
 *  as duas nao discordarem por causa da hora. */
function diasDesde(iso) {
  if (!iso) return null;
  const dia = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  return Math.round((dia(new Date()) - dia(new Date(iso))) / 86400000);
}

/** "hoje, 14:32" / "ontem, 09:10" / "há 3 dias" — o quando de uma linha. */
function quando(iso) {
  if (!iso) return null;
  const relativo = tempoDesde(iso);
  return relativo === "hoje" || relativo === "ontem" ? `${relativo}, ${hora(iso)}` : relativo;
}

/** O alerta da pessoa, se ha: nunca entrou, ou entrou e sumiu. */
function Situacao({ pessoa }) {
  if (pessoa.sem_senha) {
    return <span className="etiqueta etiqueta--parado">Não criou senha</span>;
  }
  if (!pessoa.ultimo_acesso) {
    return <span className="etiqueta etiqueta--parado">Nunca entrou</span>;
  }
  const dias = diasDesde(pessoa.ultimo_acesso);
  if (dias >= PARADO_DIAS) {
    return <span className="etiqueta etiqueta--espera">Sem entrar há {dias} dias</span>;
  }
  return null;
}

/** "Hoje", "Ontem" ou a data: o cabecalho de cada dia da linha do tempo. */
function rotuloDoDia(iso) {
  const relativo = tempoDesde(iso);
  if (relativo === "hoje") return "Hoje";
  if (relativo === "ontem") return "Ontem";
  return new Date(iso).toLocaleDateString("pt-BR", {
    weekday: "long", day: "2-digit", month: "2-digit",
  });
}

function porDia(itens) {
  const dias = [];
  for (const item of itens) {
    const chave = new Date(item.quando).toDateString();
    const ultimo = dias[dias.length - 1];
    if (ultimo?.chave === chave) ultimo.itens.push(item);
    else dias.push({ chave, rotulo: rotuloDoDia(item.quando), itens: [item] });
  }
  return dias;
}

/** O que uma pessoa fez, agrupado por dia, das acoes mais novas para as mais
 *  antigas. Carrega de 50 em 50. */
function LinhaDoTempo({ edicaoId, pessoa }) {
  const [itens, definirItens] = useState(null);
  const [mais, definirMais] = useState(false);
  const [carregando, definirCarregando] = useState(false);
  const [erro, definirErro] = useState("");

  async function carregar(antes) {
    definirCarregando(true);
    definirErro("");
    try {
      const r = await buscarAtividadeDaPessoa(edicaoId, pessoa.usuario_id, antes);
      definirItens((atual) => (antes ? [...(atual ?? []), ...r.itens] : r.itens));
      definirMais(r.mais);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }

  useEffect(() => {
    // Buscar no servidor e justamente o que este efeito existe para fazer.
    // eslint-disable-next-line react/set-state-in-effect
    carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pessoa.usuario_id]);

  if (itens === null) {
    return erro ? <Mensagem tipo="erro">{erro}</Mensagem> : <Carregando>Buscando o que foi feito...</Carregando>;
  }
  if (itens.length === 0) {
    return (
      <EmptyState
        titulo="Nenhuma ação ainda"
        corpo={`${pessoa.nome} ainda não fez nada no sistema além de entrar.`}
      />
    );
  }

  return (
    <div className="atividade__tempo">
      {porDia(itens).map((dia) => (
        <section key={dia.chave} className="atividade__dia">
          <h3 className="atividade__dia-titulo">{dia.rotulo}</h3>
          <ol className="atividade__itens">
            {dia.itens.map((item) => (
              <li key={item.id} className="atividade__item">
                <span className="atividade__hora">{hora(item.quando)}</span>
                <span>{item.texto}</span>
              </li>
            ))}
          </ol>
        </section>
      ))}
      <Mensagem tipo="erro">{erro}</Mensagem>
      {mais && (
        <Button
          variant="ghost"
          size="sm"
          carregando={carregando}
          onClick={() => carregar(itens[itens.length - 1].id)}
        >
          Ver mais antigas
        </Button>
      )}
    </div>
  );
}

/** "Ver atividade", no painel da coordenacao: a equipe da edicao, quem esta
 *  trabalhando, e o que cada um fez. Clicar numa pessoa abre a linha do tempo
 *  dela na mesma janela; a seta volta para a equipe. */
export default function AtividadeEquipe({ edicaoId, aoFechar }) {
  const estreita = useTelaEstreita();
  const [equipe, definirEquipe] = useState(null);
  const [erro, definirErro] = useState("");
  const [pessoa, definirPessoa] = useState(null);

  useEffect(() => {
    let vivo = true;
    buscarAtividade(edicaoId)
      .then((r) => vivo && definirEquipe(r))
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, [edicaoId]);

  return (
    <Modal
      rotulo={pessoa ? "Atividade de" : "Equipe da edição"}
      titulo={pessoa ? pessoa.nome : "Atividade"}
      tamanho="grande"
      aoFechar={aoFechar}
    >
      {pessoa ? (
        <>
          <button
            type="button"
            className="pasta-aberta__voltar atividade__voltar"
            onClick={() => definirPessoa(null)}
          >
            ← Toda a equipe
          </button>
          <LinhaDoTempo edicaoId={edicaoId} pessoa={pessoa} />
        </>
      ) : (
        <>
          <Mensagem tipo="erro">{erro}</Mensagem>
          {equipe === null && !erro && <Carregando>Juntando a atividade da equipe...</Carregando>}
          {equipe?.length === 0 && (
            <EmptyState titulo="Ninguém na equipe ainda" corpo="Cadastre as pessoas em Usuários." />
          )}
          {equipe?.length > 0 && (
            <>
              <p className="atividade__nota">
                Ações de trabalho, sem contar entrar, sair e buscar. Clique numa pessoa
                para ver tudo o que ela fez.
              </p>
              {estreita ? (
                <ul className="atividade__cartoes">
                  {equipe.map((p) => (
                    <li key={p.usuario_id}>
                      <button
                        type="button"
                        className="atividade__cartao"
                        onClick={() => definirPessoa(p)}
                      >
                        <span className="atividade__nome">{p.nome}</span>
                        <span className="campo__dica">
                          {p.perfil} · {p.hoje} hoje · {p.semana} em 7 dias
                        </span>
                        <span className="atividade__ultima">
                          {p.ultima_acao
                            ? `${p.ultima_acao} · ${quando(p.ultima_acao_em)}`
                            : "Nenhuma ação ainda"}
                        </span>
                        <Situacao pessoa={p} />
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="tabela-rolagem">
                  <table className="tabela tabela--densa atividade__tabela">
                    <thead>
                      <tr>
                        <th>Pessoa</th>
                        <th>Último acesso</th>
                        <th>Última ação</th>
                        <th className="tabela__numero">Hoje</th>
                        <th className="tabela__numero">7 dias</th>
                      </tr>
                    </thead>
                    <tbody>
                      {equipe.map((p) => (
                        <tr
                          key={p.usuario_id}
                          className="atividade__linha"
                          onClick={() => definirPessoa(p)}
                        >
                          <td>
                            <button
                              type="button"
                              className="atividade__link"
                              onClick={() => definirPessoa(p)}
                            >
                              {p.nome}
                            </button>
                            <span className="campo__dica">{p.perfil}</span>
                          </td>
                          <td>
                            {p.ultimo_acesso ? quando(p.ultimo_acesso) : "—"}
                            <div>
                              <Situacao pessoa={p} />
                            </div>
                          </td>
                          <td>
                            {p.ultima_acao ? (
                              <>
                                {p.ultima_acao}
                                <span className="campo__dica">{quando(p.ultima_acao_em)}</span>
                              </>
                            ) : (
                              <span className="celula--vazia">—</span>
                            )}
                          </td>
                          <td className="tabela__numero">{p.hoje}</td>
                          <td className="tabela__numero">{p.semana}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </>
      )}
    </Modal>
  );
}
