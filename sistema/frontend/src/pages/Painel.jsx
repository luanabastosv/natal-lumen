import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import Numero from "../components/feedback/Numero.jsx";
import { itensVisiveis } from "../components/layout/menu.js";
import { useSessao } from "../contexts/useSessao.js";
import { buscarRelatorio } from "../services/painel.js";
import { dinheiro, formatarData } from "../utils/dinheiro.js";

function primeiroNome(nome) {
  return nome?.trim().split(" ")[0] ?? "";
}

export default function Painel() {
  const { usuario, pode, vinculoAtivo, edicaoAtiva, escolherEdicao } = useSessao();

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

  const atalhos = itensVisiveis(pode, Boolean(usuario?.admin_geral)).filter(
    (i) => i.para !== "/painel",
  );

  const r = relatorio?.resumo;

  return (
    <div>
      <div className="pagina__eyebrow">
        {vinculoAtivo
          ? `${vinculoAtivo.cidade} ${vinculoAtivo.ano} · ${vinculoAtivo.perfil}`
          : usuario?.admin_geral
            ? "Administração geral"
            : "Sem edição vinculada"}
      </div>
      <h1 className="pagina__titulo">Olá, {primeiroNome(usuario?.nome)}</h1>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {!vinculoAtivo && !usuario?.admin_geral ? (
        <EmptyState
          titulo="Você ainda não está numa edição"
          corpo="Sua conta existe, mas a coordenação ainda não a vinculou a uma edição. Assim que isso acontecer, o menu aparece aqui."
        />
      ) : (
        <>
          {usuario?.vinculos.length > 1 && (
            <div className="barra-acoes">
              <Selecao
                value={edicaoAtiva ?? ""}
                onChange={(e) => escolherEdicao(Number(e.target.value))}
              >
                {usuario.vinculos.map((v) => (
                  <option key={v.edicao_id} value={v.edicao_id}>
                    {v.cidade} {v.ano}
                  </option>
                ))}
              </Selecao>
            </div>
          )}

          {podeVerNumeros && carregando && <Carregando>Somando os números...</Carregando>}

          {podeVerNumeros && r && (
            <>
              <h2 className="painel__titulo">{r.edicao}</h2>

              <div className="numeros">
                <Numero rotulo="Crianças" valor={r.criancas}
                  nota={`${r.instituicoes} instituição(ões)`} />
                <Numero rotulo="Apadrinhamentos" valor={r.apadrinhamentos_feitos}
                  de={r.apadrinhamentos_possiveis}
                  nota={`${r.cesta_feitos} cesta · ${r.festa_feitos} festa`} />
                <Numero rotulo="Crianças completas" valor={r.criancas_completas} de={r.criancas}
                  nota={`${r.criancas_sem_nenhum_padrinho} sem nenhum padrinho`} />
                <Numero rotulo="Padrinhos" valor={r.padrinhos} />
                <Numero rotulo="Cartões" valor={r.cartoes_digitalizados} de={r.cartoes_possiveis}
                  nota={`${r.cartoes_enviados} já enviado(s)`} />
                <Numero rotulo="Kits entregues" valor={r.kits_entregues} de={r.criancas}
                  nota={`${r.kits_montados} montado(s) · ${r.kits_pendentes} pendente(s)`} />
                <Numero rotulo="Check-in" valor={r.checkin_feitos} de={r.criancas} />
              </div>

              <div className="numeros">
                <Numero rotulo="Combinado com padrinhos" valor={dinheiro(r.valor_combinado)} />
                <Numero rotulo="Já pago" valor={dinheiro(r.valor_pago)}
                  nota={
                    Number(r.valor_combinado) > 0
                      ? `${Math.round((Number(r.valor_pago) / Number(r.valor_combinado)) * 100)}% do combinado`
                      : null
                  } />
                <Numero rotulo="Gasto em compras" valor={dinheiro(r.compras_total)} />
              </div>

              {relatorio.por_instituicao.length > 0 && (
                <>
                  <h2 className="painel__titulo">Por instituição</h2>
                  <div className="tabela-rolagem">
                    <table className="tabela">
                      <thead>
                        <tr>
                          <th>Instituição</th><th>Crianças</th><th>Apadrinhadas</th>
                          <th>Cartões</th><th>Kits entregues</th><th>Check-in</th>
                        </tr>
                      </thead>
                      <tbody>
                        {relatorio.por_instituicao.map((l) => (
                          <tr key={l.instituicao_id}>
                            <td>{l.instituicao}</td>
                            <td>{l.criancas}</td>
                            <td>{l.apadrinhados}</td>
                            <td>{l.cartoes}</td>
                            <td>{l.kits_entregues}</td>
                            <td>{l.checkin}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}

              {relatorio.por_dia.length > 0 && (
                <>
                  <h2 className="painel__titulo" style={{ marginTop: "var(--space-7)" }}>
                    Por dia
                  </h2>
                  <div className="tabela-rolagem">
                    <table className="tabela">
                      <thead>
                        <tr><th>Dia</th><th>Descrição</th><th>Crianças</th><th>Check-in</th></tr>
                      </thead>
                      <tbody>
                        {relatorio.por_dia.map((l) => (
                          <tr key={l.dia_evento_id ?? "sem-dia"}>
                            <td>{l.data ? formatarData(l.data) : "sem dia marcado"}</td>
                            <td>{l.descricao ?? "—"}</td>
                            <td>{l.criancas}</td>
                            <td>{l.checkin}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </>
          )}

          <h2 className="painel__titulo" style={{ marginTop: "var(--space-7)" }}>
            {podeVerNumeros ? "Ir para" : "Escolha por onde começar"}
          </h2>
          <p className="pagina__lede">
            O menu mostra apenas o que o seu perfil alcança.
          </p>

          <div className="atalhos">
            {atalhos.map((item) => (
              <Link key={item.para} to={item.para} className="atalho">
                <span className="atalho__rotulo">{item.rotulo}</span>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
