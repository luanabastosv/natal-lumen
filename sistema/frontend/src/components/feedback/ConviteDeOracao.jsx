import { useEffect, useState } from "react";
import Button from "../core/Button.jsx";
import Modal from "./Modal.jsx";
import { useSessao } from "../../contexts/useSessao.js";
import { buscarConvite } from "../../services/oracao.js";

/** O convite a rezar do primeiro acesso do dia.
 *
 * Mora no layout, e nao numa pagina: a pessoa entra no sistema por onde o
 * trabalho dela pede — o check-in no dia do evento, a lista de criancas, o
 * financeiro — e o convite tem de alcancar quem nunca passa pelo painel.
 *
 * Quem lembra que ela ja viu hoje e o NAVEGADOR, nao o servidor. E uma escolha
 * com consequencia: quem abre no celular e depois no computador ve duas vezes,
 * e limpar o cache faz aparecer de novo. Em troca, nao ha tabela para manter
 * nem escrita a cada login.
 */

const CHAVE = "nl_oracao";

/** A data de hoje como AAAA-MM-DD, no fuso de quem esta olhando.
 *
 * Feita a mao de proposito: `toISOString()` converte para UTC, e a partir das
 * 21h em Brasilia ele ja responde a data de amanha — o convite sumiria no fim
 * da tarde e voltaria de madrugada.
 */
function hoje() {
  const d = new Date();
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${dia}`;
}

// A chave leva o id do usuario: duas pessoas que usam o mesmo computador —
// a coordenacao e o monitor no dia do evento — nao roubam o convite uma da
// outra.
function jaViuHoje(usuarioId) {
  try {
    return localStorage.getItem(`${CHAVE}_${usuarioId}`) === hoje();
  } catch {
    // Navegador com armazenamento bloqueado: o convite aparece a cada visita.
    // Aparecer demais e melhor do que quebrar a tela.
    return false;
  }
}

function marcarComoVisto(usuarioId) {
  try {
    localStorage.setItem(`${CHAVE}_${usuarioId}`, hoje());
  } catch {
    // sem problema: vale so para esta visita
  }
}

export default function ConviteDeOracao() {
  const { usuario, edicaoAtiva } = useSessao();
  const [convite, definirConvite] = useState(null);

  useEffect(() => {
    if (!usuario || !edicaoAtiva) return;
    if (jaViuHoje(usuario.id)) return;

    let vivo = true;

    buscarConvite(edicaoAtiva)
      .then((dados) => {
        // Sem crianca no alcance nao ha convite: a edicao ainda nao recebeu
        // lista, ou este comissario ainda nao tem nenhuma na mao.
        if (!vivo || !dados?.crianca) return;
        // Marcado ao APARECER, e nao ao fechar: "uma vez por dia" e sobre ter
        // sido convidada, e recarregar a pagina nao pode trazer o convite de
        // volta.
        marcarComoVisto(usuario.id);
        definirConvite(dados);
      })
      .catch(() => {
        // Um convite que nao carregou nao pode atrapalhar o trabalho: a pessoa
        // entrou para fazer check-in, nao para ler um erro. Amanha ele volta.
      });

    return () => {
      vivo = false;
    };
  }, [usuario, edicaoAtiva]);

  if (!convite) return null;

  const primeiroNome = usuario.nome.trim().split(" ")[0];

  return (
    <Modal
      titulo="Convite de oração do dia"
      cabecalho={false}
      aoFechar={() => definirConvite(null)}
      rodape={
        <Button larguraTotal onClick={() => definirConvite(null)}>
          Amém
        </Button>
      }
    >
      <div className="convite">
        <img src="/acesso/images/star-mascot-amarelo.svg" alt="" className="convite__mascote" />

        <h2 className="convite__saudacao">Olá, {primeiroNome}!</h2>
        <p className="convite__pergunta">Vamos rezar uma ave-maria agora?</p>

        <p className="convite__chamado">Hoje te convidamos a interceder pelo coração de</p>
        <p className="convite__crianca">{convite.crianca}</p>
        <p className="convite__instituicao">{convite.instituicao}</p>

        <p className="convite__frase">Cada vida que você salva é o mundo que você muda</p>
      </div>
    </Modal>
  );
}
