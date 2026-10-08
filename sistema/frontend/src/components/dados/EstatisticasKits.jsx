/* Quantas criancas de cada idade e sexo numa instituicao: "3 meninas de 4
   anos". E a conta da compra dos presentes, que se escolhem por idade e sexo —
   antes a equipe contava linha por linha na lista.

   As linhas chegam do servidor ja sem as desistentes: a caixa delas nao se
   monta. */

const SEXOS = [
  { id: "F", rotulo: "Meninas" },
  { id: "M", rotulo: "Meninos" },
];

const anos = (idade) => (idade === 1 ? "1 ano" : `${idade} anos`);

/** Agrupa as linhas ({idade, sexo, quantidade}) numa grade idade x sexo. */
function montarGrade(linhas) {
  const porIdade = new Map();
  const total = { F: 0, M: 0 };
  for (const l of linhas) {
    if (!porIdade.has(l.idade)) porIdade.set(l.idade, { F: 0, M: 0 });
    porIdade.get(l.idade)[l.sexo] = (porIdade.get(l.idade)[l.sexo] ?? 0) + l.quantidade;
    total[l.sexo] = (total[l.sexo] ?? 0) + l.quantidade;
  }
  const idades = [...porIdade.keys()].sort((a, b) => a - b);
  return { idades, porIdade, total, soma: total.F + total.M };
}

function Resumo({ total, soma }) {
  return (
    <>
      <strong>{total.F}</strong> {total.F === 1 ? "menina" : "meninas"} ·{" "}
      <strong>{total.M}</strong> {total.M === 1 ? "menino" : "meninos"} · {soma}{" "}
      {soma === 1 ? "criança" : "crianças"}
    </>
  );
}

/** Na janela: uma linha por idade, que e como se le de cima para baixo
 *  procurando "quantas de 4 anos". */
export function TabelaEstatisticas({ linhas }) {
  const { idades, porIdade, total, soma } = montarGrade(linhas);
  if (soma === 0) {
    return <p className="campo__dica">Nenhuma criança confirmada nesta instituição.</p>;
  }
  return (
    <>
      <p className="estatisticas-kits__resumo">
        <Resumo total={total} soma={soma} />
      </p>
      <table className="tabela tabela--densa estatisticas-kits__tabela">
        <thead>
          <tr>
            <th>Idade</th>
            {SEXOS.map((s) => (
              <th key={s.id}>{s.rotulo}</th>
            ))}
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {idades.map((idade) => {
            const linha = porIdade.get(idade);
            return (
              <tr key={idade}>
                <td>{anos(idade)}</td>
                {/* O zero fica apagado: o olho procura onde HA crianca. */}
                {SEXOS.map((s) => (
                  <td key={s.id} className={linha[s.id] ? "" : "estatisticas-kits__zero"}>
                    {linha[s.id] || "—"}
                  </td>
                ))}
                <td>{linha.F + linha.M}</td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <th>Total</th>
            {SEXOS.map((s) => (
              <td key={s.id}>{total[s.id]}</td>
            ))}
            <td>{soma}</td>
          </tr>
        </tfoot>
      </table>
    </>
  );
}

/** No papel: deitada, uma coluna por idade. Em pe a tabela comia meia folha
 *  antes da lista comecar; deitada cabe em tres linhas. */
export function EstatisticasImpressas({ linhas }) {
  const { idades, porIdade, total, soma } = montarGrade(linhas);
  if (soma === 0) return null;
  return (
    <div className="impressao__estatisticas">
      <p>
        <Resumo total={total} soma={soma} /> (sem as desistentes)
      </p>
      <table className="impressao__tabela">
        <thead>
          <tr>
            <th>Idade</th>
            {idades.map((idade) => (
              <th key={idade}>{anos(idade)}</th>
            ))}
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {SEXOS.map((s) => (
            <tr key={s.id}>
              <td>{s.rotulo}</td>
              {idades.map((idade) => (
                <td key={idade}>{porIdade.get(idade)[s.id] || "—"}</td>
              ))}
              <td>{total[s.id]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
