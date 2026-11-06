import { useState } from "react";
import { desmarcarIntercessao, marcarIntercessao } from "../../services/intercessao.js";
import { nomeCurto, primeiroNome } from "../../utils/nomes.js";

// Quantas etiquetas cabem na celula antes do "+N". O resto fica na dica.
const VISIVEIS = 2;

function quando(iso) {
  return new Date(iso).toLocaleDateString("pt-BR");
}

/** Uma vivencia de intercessao (missa, adoracao, terco, jejum) numa crianca.
 *
 *  O checkbox e de quem esta na sessao: marcado = eu ja ofereci esta vivencia
 *  por ela. Ao lado, uma etiqueta com o nome de cada pessoa que marcou, a
 *  minha inclusive. Cada um desmarca so o que e seu.
 *
 *  `aoErro` recebe a frase do servidor quando a marcacao falha.
 *  `compacta` e o celular: so o checkbox e quantas pessoas marcaram.
 */
export default function CelulaIntercessao({ crianca, vivencia, usuarioId, aoMudar, aoErro, compacta }) {
  const [salvando, definirSalvando] = useState(false);

  const marcas = (crianca.intercessoes ?? []).filter((m) => m.tipo === vivencia.tipo);
  const minha = marcas.some((m) => m.usuario_id === usuarioId);
  const dica = marcas.map((m) => `${nomeCurto(m.nome) || "Alguém"} · ${quando(m.em)}`).join("\n");

  async function alternar() {
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
    <span className="intercessao" onClick={(e) => e.stopPropagation()} title={dica || undefined}>
      <input
        type="checkbox"
        checked={minha}
        disabled={salvando}
        onChange={alternar}
        aria-label={`${vivencia.rotulo} por ${crianca.nome}`}
      />
      {compacta
        ? marcas.length > 0 && <span className="intercessao__conta">{marcas.length}</span>
        : (
          <>
            {marcas.slice(0, VISIVEIS).map((m, i) => (
              <span
                key={`${m.usuario_id}-${i}`}
                className={`etiqueta ${m.usuario_id === usuarioId ? "etiqueta--ok" : "etiqueta--neutra"} intercessao__etiqueta`}
              >
                {primeiroNome(m.nome) || "Alguém"}
              </span>
            ))}
            {marcas.length > VISIVEIS && (
              <span className="intercessao__conta">+{marcas.length - VISIVEIS}</span>
            )}
          </>
        )}
    </span>
  );
}
