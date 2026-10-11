import { useMemo, useState } from "react";
import Button from "../core/Button.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import { salvarNucleos } from "../../services/monitoria.js";
import { CORES_DE_BATA, nomeDaCor, parecidas } from "../../utils/cores.js";
import { rotuloDia } from "../../utils/dinheiro.js";

const NUCLEOS = ["A", "B", "C", "D"];
const OUTRA = "outra";

/** Os pares de instituicoes, no mesmo nucleo, com batas que se confundem. */
function conflitos(instituicoes, rascunho) {
  const pares = [];
  for (let i = 0; i < instituicoes.length; i += 1) {
    for (let j = i + 1; j < instituicoes.length; j += 1) {
      const a = rascunho[instituicoes[i].instituicao_id];
      const b = rascunho[instituicoes[j].instituicao_id];
      if (parecidas(a.cor_bata_hex, b.cor_bata_hex)) pares.push([instituicoes[i], instituicoes[j]]);
    }
  }
  return pares;
}

/** Sugere a divisao de UM dia: as maiores primeiro, cada uma no nucleo com
 *  menos criancas onde a bata dela nao se confunde com nenhuma que ja esta
 *  la. Se nao houver nucleo sem conflito, vai para o mais vazio mesmo — e o
 *  aviso aparece para a coordenacao decidir. */
function sugerir(instituicoes, rascunho) {
  const cor = (inst) => rascunho[inst.instituicao_id].cor_bata_hex;
  const onde = new Map();
  const total = Object.fromEntries(NUCLEOS.map((n) => [n, 0]));
  const membros = Object.fromEntries(NUCLEOS.map((n) => [n, []]));
  const cabe = (inst, n, sem) =>
    !membros[n].some((o) => o !== inst && o !== sem && parecidas(cor(o), cor(inst)));
  const por = (inst, n) => {
    onde.set(inst, n);
    membros[n].push(inst);
    total[n] += inst.criancas;
  };
  const tira = (inst) => {
    const n = onde.get(inst);
    membros[n] = membros[n].filter((o) => o !== inst);
    total[n] -= inst.criancas;
  };

  // 1. As maiores primeiro, cada uma no nucleo mais vazio onde a bata cabe.
  for (const inst of [...instituicoes].sort((a, b) => b.criancas - a.criancas)) {
    const porVazio = [...NUCLEOS].sort((a, b) => total[a] - total[b]);
    por(inst, porVazio.find((n) => cabe(inst, n)) ?? porVazio[0]);
  }

  // 2. Acerto fino: move uma instituicao, ou troca duas de nucleo, sempre que
  //    isso aproxima os totais sem juntar batas parecidas. Para quando
  //    nenhuma troca melhora mais nada.
  const desequilibrio = () => {
    const media = instituicoes.reduce((s, i) => s + i.criancas, 0) / NUCLEOS.length;
    return NUCLEOS.reduce((s, n) => s + (total[n] - media) ** 2, 0);
  };
  for (let melhorou = true, voltas = 0; melhorou && voltas < 50; voltas += 1) {
    melhorou = false;
    for (const a of instituicoes) {
      for (const n of NUCLEOS) {
        if (n === onde.get(a)) continue;
        const antes = desequilibrio();
        // Mover a para n.
        if (cabe(a, n)) {
          const de = onde.get(a);
          tira(a);
          por(a, n);
          if (desequilibrio() < antes) {
            melhorou = true;
            continue;
          }
          tira(a);
          por(a, de);
        }
        // Trocar a com alguem de n.
        for (const b of [...membros[n]]) {
          const na = onde.get(a);
          if (!cabe(a, n, b) || !cabe(b, na, a)) continue;
          tira(a);
          tira(b);
          por(a, n);
          por(b, na);
          if (desequilibrio() < antes) {
            melhorou = true;
            break;
          }
          tira(a);
          tira(b);
          por(a, na);
          por(b, n);
        }
      }
    }
  }

  const novo = { ...rascunho };
  for (const [inst, n] of onde) {
    novo[inst.instituicao_id] = { ...novo[inst.instituicao_id], nucleo: n };
  }
  return novo;
}

