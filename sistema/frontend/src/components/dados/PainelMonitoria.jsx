import { useEffect, useState } from "react";
import Button from "../core/Button.jsx";
import EtiquetaDia from "../core/EtiquetaDia.jsx";
import Carregando from "../feedback/Carregando.jsx";
import EmptyState from "../feedback/EmptyState.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Metrica from "../feedback/Metrica.jsx";
import Modal from "../feedback/Modal.jsx";
import Progresso from "../feedback/Progresso.jsx";
import OrganizarNucleos from "./OrganizarNucleos.jsx";
import { buscarPainelMonitoria } from "../../services/monitoria.js";
import { rotuloDia } from "../../utils/dinheiro.js";

const NUCLEOS = ["A", "B", "C", "D"];

const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

/** O painel da coordenacao da monitoria: o papel (cartoes de cesta e de
 *  festa, autorizacoes), os cuidados especiais e o dia — quantas criancas em
 *  cada dia e em cada nucleo.
 *
 *  `monitor`: a versao do monitor de base. O servidor ja manda so as
 *  instituicoes dele; aqui saem os nucleos (que sao da coordenacao) e os
 *  cuidados aparecem abertos, crianca a crianca — sao poucas, e e o que ele
 *  precisa ter na mao no dia. */
export default function PainelMonitoria({ edicaoId, monitor = false }) {
  const [p, definirP] = useState(null);
  const [erro, definirErro] = useState("");
  const [organizando, definirOrganizando] = useState(false);
  const [vendoCuidados, definirVendoCuidados] = useState(null);

  useEffect(() => {
    let vivo = true;
    buscarPainelMonitoria(edicaoId)
      .then((r) => vivo && definirP(r))
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
  }, [edicaoId]);

  if (erro) return <Mensagem tipo="erro">{erro}</Mensagem>;
  if (!p) return <Carregando tela>Somando os números...</Carregando>;
  if (p.criancas === 0) {
    return monitor ? (
      <EmptyState
        titulo="Nenhuma criança nas suas instituições ainda"
        corpo="Assim que a coordenação ligar você a uma instituição e a lista dela for importada, os números aparecem aqui."
      />
    ) : (
      <EmptyState
        titulo="Nenhuma criança nesta edição ainda"
        corpo="Assim que as listas das instituições forem importadas, os números aparecem aqui."
      />
    );
  }

  const dias = p.por_dia.filter((d) => d.dia_evento_id);
  // Por dia e por nucleo: quantas criancas e quais instituicoes em cada um.
  const nucleosDoDia = (diaId) =>
    NUCLEOS.map((n) => {
      const insts = p.por_instituicao.filter((i) => i.dia_evento_id === diaId && i.nucleo === n);
      return { nucleo: n, insts, criancas: insts.reduce((s, i) => s + i.criancas, 0) };
    });
  const temNucleos = (diaId) =>
    p.por_instituicao.some((i) => i.dia_evento_id === diaId && i.nucleo);
  const comCuidados = p.por_instituicao.filter((i) => i.cuidados.length > 0);

  return (
    <>
      <div className="painel__cabeca">
        <h2 className="painel__titulo">
          {monitor
            ? p.por_instituicao.length === 1
              ? p.por_instituicao[0].instituicao
              : "Suas instituições"
            : p.edicao}
        </h2>
        {!monitor && (
          <Button size="sm" onClick={() => definirOrganizando(true)}>
            Organizar núcleos
          </Button>
        )}
      </div>

      {/* Cartao aqui e PAPEL: o que a crianca escreveu para o padrinho de
          cesta e o de festa, ja digitalizado. Nao e quantidade de
          apadrinhamento — o rotulo diz "cartões" e a nota repete. */}
      <div className="metricas">
        <Metrica
          rotulo="Crianças"
          valor={p.criancas}
          destaque
          nota={plural(p.por_instituicao.length, "instituição", "instituições")}
        />
        <Metrica
          rotulo="Cartões de cesta"
          valor={p.cartoes_cesta}
          de={p.criancas}
          tom="cesta"
          nota={monitor ? `faltam ${p.criancas - p.cartoes_cesta}` : "cartões escritos e digitalizados"}
        />
        <Metrica
          rotulo="Cartões de festa"
          valor={p.cartoes_festa}
          de={p.criancas}
          tom="festa"
          nota={monitor ? `faltam ${p.criancas - p.cartoes_festa}` : "cartões escritos e digitalizados"}
        />
        <Metrica
          rotulo="Autorizações"
          valor={p.autorizacoes}
          de={p.criancas}
          nota={`faltam ${p.criancas - p.autorizacoes}`}
        />
      </div>
      <p className="painel__nota-cartao">
        Os números de cartões contam o <strong>papel</strong> que cada criança escreve para o
        padrinho — não a quantidade de apadrinhamentos.
      </p>

      <div className={monitor ? "painel__monitor" : "painel__grade painel__grade--meio"}>
        {!monitor && (
          <section className="cartao">
            <div className="cartao__topo">
              <h3 className="cartao__titulo">Por dia do evento</h3>
            </div>
            {dias.length === 0 && (
              <p className="campo__dica">Nenhuma instituição tem dia do evento ainda.</p>
            )}
            {dias.map((d) => (
              <div key={d.dia_evento_id} className="monitoria-dia">
                <div className="monitoria-dia__topo">
                  <EtiquetaDia data={d.data} descricao={d.descricao} />
                  <span>
                    <strong>{d.criancas}</strong> crianças ·{" "}
                    {plural(d.instituicoes, "instituição", "instituições")}
                  </span>
                </div>
                {temNucleos(d.dia_evento_id) ? (
                  <div className="monitoria-dia__nucleos">
                    {nucleosDoDia(d.dia_evento_id).map((n) => (
                      <div key={n.nucleo} className="monitoria-nucleo">
                        <span className="monitoria-nucleo__letra">{n.nucleo}</span>
                        <span className="monitoria-nucleo__conta">{n.criancas}</span>
                        <span className="monitoria-nucleo__batas">
                          {n.insts.map((i) => (
                            <span
                              key={i.instituicao_id}
                              className={`amostra-bata ${i.cor_bata_hex ? "" : "amostra-bata--vazia"}`}
                              style={i.cor_bata_hex ? { background: i.cor_bata_hex } : undefined}
                              title={`${i.sigla || i.instituicao}${i.cor_bata_nome ? ` · ${i.cor_bata_nome}` : ""}`}
                            />
                          ))}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="campo__dica">Núcleos deste dia ainda não organizados.</p>
                )}
                {(d.necessidade_especial > 0 || d.restricao_alimentar > 0) && (
                  <p className="campo__dica">
                    {plural(d.necessidade_especial, "necessidade especial", "necessidades especiais")} ·{" "}
                    {plural(d.restricao_alimentar, "restrição alimentar", "restrições alimentares")}
                  </p>
                )}
              </div>
            ))}
          </section>
        )}

        <section className="cartao">
          <div className="cartao__topo">
            <h3 className="cartao__titulo">Cuidados especiais</h3>
          </div>
          <p className="campo__dica" style={{ marginTop: 0 }}>
            {plural(p.necessidade_especial, "criança com necessidade especial", "crianças com necessidade especial")}{" "}
            · {plural(p.restricao_alimentar, "com alergia ou restrição", "com alergia ou restrição")}
          </p>
          {comCuidados.length === 0 ? (
            <p className="campo__dica">Nenhuma autorização com cuidado especial até agora.</p>
          ) : monitor ? (
            // Aberto, crianca a crianca: o monitor tem poucas, e precisa saber
            // quem sao sem clicar.
            comCuidados.map((i) => (
              <div key={i.instituicao_id} className="monitoria-cuidados__bloco">
                {p.por_instituicao.length > 1 && (
                  <h4 className="monitoria-cuidados__inst">{i.instituicao}</h4>
                )}
                <ul className="monitoria-cuidados-lista">
                  {i.cuidados.map((c) => (
                    <li key={c.crianca_id}>
                      <strong>{c.nome}</strong> <span className="campo__dica">{c.codigo}</span>
                      {c.necessidade_especial && <div>Necessidade especial: {c.necessidade_especial}</div>}
                      {c.restricao_alimentar && <div>Alergia ou restrição: {c.restricao_alimentar}</div>}
                    </li>
                  ))}
                </ul>
              </div>
            ))
          ) : (
            <ul className="monitoria-cuidados">
              {comCuidados.map((i) => (
                <li key={i.instituicao_id}>
                  <button
                    type="button"
                    className="monitoria-cuidados__item"
                    onClick={() => definirVendoCuidados(i)}
                  >
                    <span>{i.instituicao}</span>
                    <span className="monitoria-cuidados__conta">
                      {plural(i.cuidados.length, "criança", "crianças")} →
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="cartao">
        <div className="cartao__topo">
          <h3 className="cartao__titulo">Por instituição</h3>
          <span className="legenda">
            <span className="legenda__item legenda__item--cesta">cartão de cesta</span>
            <span className="legenda__item legenda__item--festa">cartão de festa</span>
            <span className="legenda__item legenda__item--autorizacao">autorização</span>
          </span>
        </div>
        <div className="lista-progresso lista-progresso--densa">
          {p.por_instituicao.map((i) => (
            <div key={i.instituicao_id} className="lista-progresso__item">
              <div className="lista-progresso__topo">
                <span className="lista-progresso__nome">
                  {i.cor_bata_hex && (
                    <span
                      className="amostra-bata"
                      style={{ background: i.cor_bata_hex }}
                      title={i.cor_bata_nome ?? ""}
                    />
                  )}
                  {i.instituicao}
                  {i.sigla && (
                    <span className="etiqueta etiqueta--neutra lista-progresso__sigla">{i.sigla}</span>
                  )}
                  {i.nucleo && (
                    <span className="etiqueta etiqueta--ok lista-progresso__sigla">
                      Núcleo {i.nucleo}
                    </span>
                  )}
                </span>
                <span className="lista-progresso__total">
                  {i.criancas}
                  {i.dia_evento_id && (
                    <span className="lista-progresso__falta">
                      {" "}
                      · {rotuloDia(i.dia_data, i.dia_descricao)}
                    </span>
                  )}
                </span>
              </div>
              <Progresso rotulo="Cartão cesta" valor={i.cartoes_cesta} de={i.criancas} tom="cesta" />
              <Progresso rotulo="Cartão festa" valor={i.cartoes_festa} de={i.criancas} tom="festa" />
              <Progresso rotulo="Autorização" valor={i.autorizacoes} de={i.criancas} tom="autorizacao" />
            </div>
          ))}
        </div>
      </section>

      {organizando && !monitor && (
        <OrganizarNucleos
          edicaoId={edicaoId}
          instituicoes={p.por_instituicao}
          aoFechar={() => definirOrganizando(false)}
          aoSalvar={(novo) => {
            definirP(novo);
            definirOrganizando(false);
          }}
        />
      )}

      {vendoCuidados && (
        <Modal
          rotulo="Cuidados especiais de"
          titulo={vendoCuidados.instituicao}
          aoFechar={() => definirVendoCuidados(null)}
        >
          <ul className="monitoria-cuidados-lista">
            {vendoCuidados.cuidados.map((c) => (
              <li key={c.crianca_id}>
                <strong>{c.nome}</strong> <span className="campo__dica">{c.codigo}</span>
                {c.necessidade_especial && <div>Necessidade especial: {c.necessidade_especial}</div>}
                {c.restricao_alimentar && <div>Alergia ou restrição: {c.restricao_alimentar}</div>}
              </li>
            ))}
          </ul>
        </Modal>
      )}
    </>
  );
}
