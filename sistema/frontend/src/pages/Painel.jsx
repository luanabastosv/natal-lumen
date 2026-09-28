import { useEffect, useState } from "react";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Numero from "../components/feedback/Numero.jsx";
import Progresso from "../components/feedback/Progresso.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { buscarRelatorio } from "../services/painel.js";

function primeiroNome(nome) {
  return nome?.trim().split(" ")[0] ?? "";
}

function plural(n, um, muitos) {
  return `${n} ${n === 1 ? um : muitos}`;
}

export default function Painel() {
  const { usuario, pode, vinculoAtivo, edicao, edicaoAtiva } = useSessao();

  const [relatorio, definirRelatorio] = useState(null);
  const [carregando, definirCarregando] = useState(false);
  const [erro, definirErro] = useState("");

  const podeVerNumeros = pode("ver_painel");

  useEffect(() => {
    if (!podeVerNumeros || !edicaoAtiva) return;

    let vivo = true;
    // Mostrar o carregando e justamente o efeito colateral que queremos aqui.
    // eslint-disable-next-line react/set-state-in-effect
    definirCarregando(true);
    buscarRelatorio(edicaoAtiva)
      .then((dados) => vivo && definirRelatorio(dados))
      .catch((e) => vivo && definirErro(e.message))
      .finally(() => vivo && definirCarregando(false));

    return () => {
      vivo = false;
    };
  }, [podeVerNumeros, edicaoAtiva]);

  const r = relatorio?.resumo;

  return (
    <div>
      {/* Card de abertura: no layout Sidebar e ele que faz o papel do
          cabecalho, carregando saudacao e contexto. So existe na home. */}
      <div className="abertura">
        <h1 className="abertura__titulo">
          Olá, <span className="abertura__nome">{primeiroNome(usuario?.nome)}</span>!
        </h1>
        <p className="abertura__lede">
          Acompanhe o panorama da edição e siga para o que precisa da sua mão.
        </p>
        <div className="abertura__contexto">
          {/* Qual edicao esta sendo vista. Trocar de edicao e na lateral: e
              uma escolha do sistema inteiro, nao deste card. */}
          <span className="chip">
            {edicao
              ? `${edicao.cidade} ${edicao.ano}`
              : usuario?.admin_geral
                ? "Administração geral"
                : "Sem edição vinculada"}
          </span>
          {vinculoAtivo && <span className="chip chip--discreto">{vinculoAtivo.perfil}</span>}
        </div>
      </div>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {!vinculoAtivo && !usuario?.admin_geral ? (
        <EmptyState
          titulo="Você ainda não está numa edição"
          corpo="Sua conta existe, mas a coordenação ainda não a vinculou a uma edição. Assim que isso acontecer, o menu aparece aqui."
        />
      ) : (
        <>
          {podeVerNumeros && carregando && <Carregando>Somando os números...</Carregando>}

          {podeVerNumeros && r && (
            <>
              <h2 className="painel__titulo">{r.edicao}</h2>

              {/* Cada crianca precisa de um padrinho de cesta e um de festa.
                  Os dois se comparam ao total de criancas, nunca entre si. */}
              <div className="numeros">
                <Numero
                  rotulo="Crianças"
                  valor={r.criancas}
                  nota={plural(r.instituicoes, "instituição", "instituições")}
                />
                <Numero
                  rotulo="Cesta apadrinhada"
                  valor={r.cesta_feitos}
                  de={r.criancas}
                  tom="cesta"
                  nota={`faltam ${r.criancas - r.cesta_feitos}`}
                />
                <Numero
                  rotulo="Festa apadrinhada"
                  valor={r.festa_feitos}
                  de={r.criancas}
                  tom="festa"
                  nota={`faltam ${r.criancas - r.festa_feitos}`}
                />
              </div>

              {relatorio.por_instituicao.length > 0 && (
                <>
                  <h2 className="painel__titulo">Por instituição</h2>
                  <div className="lista-progresso">
                    {relatorio.por_instituicao.map((l) => (
                      <div key={l.instituicao_id} className="lista-progresso__item">
                        <div className="lista-progresso__topo">
                          <span className="lista-progresso__nome">{l.instituicao}</span>
                          <span className="lista-progresso__total">
                            {plural(l.criancas, "criança", "crianças")}
                          </span>
                        </div>
                        <Progresso rotulo="Cesta" valor={l.cesta} de={l.criancas} tom="cesta" />
                        <Progresso rotulo="Festa" valor={l.festa} de={l.criancas} tom="festa" />
                      </div>
                    ))}
                  </div>
                </>
              )}

              {relatorio.por_comissario.length > 0 && (
                <>
                  <h2 className="painel__titulo" style={{ marginTop: "var(--space-7)" }}>
                    Por comissário
                  </h2>
                  <p className="pagina__lede">
                    Completa é a criança que já tem os dois padrinhos, de cesta e de festa.
                  </p>
                  <div className="tabela-rolagem">
                    <table className="tabela tabela--larga">
                      <caption className="tabela-dica">
                        Arraste a lista para o lado para ver todas as colunas.
                      </caption>
                      <thead>
                        <tr>
                          <th>Comissário</th>
                          <th>Crianças</th>
                          <th>Cesta</th>
                          <th>Festa</th>
                          <th>Completas</th>
                          <th>Faltam</th>
                        </tr>
                      </thead>
                      <tbody>
                        {relatorio.por_comissario.map((l) => (
                          <tr key={l.comissario_id ?? "sem-comissario"}>
                            <td>
                              {l.comissario}
                              {/* O grupo e dado de apoio do nome logo acima:
                                  le-se depois dele, nao no lugar dele. */}
                              <div className="vinculo-linha__detalhe">{l.grupo ?? "—"}</div>
                            </td>
                            <td>{l.criancas}</td>
                            <td>{l.cesta}</td>
                            <td>{l.festa}</td>
                            <td>{l.completas}</td>
                            <td className={l.faltam > 0 ? "tabela__pendente" : undefined}>
                              {l.faltam}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </>
          )}

          {/* Sem ver_painel nao ha o que mostrar aqui, e a pagina ficaria so
              com a saudacao. O caminho e o menu — que ja lista o que o perfil
              alcanca — entao o que falta dizer e so isso. */}
          {!podeVerNumeros && (
            <EmptyState
              titulo="Escolha por onde começar"
              corpo="Seu perfil não acompanha os números da edição. Use o menu ao lado: ele mostra tudo o que você alcança."
            />
          )}
        </>
      )}
    </div>
  );
}
