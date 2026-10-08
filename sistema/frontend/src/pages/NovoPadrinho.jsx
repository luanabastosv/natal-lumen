import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import Button from "../components/core/Button.jsx";
import { AvisoParecidos, CamposPadrinho } from "../components/dados/CamposPadrinho.jsx";
import { PADRINHO_NOVO, dadosDoPadrinho, padrinhoCompleto } from "../components/dados/padrinho.js";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useNotificar } from "../contexts/useNotificar.js";
import { useSessao } from "../contexts/useSessao.js";
import { criarPadrinho } from "../services/padrinhos.js";

/** Cadastrar um padrinho, como PAGINA — o caminho do celular.
 *
 * Mesmo desenho do passo a passo de apadrinhar, que vem logo depois: o topo
 * e o botao fixos, e so os campos rolam. A janela espremia o formulario e o
 * teclado cobria o botao de salvar.
 *
 * Salvar ja leva a apadrinhar por este padrinho. Se o nome digitado for de
 * um padrinho que ja existe, o aviso leva direto a apadrinhar por ele, sem
 * cadastrar de novo. Os dois caminhos SUBSTITUEM esta pagina no historico: o
 * "voltar" do celular, la do apadrinhar, cai na lista, e nao num formulario
 * que ja foi salvo.
 */
export default function NovoPadrinho() {
  const { edicaoAtiva, pode } = useSessao();
  const navegar = useNavigate();
  const notificar = useNotificar();
  const [campos, definirCampos] = useState(PADRINHO_NOVO);
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState("");

  const apadrinharDepois = pode("registrar_pagamentos_padrinho");

  // A pagina cobre a tela e rola so por dentro.
  useEffect(() => {
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = antes;
    };
  }, []);

  function apadrinharPor(id) {
    navegar(`/padrinhos/${id}/apadrinhar`, { replace: true });
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      const novo = await criarPadrinho({
        edicao_id: Number(edicaoAtiva),
        ...dadosDoPadrinho(campos),
      });
      notificar(`${novo.nome} cadastrado.`);
      if (apadrinharDepois) apadrinharPor(novo.id);
      else navegar("/padrinhos", { replace: true });
    } catch (e) {
      definirErro(e.message);
      definirSalvando(false);
    }
  }

  return createPortal(
    <form className="apadrinhar-pagina" onSubmit={salvar}>
      <header className="apadrinhar-pagina__topo">
        <button
          type="button"
          className="pasta-aberta__voltar"
          onClick={() => !salvando && navegar("/padrinhos")}
        >
          ← Padrinhos
        </button>
        <div className="pagina__eyebrow">Captação</div>
        <h1 className="pagina__titulo">Novo padrinho</h1>
      </header>

      <div className="apadrinhar-pagina__meio formulario-pagina">
        <Mensagem tipo="erro">{erro}</Mensagem>
        <CamposPadrinho
          campos={campos}
          definirCampos={definirCampos}
          avisoNome={
            <AvisoParecidos
              nome={campos.nome}
              edicaoId={edicaoAtiva}
              aoEscolher={(p) => apadrinharPor(p.id)}
            />
          }
        />
      </div>

      <div className="apadrinhar-pagina__rodape">
        <div className="passos__rodape">
          <Button
            type="submit"
            variant="secondary"
            carregando={salvando}
            disabled={!edicaoAtiva || !padrinhoCompleto(campos)}
          >
            {apadrinharDepois ? "Salvar e apadrinhar" : "Salvar"}
          </Button>
        </div>
      </div>
    </form>,
    document.body,
  );
}
