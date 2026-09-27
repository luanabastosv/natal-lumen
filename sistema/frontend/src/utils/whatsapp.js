/** Links e envio para o WhatsApp.
 *
 * Um limite da plataforma que vale ter escrito aqui: o link do WhatsApp
 * (wa.me / web.whatsapp.com/send) carrega SO TEXTO. Nao existe parametro para
 * anexar arquivo — nem na web, nem no aplicativo. Por isso o envio da arte
 * segue dois caminhos:
 *
 *   celular  -> navigator.share com o arquivo: a folha nativa entrega o PNG
 *               ao WhatsApp de verdade.
 *   desktop  -> baixa o PNG e abre a conversa com o texto pronto; quem envia
 *               arrasta o arquivo para a janela.
 */

/** So digitos, com o 55 na frente. Devolve null se nao parece telefone. */
export function numeroLimpo(numero) {
  const so = (numero ?? "").replace(/\D/g, "");
  if (so.length < 10) return null;
  return so.startsWith("55") ? so : `55${so}`;
}

/** Link da conversa, opcionalmente com a mensagem ja escrita. */
export function linkWhatsapp(numero, texto) {
  const limpo = numeroLimpo(numero);
  if (!limpo) return null;

  const base = `https://wa.me/${limpo}`;
  return texto ? `${base}?text=${encodeURIComponent(texto)}` : base;
}

/** O navegador sabe compartilhar ESTE arquivo? (praticamente so no celular) */
export function podeCompartilharArquivo(arquivo) {
  return Boolean(navigator.canShare?.({ files: [arquivo] }));
}
