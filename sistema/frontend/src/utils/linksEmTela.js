/** Os links que alguma tela esta acompanhando agora, de perto.
 *
 * Logo depois de gerar o link, a propria janela confere o pagamento e segue
 * para o agradecimento. Enquanto ela esta aberta, o aviso geral (no canto da
 * tela) nao aparece para o mesmo link: seriam dois chamados para o mesmo
 * gesto. */
export const linksEmTela = new Set();
