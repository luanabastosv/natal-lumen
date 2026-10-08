import { useCallback, useEffect, useState } from "react";
import Button from "../core/Button.jsx";
import { ChevronDireita, ChevronEsquerda, Visto } from "../core/icones.jsx";
import Mensagem from "../feedback/Mensagem.jsx";
import Modal from "../feedback/Modal.jsx";
import { urlDaImagemDoLote } from "../../services/cartoes.js";
import RespostasAutorizacao from "./RespostasAutorizacao.jsx";
import { respostasCompletas } from "./autorizacao.js";
import EtiquetaDesistente from "../core/EtiquetaDesistente.jsx";

/** Conferencia do lote, um cartao por vez.
 *
 * E a unica janela depois de ler os arquivos — a lista da previa, que ficava
 * aberta atras desta, saiu. Ela responde a pergunta que a pessoa faz com a
 * pilha de papel na mao: ESTE cartao e mesmo o da crianca que o codigo diz? A
 * foto que nao vai subir aparece na sequencia com o motivo embaixo. Por isso a foto vem inteira (a miniatura
 * de 220px da lista mostra que ha um cartao, nao O cartao) e o codigo fica do
 * lado do nome.
 *
 * Passar para o seguinte E a confirmacao: nao ha botao separado de "confere",
 * porque ele so registraria de novo o que a pessoa acabou de fazer com os
 * olhos. Voltar nao desfaz nada — quem volta e para reler, nao para desdizer.
 *
 * Na pilha de autorizacoes a foto ganha, ao lado, as tres perguntas que o
 * monitor responde lendo o papel. Ai passar exige as respostas: a foto so
 * conta como conferida quando o que ela diz ja foi anotado.
 */
