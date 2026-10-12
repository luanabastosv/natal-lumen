/** Uma linha de barra empilhada: rotulo a esquerda, barra no meio, numero a
 * direita.
 *
 * A barra tem DUAS leituras ao mesmo tempo, e as duas importam:
 *
 *   - o COMPRIMENTO total diz o tamanho daquela linha contra a maior de
 *     todas (quantas criancas tem aquele dia, aquela idade);
 *   - a DIVISAO interna diz como aquele total se reparte.
 *
 * Por isso a largura sai de `max`, e nao de 100%: com todas as barras cheias,
 * um dia com 300 criancas e um com 12 desenhariam a mesma coisa.
 *
 * Entre as partes vai uma fresta de 2px na cor da superficie — sem ela, dois
 * tons vizinhos encostam e a divisa some. E cada parte leva o nome escrito na
 * legenda da secao: cor nunca e o unico sinal.
 *
 * Cada parte pode levar o proprio numero DENTRO dela (`p.rotulo`). E o que
 * "por idade" precisa: e pelos numeros de meninos e de meninas que se decide
 * quantos presentes de cada tipo comprar, e escrever ao lado empurrava a
 * barra para um canto.
 *
 * Escrever dentro cobra o contraste do texto contra cada tom, e foi isso que
 * escolheu as cores: navy-600 com numero BRANCO (9,2:1) e navy-300 com numero
 * NAVY-900 (7,1:1). Os dois tons ficam a 4,3:1 um do outro, que e separacao de
 * sobra — bem mais do que o par anterior dava, e agora com o numero legivel
 * nos dois. Texto claro em cima de um tom medio era o que nao fechava.
 *
 * Parte com numero nunca fica mais estreita que o proprio numero: a idade com
 * 3 meninas desenhava uma lasca de poucos pixels e o "3" sumia. Cada parte
 * rotulada tem largura minima do tamanho dos digitos dela, e a barra inteira,
 * a soma disso — a proporcao entre as linhas so cede onde o numero nao caberia.
 */

export default function BarraDupla({ rotulo, partes, total, max, valorTexto, aria }) {
  const escala = max > 0 ? total / max : 0;
  // Com numero dentro, a barra precisa de altura para o texto caber.
  const rotulada = partes.some((p) => p.rotulo != null);
  const visiveis = partes.filter((p) => p.valor > 0);

  // O minimo de uma parte rotulada: os digitos dela mais o respiro dos lados.
  const minimoDe = (p) => `calc(${String(p.rotulo).length}ch + 10px)`;
  const comNumero = visiveis.filter((p) => p.rotulo != null);
  const minimoDaBarra = comNumero.length
    ? `calc(${comNumero.reduce((s, p) => s + String(p.rotulo).length, 0)}ch + ${
        comNumero.length * 10 + (visiveis.length - 1) * 2
      }px)`
    : undefined;

  return (
    <div className={`barra-dupla ${rotulada ? "barra-dupla--rotulada" : ""}`.trim()}>
      <span className="barra-dupla__rotulo">{rotulo}</span>
      <div className="barra-dupla__pista">
        <div
          className="barra-dupla__barra"
          style={{
            width: `${Math.max(escala * 100, total > 0 ? 3 : 0)}%`,
            minWidth: minimoDaBarra,
          }}
          role="img"
          aria-label={aria}
        >
          {visiveis.map((p) => (
            <div
              key={p.nome}
              className={`barra-dupla__parte barra-dupla__parte--${p.tom}`}
              style={{
                flexGrow: p.valor,
                flexBasis: 0,
                minWidth: p.rotulo != null ? minimoDe(p) : undefined,
              }}
            >
              {p.rotulo != null && (
                <span className="barra-dupla__numero">{p.rotulo}</span>
              )}
            </div>
          ))}
        </div>
      </div>
      <span className="barra-dupla__valor">{valorTexto}</span>
    </div>
  );
}
