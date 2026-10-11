import EtiquetaDia from "../core/EtiquetaDia.jsx";

const NUCLEOS = ["A", "B", "C", "D"];

/** A divisao de cada dia em nucleos, feita pela coordenacao da monitoria, para
 *  a coordenacao geral acompanhar: quantas criancas em cada nucleo e quais
 *  instituicoes, com a cor da bata de cada uma. So leitura — quem organiza e
 *  a monitoria, no painel dela.
 *
 *  Recebe `por_instituicao` do painel da monitoria. Nao desenha nada se
 *  nenhum dia foi dividido ainda. */
export default function NucleosDoEvento({ instituicoes }) {
  const dias = new Map();
  for (const i of instituicoes) {
    if (!i.dia_evento_id || !i.nucleo) continue;
    if (!dias.has(i.dia_evento_id)) {
      dias.set(i.dia_evento_id, { id: i.dia_evento_id, data: i.dia_data, descricao: i.dia_descricao, insts: [] });
    }
    dias.get(i.dia_evento_id).insts.push(i);
  }
  if (dias.size === 0) return null;

  // Quem tem dia mas ainda nao caiu em nucleo: a divisao esta pela metade.
  const faltam = (diaId) =>
    instituicoes.filter((i) => i.dia_evento_id === diaId && !i.nucleo).length;

  return (
    <section className="cartao">
      <div className="cartao__topo">
        <h3 className="cartao__titulo">Núcleos de rodízio</h3>
      </div>
      <p className="cartao__lede">
        Como a coordenação da monitoria dividiu cada dia. A cor ao lado de cada instituição é a
        bata das crianças dela.
      </p>
      {[...dias.values()]
        .sort((a, b) => a.data.localeCompare(b.data))
        .map((d) => (
          <div key={d.id} className="nucleos-evento__dia">
            <div className="monitoria-dia__topo">
              <EtiquetaDia data={d.data} descricao={d.descricao} />
              <span>
                <strong>{d.insts.reduce((s, i) => s + i.criancas, 0)}</strong> crianças em núcleo
                {faltam(d.id) > 0 && (
                  <span className="nucleos-evento__falta">
                    {" "}
                    · {faltam(d.id)} {faltam(d.id) === 1 ? "instituição" : "instituições"} sem núcleo
                  </span>
                )}
              </span>
            </div>
            <div className="nucleos-evento__grade">
              {NUCLEOS.map((n) => {
                const insts = d.insts
                  .filter((i) => i.nucleo === n)
                  .sort((a, b) => b.criancas - a.criancas);
                return (
                  <div key={n} className="nucleos-evento__nucleo">
                    <div className="nucleos-evento__cabeca">
                      <span className="monitoria-nucleo__letra">Núcleo {n}</span>
                      <span className="monitoria-nucleo__conta">
                        {insts.reduce((s, i) => s + i.criancas, 0)}
                      </span>
                    </div>
                    <ul className="nucleos-evento__insts">
                      {insts.map((i) => (
                        <li key={i.instituicao_id} title={i.instituicao}>
                          <span
                            className={`amostra-bata ${i.cor_bata_hex ? "" : "amostra-bata--vazia"}`}
                            style={i.cor_bata_hex ? { background: i.cor_bata_hex } : undefined}
                          />
                          <span className="nucleos-evento__nome">{i.sigla || i.instituicao}</span>
                          <span className="nucleos-evento__criancas">{i.criancas}</span>
                        </li>
                      ))}
                      {insts.length === 0 && <li className="nucleo__vazio">—</li>}
                    </ul>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
    </section>
  );
}