function Amostra({ hex }) {
  return (
    <span
      className={`amostra-bata ${hex ? "" : "amostra-bata--vazia"}`}
      style={hex ? { background: hex } : undefined}
      aria-hidden="true"
    />
  );
}

/** A instituicao dentro do nucleo: quantas criancas, o nucleo e a bata. */
function CartaoInstituicao({ inst, valor, aoMudar, conflito }) {
  const naLista = Boolean(nomeDaCor(valor.cor_bata_hex));
  const [outra, definirOutra] = useState(Boolean(valor.cor_bata_hex) && !naLista);

  function escolherCor(evento) {
    const v = evento.target.value;
    if (v === OUTRA) {
      definirOutra(true);
      aoMudar({ cor_bata_hex: valor.cor_bata_hex || "#888888", cor_bata_nome: valor.cor_bata_nome || "" });
      return;
    }
    definirOutra(false);
    const cor = CORES_DE_BATA.find((c) => c.hex === v);
    aoMudar({ cor_bata_hex: cor?.hex ?? null, cor_bata_nome: cor?.nome ?? null });
  }

  return (
    <div className={`nucleo-inst ${conflito ? "nucleo-inst--conflito" : ""}`}>
      <div className="nucleo-inst__topo">
        <Amostra hex={valor.cor_bata_hex} />
        <span className="nucleo-inst__nome" title={inst.instituicao}>
          {inst.sigla || inst.instituicao}
        </span>
        <span className="nucleo-inst__criancas">{inst.criancas}</span>
      </div>
      <div className="nucleo-inst__controles">
        <select
          className="campo__controle"
          aria-label={`Núcleo de ${inst.instituicao}`}
          value={valor.nucleo ?? ""}
          onChange={(e) => aoMudar({ nucleo: e.target.value || null })}
        >
          <option value="">Sem núcleo</option>
          {NUCLEOS.map((n) => (
            <option key={n} value={n}>
              Núcleo {n}
            </option>
          ))}
        </select>
        <select
          className="campo__controle"
          aria-label={`Cor da bata de ${inst.instituicao}`}
          value={outra ? OUTRA : (valor.cor_bata_hex ?? "")}
          onChange={escolherCor}
        >
          <option value="">Sem cor</option>
          {CORES_DE_BATA.map((c) => (
            <option key={c.hex} value={c.hex}>
              {c.nome}
            </option>
          ))}
          <option value={OUTRA}>Outra cor…</option>
        </select>
        {outra && (
          <div className="nucleo-inst__outra">
            <input
              type="color"
              aria-label={`Escolher a cor exata da bata de ${inst.instituicao}`}
              value={valor.cor_bata_hex || "#888888"}
              onChange={(e) => aoMudar({ cor_bata_hex: e.target.value })}
            />
            <input
              className="campo__controle"
              placeholder="Nome da cor"
              aria-label={`Nome da cor da bata de ${inst.instituicao}`}
              value={valor.cor_bata_nome ?? ""}
              maxLength={40}
              onChange={(e) => aoMudar({ cor_bata_nome: e.target.value })}
            />
          </div>
        )}
      </div>
    </div>
  );
}

/** "Organizar núcleos": divide as instituicoes de cada dia em A, B, C e D, com
 *  quantidades parecidas de criancas, e marca a cor da bata de cada uma —
 *  avisando quando duas batas parecidas caem no mesmo nucleo. */
