/** A arte de fundo do card de abertura do painel.
 *
 * O painel e a unica tela de momento que a pessoa ve todo dia, e era a mais
 * lisa do sistema. Esta arte existe para que ela nao abra como mais uma
 * planilha: um ceu de estrelinhas com dois brilhos quentes atras do mascote.
 *
 * O que ela usa, e por que:
 *
 *   - O mascote e a arte de verdade (mascote-pulo.png), nao um desenho meu.
 *     Ele entra como <img> ao lado deste SVG, e nao dentro dele: o ceu
 *     precisa escalar com a caixa e o mascote precisa manter o tamanho.
 *   - As estrelinhas sao a ESTRELA DA MARCA, o mesmo path do mascote, em
 *     tamanhos e giros variados. Nao e um sparkle generico de biblioteca: e a
 *     silhueta torta de cinco pontas do logo, que e o que faz o ceu parecer do
 *     Natal Lumen.
 *   - NAO ha brilho nem degrade. Dois blobs em ambar chegaram a existir aqui
 *     e sairam: na tela eles liam como mancha, nao como brilho. Com isso a
 *     regra "sem gradiente" do design system volta a valer sem excecao.
 *
 * A composicao e fixa, nao sorteada em tempo de execucao: as posicoes sairam
 * de uma semente fixa e foram conferidas a olho. Arte que se sorteia a cada
 * carregamento nao pode ser aprovada — ninguem ve duas vezes a mesma.
 *
 * O texto vive a esquerda de x=470 e as estrelinhas nao entram la, para que
 * nada passe por tras da saudacao. Decorativa inteira: aria-hidden.
 */

export default function ArtePainel() {
  return (
    <svg
      className="abertura__arte"
      viewBox="0 0 960 240"
      preserveAspectRatio="xMaxYMid slice"
      aria-hidden="true"
    >
      <defs>
          <path id="abertura-estrela" d="M10.79,49.77c-1.34-1.61-1.35-4.41-1.26-6.44.14-2.86.94-5.13,1.38-7.82.18-1.09.01-1.05-.74-1.72-2.27-2.03-4.44-3.94-6.46-6.24C2.32,25.96-.28,22.83.02,20.62c.58-4.19,4.64-5.6,8.18-6.5,3.04-.77,6.26-1.06,9.4-1.1.24-.04.41-.56.61-.67.31-.16.93-.03,1.25-.22,2.65-3.75,5.37-7.55,8.96-10.48,2.23-1.82,6.23-2.35,8.59-.48,1.82,1.44,4.44,5.87,5.43,8.04.31.67,1.79,4.95,2.01,5.11,1.79.53,3.68.47,5.52.74,2.13.31,4.59,1.22,6.58,2.05,3.43,1.43,4.85,2.97,4.19,6.88-.42,2.51-4.09,5.79-5.99,7.43-1.6,1.38-3.34,2.59-4.96,3.95-.1.26.5,2.04.56,2.52.06.52.02,1.03.08,1.57.13,1.18.58,2.37.72,3.5.34,2.72.03,7.94-3.25,8.67-4.56,1.02-10.21-2.07-13.8-4.67-.69-.5-1.76-1.55-2.47-1.87-.16-.07-.59-.19-.76-.2-.68-.02-2.72,1.67-3.41,2.1-1.64,1.02-4.09,2.06-5.9,2.8-3.23,1.32-8.09,3.21-10.78-.01Z" />
        </defs>
        <use href="#abertura-estrela" fill="var(--navy-300)" opacity="0.41" transform="translate(488 190) rotate(19) scale(0.3448)" />
        <use href="#abertura-estrela" fill="var(--navy-300)" opacity="0.24" transform="translate(715 56) rotate(-29) scale(0.2955)" />
        <use href="#abertura-estrela" fill="var(--navy-300)" opacity="0.38" transform="translate(541 146) rotate(6) scale(0.2463)" />
        <use href="#abertura-estrela" fill="var(--amarelo-500)" opacity="0.37" transform="translate(513 86) rotate(23) scale(0.2955)" />
        <use href="#abertura-estrela" fill="var(--navy-300)" opacity="0.36" transform="translate(726 179) rotate(-16) scale(0.2463)" />
        <use href="#abertura-estrela" fill="var(--amarelo-500)" opacity="0.23" transform="translate(613 181) rotate(-22) scale(0.2955)" />
        <use href="#abertura-estrela" fill="var(--amarelo-500)" opacity="0.32" transform="translate(667 145) rotate(15) scale(0.2134)" />
        <use href="#abertura-estrela" fill="var(--amarelo-500)" opacity="0.43" transform="translate(539 28) rotate(-9) scale(0.2463)" />
        <use href="#abertura-estrela" fill="var(--navy-300)" opacity="0.45" transform="translate(486 133) rotate(25) scale(0.1806)" />
        <use href="#abertura-estrela" fill="var(--navy-300)" opacity="0.2" transform="translate(480 39) rotate(-5) scale(0.3448)" />
        <use href="#abertura-estrela" fill="var(--amarelo-500)" opacity="0.44" transform="translate(662 201) rotate(5) scale(0.1806)" />
        <use href="#abertura-estrela" fill="var(--navy-300)" opacity="0.22" transform="translate(720 122) rotate(-20) scale(0.1806)" />
        <use href="#abertura-estrela" fill="var(--navy-300)" opacity="0.32" transform="translate(557 197) rotate(17) scale(0.1806)" />
    </svg>
  );
}
