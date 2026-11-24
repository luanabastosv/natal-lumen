import { useState } from "react";
import Button from "../core/Button.jsx";
import { Entrada } from "../core/Campo.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import { listarCriancas } from "../../services/criancas.js";
import { trocarCrianca } from "../../services/padrinhos.js";

const TIPOS = { cesta: "cesta", festa: "festa" };

/** Passa o apadrinhamento de uma crianca desistente para outra.
 *
 * E o mesmo apadrinhamento que muda de crianca: o pagamento, o valor e o
 * comissario que captou ficam. A desistente fica livre. So a coordenacao
 * (por enquanto) chega aqui; o servidor confere de novo.
 *
 * A busca e por nome ou codigo na edicao inteira, como no apadrinhar de quem
 * coordena. Quem nao pode receber (ja tem padrinho daquele tipo, desistiu,
 * esta reservada por um link) aparece na lista apagada, com o motivo: some-la
 * deixaria a pessoa achando que a busca falhou.
 */
export default function TrocarCrianca({ apadrinhamento, padrinho, aoTrocar, aoFechar }) {
  const tipo = apadrinhamento.tipo;
  const [busca, definirBusca] = useState("");
  const [resultados, definirResultados] = useState(null);
  const [procurando, definirProcurando] = useState(false);
  const [escolhida, definirEscolhida] = useState(null);
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState("");

  async function procurar(evento) {
    evento.preventDefault();
    const termo = busca.trim();
    if (!termo) return;
    definirErro("");
    definirEscolhida(null);
    definirProcurando(true);
    try {
      const r = await listarCriancas({
        edicao_id: padrinho.edicao_id,
        busca: termo,
        por_pagina: 10,
      });
      definirResultados(r.itens);
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirProcurando(false);
    }
  }

  function motivo(c) {
    if (c.desistiu_em) return "desistiu";
    if (c[`tem_padrinho_${tipo}`]) return `já tem padrinho de ${TIPOS[tipo]}`;
    if (c[`promessa_${tipo}`]) return "reservada, a pagar";
    if (tipo === "festa" && c.festa_liberada === false) return "festa ainda não liberada";
    return "";
  }

  async function confirmar() {
    definirErro("");
    definirSalvando(true);
    try {
      aoTrocar(await trocarCrianca(apadrinhamento.id, escolhida.id));
    } catch (e) {
      definirErro(e.message);
      definirSalvando(false);
    }
  }

  return (
    <Modal
      rotulo={`Apadrinhamento de ${TIPOS[tipo]} de ${padrinho.nome}`}
      titulo="Vincular nova criança"
      aoFechar={() => !salvando && aoFechar()}
      rodape={
        <div className="barra-acoes barra-acoes--fim" style={{ marginTop: 0 }}>
          <Button variant="ghost" onClick={aoFechar} disabled={salvando}>
            Cancelar
          </Button>
          <Button onClick={confirmar} disabled={!escolhida} carregando={salvando}>
            {escolhida ? `Vincular ${escolhida.codigo} ${escolhida.nome.split(" ")[0]}` : "Escolha a criança"}
          </Button>
        </div>
      }
    >
      <p className="exclusao__texto" style={{ marginTop: 0 }}>
        <strong>
          {apadrinhamento.crianca_codigo} {apadrinhamento.crianca_nome}
        </strong>{" "}
        desistiu. O apadrinhamento é vinculado à criança que você escolher, com o mesmo
        pagamento: ninguém paga de novo. {apadrinhamento.crianca_primeiro_nome} fica sem
        padrinho e, se voltar, volta livre.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>

      <form className="barra-acoes" onSubmit={procurar}>
        <Entrada
          classe="barra-acoes__busca"
          tipo="search"
          enterKeyHint="search"
          value={busca}
          onChange={(e) => definirBusca(e.target.value)}
          placeholder="Nome ou código da criança"
          autoFocus
        />
        <Button type="submit" size="sm" variant="ghost" carregando={procurando}>
          Buscar
        </Button>
      </form>

      {resultados && resultados.length === 0 && (
        <p className="campo__dica">Nenhuma criança com esta busca.</p>
      )}
      {resultados && resultados.length > 0 && (
        <ul className="troca__lista">
          {resultados.map((c) => {
            const barrada = motivo(c);
            const marcada = escolhida?.id === c.id;
            return (
              <li key={c.id}>
                <button
                  type="button"
                  className={`troca__item ${marcada ? "troca__item--marcada" : ""}`}
                  onClick={() => definirEscolhida(c)}
                  disabled={Boolean(barrada)}
                  aria-pressed={marcada}
                >
                  <span className="troca__nome">
                    <span className="ficha__linha-codigo">{c.codigo}</span>
                    {c.nome}, {c.idade}
                  </span>
                  <span className="troca__detalhe">{barrada || c.instituicao}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Modal>
  );
}