export default function OrganizarNucleos({ edicaoId, instituicoes, aoFechar, aoSalvar }) {
  const comDia = instituicoes.filter((i) => i.dia_evento_id);
  const semDia = instituicoes.length - comDia.length;

  const dias = useMemo(() => {
    const mapa = new Map();
    for (const i of comDia) {
      if (!mapa.has(i.dia_evento_id)) {
        mapa.set(i.dia_evento_id, { id: i.dia_evento_id, data: i.dia_data, descricao: i.dia_descricao });
      }
    }
    return [...mapa.values()].sort((a, b) => a.data.localeCompare(b.data));
  }, [comDia]);

  const [diaId, definirDiaId] = useState(dias[0]?.id ?? null);
  const [rascunho, definirRascunho] = useState(() =>
    Object.fromEntries(
      comDia.map((i) => [
        i.instituicao_id,
        { nucleo: i.nucleo, cor_bata_nome: i.cor_bata_nome, cor_bata_hex: i.cor_bata_hex },
      ]),
    ),
  );
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState("");

  const doDia = comDia.filter((i) => i.dia_evento_id === diaId);
  const totalDoDia = doDia.reduce((s, i) => s + i.criancas, 0);
  const ideal = totalDoDia / NUCLEOS.length;

  function mudar(id, mudanca) {
    definirRascunho((r) => ({ ...r, [id]: { ...r[id], ...mudanca } }));
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      const novo = await salvarNucleos(
        edicaoId,
        comDia.map((i) => ({ instituicao_id: i.instituicao_id, ...rascunho[i.instituicao_id] })),
      );
      aoSalvar(novo);
    } catch (e) {
      definirErro(e.message);
      definirSalvando(false);
    }
  }

  const colunas = NUCLEOS.map((n) => {
    const insts = doDia
      .filter((i) => (rascunho[i.instituicao_id].nucleo ?? null) === n)
      .sort((a, b) => b.criancas - a.criancas);
    const pares = conflitos(insts, rascunho);
    return {
      nucleo: n,
      insts,
      criancas: insts.reduce((s, i) => s + i.criancas, 0),
      pares,
      emConflito: new Set(pares.flat().map((i) => i.instituicao_id)),
    };
  });
  const totalConflitos = colunas.reduce((s, c) => s + c.pares.length, 0);
  // As que ainda nao tem nucleo ficam numa lista embaixo dos quatro, e nao
  // numa quinta coluna: nao sao um nucleo, sao o que falta distribuir.
  const semNucleo = doDia
    .filter((i) => !rascunho[i.instituicao_id].nucleo)
    .sort((a, b) => b.criancas - a.criancas);

  return (
    <Modal rotulo="Monitoria" titulo="Organizar núcleos" tamanho="amplo" aoFechar={aoFechar}>
      <form onSubmit={salvar} className="nucleos">
        {dias.length === 0 ? (
          <Mensagem tipo="aviso">
            Nenhuma instituição tem dia do evento ainda. Os núcleos são uma divisão de cada
            dia: defina o dia das instituições em Instituições primeiro.
          </Mensagem>
        ) : (
          <>
            <div className="abas nucleos__dias" role="tablist">
              {dias.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  role="tab"
                  aria-selected={d.id === diaId}
                  className={`aba ${d.id === diaId ? "aba--ativa" : ""}`}
                  onClick={() => definirDiaId(d.id)}
                >
                  <span>{rotuloDia(d.data, d.descricao)}</span>
                  <span className="aba__contagem">
                    {comDia.filter((i) => i.dia_evento_id === d.id).reduce((s, i) => s + i.criancas, 0)}{" "}
                    crianças
                  </span>
                </button>
              ))}
            </div>

            <div className="nucleos__barra">
              <p className="nucleos__nota">
                {totalDoDia} crianças neste dia: o ideal são <strong>{Math.round(ideal)}</strong> por
                núcleo. Escolha o núcleo e a cor da bata de cada instituição, ou peça uma sugestão.
              </p>
              <Button
                variant="suave"
                size="sm"
                onClick={() => definirRascunho((r) => sugerir(doDia, r))}
              >
                Sugerir divisão
              </Button>
            </div>

            {totalConflitos > 0 && (
              <Mensagem tipo="aviso">
                {totalConflitos === 1 ? "Há 1 par" : `Há ${totalConflitos} pares`} de batas parecidas
                no mesmo núcleo — marcados em vermelho. Troque uma delas de núcleo.
              </Mensagem>
            )}

            <div className="nucleos__grade">
              {colunas.map((c) => {
                const desvio = ideal > 0 ? Math.round(((c.criancas - ideal) / ideal) * 100) : 0;
                return (
                  <section key={c.nucleo} className="nucleo">
                    <header className="nucleo__topo">
                      <h3 className="nucleo__titulo">Núcleo {c.nucleo}</h3>
                      <span className="nucleo__conta">
                        {c.criancas} crianças · {c.insts.length}{" "}
                        {c.insts.length === 1 ? "instituição" : "instituições"}
                      </span>
                      {ideal > 0 && (
                        <div
                          className="nucleo__trilho"
                          role="img"
                          aria-label={`${c.criancas} de ${Math.round(ideal)} ideais`}
                        >
                          <div
                            className={`nucleo__parte ${Math.abs(desvio) > 15 ? "nucleo__parte--fora" : ""}`}
                            style={{ width: `${Math.min(100, (c.criancas / (ideal * 1.5)) * 100)}%` }}
                          />
                          <span className="nucleo__ideal" style={{ left: `${100 / 1.5}%` }} />
                        </div>
                      )}
                      {ideal > 0 && Math.abs(desvio) > 15 && (
                        <span className="nucleo__desvio">
                          {desvio > 0 ? `${desvio}% acima` : `${-desvio}% abaixo`} do ideal
                        </span>
                      )}
                    </header>
                    {c.insts.map((inst) => (
                      <CartaoInstituicao
                        key={inst.instituicao_id}
                        inst={inst}
                        valor={rascunho[inst.instituicao_id]}
                        conflito={c.emConflito.has(inst.instituicao_id)}
                        aoMudar={(m) => mudar(inst.instituicao_id, m)}
                      />
                    ))}
                    {c.insts.length === 0 && <p className="nucleo__vazio">Nenhuma instituição</p>}
                  </section>
                );
              })}
            </div>

            {semNucleo.length > 0 ? (
              <section className="nucleos__sem">
                <h3 className="nucleos__sem-titulo">
                  Sem núcleo
                  <span className="nucleo__conta">
                    {" "}
                    · {semNucleo.length}{" "}
                    {semNucleo.length === 1 ? "instituição" : "instituições"},{" "}
                    {semNucleo.reduce((s, i) => s + i.criancas, 0)} crianças para distribuir
                  </span>
                </h3>
                <div className="nucleos__sem-lista">
                  {semNucleo.map((inst) => (
                    <CartaoInstituicao
                      key={inst.instituicao_id}
                      inst={inst}
                      valor={rascunho[inst.instituicao_id]}
                      conflito={false}
                      aoMudar={(m) => mudar(inst.instituicao_id, m)}
                    />
                  ))}
                </div>
              </section>
            ) : (
              <p className="nucleos__nota">Todas as instituições deste dia estão num núcleo.</p>
            )}

            {semDia > 0 && (
              <p className="nucleos__nota">
                {semDia === 1
                  ? "1 instituição ainda não tem dia do evento e fica fora da divisão."
                  : `${semDia} instituições ainda não têm dia do evento e ficam fora da divisão.`}
              </p>
            )}
          </>
        )}

        <Mensagem tipo="erro">{erro}</Mensagem>
        <div className="barra-acoes barra-acoes--fim">
          <div className="barra-acoes__ponta">
            <Button variant="ghost" onClick={aoFechar} disabled={salvando}>
              Cancelar
            </Button>
            <Button variant="secondary" type="submit" carregando={salvando} disabled={dias.length === 0}>
              Salvar núcleos
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
