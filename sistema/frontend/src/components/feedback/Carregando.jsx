import Estrelinhas from "./Estrelinhas.jsx";

/** A espera do sistema: estrelinhas piscando e a frase do que esta acontecendo.
 *
 * A frase nunca e "Carregando..." sozinha quando da para ser melhor — cada
 * chamada diz o que esta sendo buscado, porque "Somando o caixa da edicao" faz
 * a espera parecer trabalho e "Carregando" faz parecer travamento.
 *
 * `tela` e para quando a pagina inteira ainda nao tem o que mostrar: ai as
 * estrelinhas crescem e sobem para cima do texto, no meio da area vazia — e
 * no tamanho grande o mascote aparece de rosto e tudo.
 */
export default function Carregando({ children = "Carregando...", tela = false }) {
  const conteudo = (
    <div className={tela ? "carregando carregando--tela" : "carregando"} role="status">
      <Estrelinhas tamanho={tela ? 34 : 16} />
      <span>{children}</span>
    </div>
  );

  return tela ? <div className="carregando-tela">{conteudo}</div> : conteudo;
}
