import { useEffect, useState } from "react";
import Carregando from "../feedback/Carregando.jsx";
import EmptyState from "../feedback/EmptyState.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Metrica from "../feedback/Metrica.jsx";
import { buscarPainelIntercessao } from "../../services/intercessao.js";
import useTelaEstreita from "../../hooks/useTelaEstreita.js";

/** 41,2 e nao 41.2: o numero quebrado e a regra da planilha, e se le em
 *  portugues. Inteiro sai sem virgula. */
const decimal = (n) => n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });

/** O quantitativo da intercessao, como a planilha manual somava.
 *
 *  Missas, adoracoes e jejuns sao as marcacoes divididas por 5 (cinco criancas
 *  por vivencia); os tercos, os misterios divididos por 15. A conta e do
 *  servidor; aqui so se escreve.
 *
 *  `secao`: a coordenacao ve isto embaixo do painel dela, como uma lista
 *  resumida num cartao. Para a equipe da intercessao, e o painel inteiro, em
 *  cards. */
export default function PainelIntercessao({ edicaoId, secao = false }) {
  const [p, definirP] = useState(null);
  const [erro, definirErro] = useState("");
  const estreita = useTelaEstreita();

  useEffect(() => {
    let vivo = true;
    buscarPainelIntercessao(edicaoId)
      .then((r) => vivo && definirP(r))
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, [edicaoId]);

  // Embaixo do painel da coordenacao, a intercessao e um extra: se a consulta
  // falhar, a secao so nao aparece, e o resto do painel segue limpo.
  if (erro) return secao ? null : <Mensagem tipo="erro">{erro}</Mensagem>;
  if (!p) return secao ? null : <Carregando tela>Somando as intercessões...</Carregando>;
  if (p.criancas === 0 && !secao) {
    return (
      <EmptyState
        titulo="Nenhuma criança nesta edição ainda"
        corpo="Assim que as listas das instituições forem importadas, as crianças aparecem na lista geral para a intercessão."
      />
    );
  }

  // A coordenacao ve a intercessao como lista, no jeito da planilha: uma
  // linha por numero, num cartao so, sem os cards grandes da equipe.
  if (secao) {
    const pct = p.criancas > 0 ? ` (${Math.round((p.receberam / p.criancas) * 100)}%)` : "";
    const linhas = [
      ["Crianças", p.criancas],
      ["Receberam intercessão", `${p.receberam}${pct}`],
      ["Ainda não receberam", p.faltam],
      ["Crianças intercedidas na missa", `${p.marcacoes_missa} · ${decimal(p.missas)} ${p.missas === 1 ? "missa" : "missas"}`],
      ["Crianças intercedidas na adoração", `${p.marcacoes_adoracao} · ${decimal(p.adoracoes)} ${p.adoracoes === 1 ? "adoração" : "adorações"}`],
      ["Crianças intercedidas por terço", `${p.marcacoes_terco} · ${decimal(p.tercos)} ${p.tercos === 1 ? "terço" : "terços"}`],
      ["Crianças intercedidas no jejum", `${p.marcacoes_jejum} · ${decimal(p.jejuns)} ${p.jejuns === 1 ? "jejum" : "jejuns"}`],
      ["Ave-marias rezadas por outras equipes", p.ave_marias],
    ];
    return (
      <section className="cartao painel__secao">
        <div className="cartao__topo">
          <h3 className="cartao__titulo">Intercessão</h3>
        </div>
        <table className="tabela tabela--densa">
          <tbody>
            {linhas.map(([rotulo, valor]) => (
              <tr key={rotulo}>
                <td>{rotulo}</td>
                <td className="cartao__numero painel__valor-lista">{valor}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    );
  }

  // As ave-marias vem de todas as equipes, pelo convite de oracao: o numero e
  // so informativo para a intercessao, e o card diz isso no fundo e na etiqueta.
  const aveMarias = (
    <Metrica
      rotulo="Ave-marias"
      valor={p.ave_marias}
      // No celular a etiqueta nao cabe ao lado do rotulo em meia largura: la
      // o aviso vira o subtitulo do card.
      etiqueta={estreita ? undefined : "Rezadas por outras equipes"}
      nota={estreita ? "Ave-marias rezadas por outras equipes" : undefined}
      informativa
    />
  );

  const cabeca = [
    <Metrica key="criancas" rotulo="Crianças" valor={p.criancas} destaque />,
    <Metrica key="receberam" rotulo="Receberam intercessão" valor={p.receberam} de={p.criancas} />,
    <Metrica
      key="faltam"
      rotulo="Ainda não receberam"
      valor={p.faltam}
      nota={p.faltam === 0 && p.criancas > 0 ? "todas já receberam" : undefined}
    />,
  ];

  // O mesmo padrao nas quatro: o numero grande e quantas criancas ja foram
  // intercedidas naquela vivencia (cada checkbox marcado), e embaixo quantas
  // vivencias isso da pela regra da planilha: 5 criancas por missa, adoracao
  // ou jejum; 15 por terco (3 por misterio, 5 misterios). A divisao vem pronta
  // do servidor.
  const vivencias = [
    <Metrica
      key="missa"
      rotulo="Crianças intercedidas na missa"
      valor={p.marcacoes_missa}
      nota={`${decimal(p.missas)} ${p.missas === 1 ? "missa participada" : "missas participadas"}`}
    />,
    <Metrica
      key="adoracao"
      rotulo="Crianças intercedidas na adoração"
      valor={p.marcacoes_adoracao}
      nota={`${decimal(p.adoracoes)} ${p.adoracoes === 1 ? "adoração participada" : "adorações participadas"}`}
    />,
    <Metrica
      key="terco"
      rotulo="Crianças intercedidas por terço"
      valor={p.marcacoes_terco}
      nota={`${decimal(p.tercos)} ${p.tercos === 1 ? "terço rezado" : "terços rezados"}`}
    />,
    <Metrica
      key="jejum"
      rotulo="Crianças intercedidas no jejum"
      valor={p.marcacoes_jejum}
      nota={`${decimal(p.jejuns)} ${p.jejuns === 1 ? "jejum feito" : "jejuns feitos"}`}
    />,
  ];

  return (
    <section>
      <div className="painel__cabeca">
        <h2 className="painel__titulo">{p.edicao}</h2>
      </div>

      {/* No computador, duas fileiras de quatro, com as ave-marias fechando a
          primeira. No celular, uma grade so de duas colunas com as oito, e as
          ave-marias por ultimo: o canto de baixo a direita, fora do caminho
          dos numeros que sao da intercessao. */}
      {estreita ? (
        <div className="metricas">
          {cabeca}
          {vivencias}
          {aveMarias}
        </div>
      ) : (
        <>
          <div className="metricas">
            {cabeca}
            {aveMarias}
          </div>
          <div className="metricas">{vivencias}</div>
        </>
      )}
    </section>
  );
}