export default function ConferirCartoes({
  previa,
  conferidos,
  aoConferir,
  aoFechar,
  aoGuardar,
  salvando = false,
  erro = "",
  // So na pilha de autorizacoes: as respostas de cada foto, pelo indice.
  respostas = {},
  aoResponder,
}) {
  const itens = previa.arquivos;
  const ehAutorizacao = previa.tipo === "autorizacao";

  // Abre no primeiro que ainda ninguem viu. Na primeira vez e o zero; se a
  // pessoa fechou no meio e voltou, e de onde ela parou.
  const [atual, definirAtual] = useState(() => {
    const parado = itens.findIndex((a) => !conferidos.includes(a.indice));
    return parado === -1 ? 0 : parado;
  });

  const item = itens[atual];
  const ultimo = atual === itens.length - 1;
  // Foto que nao vai subir nao tem o que responder: passa direto.
  const faltaResponder =
    ehAutorizacao && item.valida && !respostasCompletas(respostas[item.indice]);
  const faltam = itens.filter(
    (a) => a.valida && !conferidos.includes(a.indice) && a.indice !== item.indice,
  ).length;

  const passar = useCallback(() => {
    if (faltaResponder) return;
    aoConferir(itens[atual].indice);
    definirAtual((i) => Math.min(i + 1, itens.length - 1));
  }, [aoConferir, atual, itens, faltaResponder]);

  const voltar = useCallback(() => definirAtual((i) => Math.max(i - 1, 0)), []);

  // As setas do teclado fazem o mesmo que os chevrons: com a pilha de papel na
  // mao, a outra mao fica no teclado, nao no mouse.
  useEffect(() => {
    const aoTeclar = (e) => {
      // Dentro do campo do "qual", a seta anda no texto, nao na pilha.
      if (e.target.closest?.("input, textarea")) return;
      if (e.key === "ArrowRight" && !ultimo) passar();
      if (e.key === "ArrowLeft") voltar();
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [passar, voltar, ultimo]);

  // Adianta a foto seguinte. Sao ~15 cartoes em sequencia: sem isto cada
  // chevron piscaria branco enquanto o navegador busca a imagem.
  useEffect(() => {
    const seguinte = itens[atual + 1];
    if (seguinte?.valida) {
      const img = new Image();
      img.src = urlDaImagemDoLote(previa.id, seguinte.indice);
    }
  }, [atual, itens, previa.id]);

  const jaConferido = conferidos.includes(item.indice);
  // A pilha de autorizacoes passa pela mesma conferencia; so o nome muda.
  const [um, varios] =
    previa.tipo === "autorizacao" ? ["autorização", "autorização(ões)"] : ["cartão", "cartão(ões)"];
  const tipo = previa.tipo === "autorizacao" ? "autorização" : previa.tipo;

  return (
    <Modal
      rotulo={`Conferência · ${um} ${atual + 1} de ${itens.length} · ${tipo}`}
      titulo={item.crianca_nome ?? item.arquivo}
      tamanho="largo"
      // Enquanto grava, nao fecha: um Esc sem querer nao pode interromper o que
      // ja esta indo para a base.
      aoFechar={() => !salvando && aoFechar()}
      rodape={
        <div className="conferencia__rodape">
          <span className="campo__dica" style={{ marginTop: 0 }}>
            {faltaResponder
              ? "Responda as três perguntas para seguir."
              : faltam > 0
                ? `Faltam ${faltam} ${varios} para conferir.`
                : "Todos conferidos."}
          </span>
          {ultimo ? (
            <Button
              onClick={() => {
                aoConferir(item.indice);
                aoGuardar();
              }}
              disabled={previa.validas === 0 || faltaResponder}
              carregando={salvando}
              iconLeft={<Visto t={15} />}
            >
              Guardar {previa.validas} {varios}
            </Button>
          ) : (
            <Button onClick={passar} disabled={faltaResponder}>
              Conferir e passar
            </Button>
          )}
        </div>
      }
    >
      <Mensagem tipo="erro">{erro}</Mensagem>

      <div className={ehAutorizacao && item.valida ? "conferencia__com-respostas" : undefined}>
      <div className="conferencia__palco">
        <button
          type="button"
          className="conferencia__seta"
          onClick={voltar}
          disabled={atual === 0}
          aria-label="Cartão anterior"
        >
          <ChevronEsquerda t={20} />
        </button>

        {item.valida ? (
          <img
            /* A chave troca a cada cartao para o navegador nao segurar a foto
               anterior na tela enquanto a nova carrega. */
            key={item.indice}
            className="cartao-imagem conferencia__foto"
            src={urlDaImagemDoLote(previa.id, item.indice)}
            alt={`${ehAutorizacao ? "Autorização" : "Cartão"} de ${item.crianca_nome ?? item.arquivo}`}
          />
        ) : (
          <div className="conferencia__sem-foto">
            Esta foto não vai subir, então não há o que conferir.
          </div>
        )}

        <button
          type="button"
          className="conferencia__seta"
          onClick={passar}
          disabled={ultimo || faltaResponder}
          aria-label="Conferir e passar ao próximo"
        >
          <ChevronDireita t={20} />
        </button>
      </div>

      {ehAutorizacao && item.valida && (
        <RespostasAutorizacao
          /* A chave troca com a foto: o "qual" que abre com foco precisa
             nascer de novo em cada crianca. */
          key={item.indice}
          respostas={respostas[item.indice]}
          aoMudar={(r) => aoResponder(item.indice, r)}
        />
      )}
      </div>

      <div className="conferencia__dados">
        <span className="conferencia__codigo">{item.codigo ?? "sem código"}</span>
        <div className="conferencia__nome">
          {item.crianca_nome ?? <span className="celula--vazia">{item.arquivo}</span>}
          {item.crianca_desistiu_em && <EtiquetaDesistente className="etiqueta--ao-lado" />}
          <span className="campo__dica" style={{ marginTop: 2, display: "block" }}>
            {item.instituicao ? `${item.instituicao} · ` : ""}
            {item.arquivo}
          </span>
        </div>
        <span className="ficha__linha-etiquetas">
          {item.valida ? (
            jaConferido ? (
              <span className="etiqueta etiqueta--ok">conferido</span>
            ) : (
              <span className="etiqueta etiqueta--espera">a conferir</span>
            )
          ) : (
            <span className="etiqueta etiqueta--parado">não vai subir</span>
          )}
        </span>
      </div>

      {(item.erros.length > 0 || item.avisos.length > 0) && (
        <p className="campo__dica" style={{ marginBottom: 0 }}>
          {[...item.erros, ...item.avisos].join(" ")}
        </p>
      )}
    </Modal>
  );
}
