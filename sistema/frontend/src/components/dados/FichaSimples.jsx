import { Fragment } from "react";
import Modal from "../feedback/Modal.jsx";

/** A janela que devolve as colunas que a lista escondeu no celular.
 *
 * Quase toda lista do sistema nasceu com dez colunas porque no monitor elas
 * cabem. No celular nao cabem, e a saida antiga era rolar de lado — que esconde
 * o dado atras de um gesto que ninguem promete e ninguem descobre sozinho.
 * O padrao passa a ser o da lista de criancas: a linha mostra o que faz alguem
 * RECONHECER o registro, e o resto vem aqui, a um toque.
 *
 * `campos`: [{ rotulo, valor, largo? }] — `largo` para o texto corrido
 * (observacao, endereco), que ocupa a faixa inteira em vez de meia. Entradas
 * falsas sao descartadas, para a pagina poder escrever
 * `podeVerValores && { ... }` sem montar o array em duas etapas.
 *
 * Nao substitui as fichas de verdade (FichaCrianca, FichaPadrinho): aquelas
 * buscam detalhe no servidor e tem acoes proprias. Esta so mostra, em coluna,
 * o que ja estava na linha.
 */
export default function FichaSimples({ rotulo, titulo, campos, rodape, aoFechar }) {
  return (
    <Modal rotulo={rotulo} titulo={titulo} aoFechar={aoFechar} rodape={rodape}>
      {/* Fragment, e nao um <div> por par: `.ficha` e um grid de duas colunas e
          quem se alinha nele sao os <dt>/<dd> — embrulhados, cada par viraria
          uma caixa so e o rotulo pararia em cima do valor. */}
      <dl className="ficha ficha--duas">
        {campos.filter(Boolean).map((campo) => (
          <Fragment key={campo.rotulo}>
            <dt className={campo.largo ? "ficha__dt-largo" : undefined}>{campo.rotulo}</dt>
            <dd className={campo.largo ? "ficha__dd-largo" : undefined}>
              {campo.valor ?? "—"}
            </dd>
          </Fragment>
        ))}
      </dl>
    </Modal>
  );
}
