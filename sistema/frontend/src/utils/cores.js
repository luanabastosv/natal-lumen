/* As cores de bata mais comuns, para escolher sem digitar. Quem nao achar a
   sua escolhe a cor exata no seletor. */
export const CORES_DE_BATA = [
  { nome: "Branco", hex: "#ffffff" },
  { nome: "Preto", hex: "#1c1c1c" },
  { nome: "Cinza", hex: "#9e9e9e" },
  { nome: "Vermelho", hex: "#d32f2f" },
  { nome: "Vinho", hex: "#7b1f2e" },
  { nome: "Rosa", hex: "#f06292" },
  { nome: "Pink", hex: "#e91e8c" },
  { nome: "Lilás", hex: "#b39ddb" },
  { nome: "Roxo", hex: "#6a1b9a" },
  { nome: "Azul-marinho", hex: "#1a237e" },
  { nome: "Azul royal", hex: "#1e63e9" },
  { nome: "Azul-claro", hex: "#64b5f6" },
  { nome: "Turquesa", hex: "#1ec8c8" },
  { nome: "Verde-escuro", hex: "#1b5e20" },
  { nome: "Verde", hex: "#43a047" },
  { nome: "Verde-limão", hex: "#b2d732" },
  { nome: "Amarelo", hex: "#fdd835" },
  { nome: "Laranja", hex: "#fb8c00" },
  { nome: "Marrom", hex: "#6d4c41" },
  { nome: "Bege", hex: "#d7c4a3" },
];

function rgb(hex) {
  const h = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
}

/* sRGB -> CIELAB: a distancia em Lab se aproxima de como o olho separa duas
   cores. Em RGB cru, um vermelho e um vinho parecem distantes e dois cinzas
   parecem perto — ao contrario do que se ve no patio. */
function lab(hex) {
  const lin = rgb(hex).map((c) => (c > 0.04045 ? ((c + 0.055) / 1.055) ** 2.4 : c / 12.92));
  const [r, g, b] = lin;
  const x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047;
  const y = r * 0.2126 + g * 0.7152 + b * 0.0722;
  const z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883;
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  return [116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))];
}

/** Distancia entre duas cores (CIE76). */
export function distancia(hexA, hexB) {
  const [l1, a1, b1] = lab(hexA);
  const [l2, a2, b2] = lab(hexB);
  return Math.hypot(l1 - l2, a1 - a2, b1 - b2);
}

/* Abaixo de 40 duas batas se confundem de longe: vermelho e vinho (39),
   azul royal e azul-marinho (33), amarelo e verde-limao (32). Acima, ja se
   separam: vermelho e laranja (49), verde e verde-limao (42). */
export const LIMITE_PARECIDAS = 40;

/** Se duas batas se confundem num patio cheio.
 *
 *  Alem da distancia, duas cores muito escuras contam como parecidas: preto e
 *  azul-marinho ficam longe na conta (61), mas a sombra de uma tenda iguala as
 *  duas. */
export function parecidas(hexA, hexB) {
  if (!hexA || !hexB) return false;
  if (distancia(hexA, hexB) < LIMITE_PARECIDAS) return true;
  return lab(hexA)[0] < 25 && lab(hexB)[0] < 25;
}

/** O nome da cor da lista, se o hex for um dos dela. */
export function nomeDaCor(hex) {
  return CORES_DE_BATA.find((c) => c.hex === hex?.toLowerCase())?.nome ?? null;
}
