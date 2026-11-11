import { useState } from "react";
import { desmarcarIntercessao, marcarIntercessao } from "../../services/intercessao.js";
import { nomeCurto, primeiroNome } from "../../utils/nomes.js";

function quando(iso) {
  return new Date(iso).toLocaleDateString("pt-BR");
}

/** Uma vivencia de intercessao (missa, adoracao, terco, jejum) numa crianca.
 *
 *  Cada vivencia de uma crianca e de uma pessoa so: quem marcou primeiro.
 *  Marcada, o checkbox aparece marcado para todo mundo, com o nome de quem
 *  marcou ao lado; so essa pessoa desmarca. Para os outros fica travado.
 *
 *  `aoErro` recebe a frase do servidor quando a marcacao falha.
 */
export default function CelulaIntercessao({ crianca, vivencia, usuarioId, aoMudar, aoErro }) {
  const [salvando, definirSalvando] = useState(false);

  const dono = (crianca.intercessoes ?? []).find((m) => m.tipo === vivencia.tipo);
  const minha = dono?.usuario_id === usuarioId;
  const deOutro = Boolean(dono) && !minha;
  const nome = dono ? nomeCurto(dono.nome) || "Alguém" : "";
  const dica = dono
    ? `${deOutro ? `Marcada por ${nome}` : "Você marcou"} · ${quando(dono.em)}`
    : undefined;

  async function alternar() {
    if (deOutro) return;
    definirSalvando(true);
    try {
      const novas = minha
        ? await desmarcarIntercessao(crianca.id, vivencia.tipo)
        : await marcarIntercessao(crianca.id, vivencia.tipo);
      // A resposta traz as marcacoes da crianca inteira, das quatro vivencias.
      aoMudar(novas);
    } catch (e) {
      // Erro fica na pagina, junto da lista, e nao num recado que some.
      aoErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  return (
    // O clique na linha abre a ficha no celular: aqui ele para.
    <span
      className={`intercessao${deOutro ? " intercessao--de-outro" : ""}`}
      onClick={(e) => e.stopPropagation()}
      title={dica}
    >
      <input
        type="checkbox"
        checked={Boolean(dono)}
        disabled={salvando || deOutro}
        onChange={alternar}
        aria-label={
          deOutro
            ? `${vivencia.rotulo} por ${crianca.nome}, marcada por ${nome}`
            : `${vivencia.rotulo} por ${crianca.nome}`
        }
      />
      {dono && (
        <span
          className={`etiqueta ${minha ? "etiqueta--ok" : "etiqueta--neutra"} intercessao__etiqueta`}
        >
          {primeiroNome(dono.nome) || "Alguém"}
        </span>
      )}
    </span>
  );
}
