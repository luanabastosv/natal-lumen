/** Tres estrelinhas piscando em fila: o sinal de "estou buscando" do sistema.
 *
 * A estrela e a nossa — o mesmo desenho do mascote da logo, copiado do
 * star-mascot-outline.svg do design system. Nao e um sparkle generico: as
 * cinco pontas sao irregulares e os bracos arredondados, e e essa silhueta
 * torta que faz a espera parecer do Natal Lumen.
 *
 * Nao da para usar o arquivo com <img> porque a cor precisa mudar no meio da
 * animacao, e imagem nao aceita CSS por dentro. Entao o path vem inline, mas
 * copiado letra por letra do SVG oficial.
 *
 * O ROSTO so entra quando ha espaco para ele: os olhos tem 3,4 das 60,9
 * unidades de largura do desenho, ou seja em 16px de estrela eles dariam um
 * ponto de 0,9px cada — nao leriam como olhos, leriam como sujeira. Abaixo do
 * limiar fica so a silhueta, que continua sendo a estrela da marca.
 *
 * A que esta acesa fica amarela e cresce; as outras duas ficam em navy-200.
 * Amarelo sozinho sobre fundo branco quase some — e o azul claro que garante
 * que sempre haja alguma coisa visivel ali, mesmo no quadro em que nenhuma
 * estrela esta no pico.
 *
 * E decorativo: quem usa leitor de tela ouve o texto do lado, nunca isto.
 */

// Copiados de public/images/star-mascot-outline.svg. O rosto sao tres
// subpaths no sentido contrario, que viram furos na silhueta pela regra
// nonzero — e por isso que os olhos herdam o fundo em vez de precisar de cor.
const SILHUETA =
  "M10.79,49.77c-1.34-1.61-1.35-4.41-1.26-6.44.14-2.86.94-5.13,1.38-7.82.18-1.09.01-1.05-.74-1.72-2.27-2.03-4.44-3.94-6.46-6.24C2.32,25.96-.28,22.83.02,20.62c.58-4.19,4.64-5.6,8.18-6.5,3.04-.77,6.26-1.06,9.4-1.1.24-.04.41-.56.61-.67.31-.16.93-.03,1.25-.22,2.65-3.75,5.37-7.55,8.96-10.48,2.23-1.82,6.23-2.35,8.59-.48,1.82,1.44,4.44,5.87,5.43,8.04.31.67,1.79,4.95,2.01,5.11,1.79.53,3.68.47,5.52.74,2.13.31,4.59,1.22,6.58,2.05,3.43,1.43,4.85,2.97,4.19,6.88-.42,2.51-4.09,5.79-5.99,7.43-1.6,1.38-3.34,2.59-4.96,3.95-.1.26.5,2.04.56,2.52.06.52.02,1.03.08,1.57.13,1.18.58,2.37.72,3.5.34,2.72.03,7.94-3.25,8.67-4.56,1.02-10.21-2.07-13.8-4.67-.69-.5-1.76-1.55-2.47-1.87-.16-.07-.59-.19-.76-.2-.68-.02-2.72,1.67-3.41,2.1-1.64,1.02-4.09,2.06-5.9,2.8-3.23,1.32-8.09,3.21-10.78-.01Z";
const ROSTO =
  "M39.16,19.78c-.91-1.13-2.36-1.34-3.4-.25-2.04,2.14-.41,7.41,2.56,6.13,2.01-.86,2.08-4.33.84-5.88ZM24.29,19.34c-3.41.19-3.28,6.85.34,6.84,3.64-.01,3.47-7.06-.34-6.84ZM38.39,31.33c-.56,0-.64.26-.76.69-1.87,6.74-10.6,6.12-13.47.29-.18-.37-.33-.72-.85-.56-.7.21-.08,1.29.12,1.71,2.61,5.47,10.48,7.35,14.09,1.91.54-.81,1.24-2.46,1.28-3.43,0-.23-.15-.6-.41-.6Z";

// Proporcao do desenho original: 60.91 x 51.82.
const PROPORCAO = 51.82 / 60.91;

// Largura a partir da qual o rosto aparece.
const LARGURA_COM_ROSTO = 26;

export default function Estrelinhas({ tamanho = 16 }) {
  const comRosto = tamanho >= LARGURA_COM_ROSTO;

  return (
    <span className="estrelinhas" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <svg
          key={i}
          className="estrelinhas__estrela"
          width={tamanho}
          height={Math.round(tamanho * PROPORCAO)}
          viewBox="0 0 60.91 51.82"
        >
          <path d={comRosto ? SILHUETA + ROSTO : SILHUETA} />
        </svg>
      ))}
    </span>
  );
}
