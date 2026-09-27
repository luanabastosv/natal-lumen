import Button from "../core/Button.jsx";
import Carregando from "./Carregando.jsx";
import Mensagem from "./Mensagem.jsx";
import Modal from "./Modal.jsx";

/** Rotulo de cada chave devolvida por /dependencias.
 *
 * O backend manda a chave crua e sem acento ("criancas", "cartoes") de
 * proposito: o acento e a flexao de numero sao assunto de tela, e e aqui que
 * o sistema escreve em portugues de verdade. Chave nova que chegue sem rotulo
 * aparece como veio, em vez de sumir da conta.
 */
const ROTULOS = {
  edicoes: ["edição", "edições"],
  instituicoes: ["instituição", "instituições"],
  dias: ["dia do evento", "dias do evento"],
  criancas: ["criança", "crianças"],
  cartoes: ["cartão digitalizado", "cartões digitalizados"],
  kits: ["kit", "kits"],
  padrinhos: ["padrinho", "padrinhos"],
  apadrinhamentos: ["apadrinhamento", "apadrinhamentos"],
  pagamentos: ["pagamento registrado", "pagamentos registrados"],
  compras: ["compra", "compras"],
  acessos: ["acesso de equipe", "acessos de equipe"],
  atribuicoes: ["atribuição de comissário", "atribuições de comissário"],
  grupos: ["grupo da comunidade", "grupos da comunidade"],
};

function rotular({ chave, quantidade }) {
  const [singular, plural] = ROTULOS[chave] ?? [chave, chave];
  return `${quantidade} ${quantidade === 1 ? singular : plural}`;
}

/** Janela de "apagar mesmo?", com a conta do que vai junto.
 *
 * Apagar cidade, edicao ou instituicao nunca e apagar uma linha: cada uma
 * segura um bloco de dados atras dela. Quem clica precisa ver o TAMANHO desse
 * bloco antes de decidir — por isso a janela abre pedindo a conta ao servidor
 * e o botao que apaga so libera depois que a conta chega.
 *
 * `dependencias` em null quer dizer "ainda perguntando".
 */
export default function ConfirmarExclusao({
  rotulo,
  nome,
  dependencias,
  // Uma frase a mais sobre o que este cadastro em particular leva ou deixa —
  // que a edicao nao leva as instituicoes, por exemplo.
  nota,
  erro,
  apagando = false,
  aoConfirmar,
  aoFechar,
}) {
  // Sem a conta em maos o botao nao libera: apagar sem ter visto o que vai
  // junto e exatamente o que esta janela existe para evitar. Se a conta falhou,
  // o que aparece e o erro — nao adianta seguir dizendo "conferindo".
  const podeApagar = Boolean(dependencias);
  const conferindo = !dependencias && !erro;
  const itens = dependencias?.itens ?? [];
  const total = dependencias?.total ?? 0;

  function fechar() {
    if (!apagando) aoFechar();
  }

  return (
    <Modal
      rotulo={rotulo}
      titulo={`Apagar ${nome}?`}
      aoFechar={fechar}
      rodape={
        <div className="barra-acoes barra-acoes--fim" style={{ marginTop: 0 }}>
          <Button
            variant="perigo"
            onClick={aoConfirmar}
            carregando={apagando}
            disabled={!podeApagar}
          >
            {apagando ? "Apagando..." : "Apagar mesmo assim"}
          </Button>
          <Button variant="ghost" onClick={fechar} disabled={apagando}>
            Cancelar
          </Button>
        </div>
      }
    >
      <Mensagem tipo="erro">{erro}</Mensagem>

      {conferindo ? (
        <Carregando>Conferindo o que está ligado a {nome}...</Carregando>
      ) : !dependencias ? null : total === 0 ? (
        <p className="exclusao__texto">
          Nada depende de <strong>{nome}</strong> — apagar não leva mais nada junto.
        </p>
      ) : (
        <>
          <p className="exclusao__texto">
            Apagar <strong>{nome}</strong> leva junto:
          </p>
          <ul className="exclusao__lista">
            {itens.map((item) => (
              <li key={item.chave}>{rotular(item)}</li>
            ))}
          </ul>
        </>
      )}

      {nota && <p className="campo__dica">{nota}</p>}

      <Mensagem tipo="aviso">Não dá para voltar atrás depois de apagar.</Mensagem>
    </Modal>
  );
}
