import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ApadrinharCriancas from "../components/dados/ApadrinharCriancas.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { detalharPadrinho } from "../services/padrinhos.js";

/** O passo a passo de apadrinhar como PAGINA — o caminho do celular.
 *
 * No computador ele abre por cima da ficha do padrinho, numa janela. No
 * celular a janela ficava espremida: a lista de criancas rolava dentro de
 * uma caixa pequena e o teclado cobria os botoes. Aqui ele ocupa a tela, e o
 * "voltar" do proprio celular sai dele como de qualquer pagina.
 */
export default function Apadrinhar() {
  const { id } = useParams();
  const navegar = useNavigate();
  const [padrinho, definirPadrinho] = useState(null);
  const [erro, definirErro] = useState("");

  // A pagina cobre a tela e rola so por dentro: o fundo nao pode rolar junto
  // quando o dedo passa do fim da lista.
  useEffect(() => {
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = antes;
    };
  }, []);

  useEffect(() => {
    detalharPadrinho(id)
      .then(definirPadrinho)
      .catch((e) => definirErro(e.message));
  }, [id]);

  if (erro) return <Mensagem tipo="erro">{erro}</Mensagem>;
  if (!padrinho) return <Carregando tela>Carregando o padrinho...</Carregando>;

  return (
    <ApadrinharCriancas
      comoPagina
      padrinho={padrinho}
      aoMudar={definirPadrinho}
      aoFechar={() => navegar("/padrinhos")}
    />
  );
}
