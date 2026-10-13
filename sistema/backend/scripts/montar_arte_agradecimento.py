"""Prepara a arte do agradecimento a partir do modelo do design, e grava o
template e o layout.json que o sistema usa.

Rodar com (da pasta sistema/backend):

    ./.venv/bin/python -m scripts.montar_arte_agradecimento "<modelo.png>"

O modelo e a arte inteira, feita pelo design, ja com um exemplo preenchido
(nome, codigo, instituicao e dia de uma crianca qualquer). Este script apaga
os quatro valores do exemplo — deixa os rotulos e as estrelinhas —, reduz para
1080 x 1620 e grava as posicoes onde o sistema escreve os dados de verdade.
Trocar a arte e rodar de novo com o modelo novo; se os campos mudarem de
lugar, as coordenadas abaixo mudam junto.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "app" / "recursos" / "agradecimento"

LARGURA, ALTURA = 1080, 1620
AZUL = "#15286a"

# Em pixels da arte ja reduzida para 1080. O papel branco vai de x ~240 a
# ~832; os valores comecam alinhados ao rotulo de cada um.
#   campo: (x do texto, linha de base, faixa a apagar (y de cima, y de baixo))
CAMPOS = {
    "nome": (382, 734, (692, 762)),
    "codigo": (387, 852, (803, 882)),
    "instituicao": (394, 971, (924, 996)),
    "dia": (394, 1090, (1042, 1116)),
}
APAGAR_X = (372, 830)


def montar(modelo: Path) -> None:
    original = Image.open(modelo).convert("RGB")
    escala = original.width / LARGURA

    # Apaga na resolucao do modelo, antes de reduzir: a borda do branco
    # fica limpa, sem o halo que um retangulo pintado depois deixaria.
    desenho = ImageDraw.Draw(original)
    for _, _, (y0, y1) in CAMPOS.values():
        desenho.rectangle(
            [APAGAR_X[0] * escala, y0 * escala, APAGAR_X[1] * escala, y1 * escala],
            fill=(255, 255, 255),
        )

    arte = original.resize((LARGURA, ALTURA), Image.LANCZOS)
    DESTINO.mkdir(parents=True, exist_ok=True)
    arte.save(DESTINO / "template.png", optimize=True)

    largura_max = APAGAR_X[1] - 6
    layout = {
        "campos": {
            nome: {
                "x": x, "y": base, "tamanho": 42, "cor": AZUL, "fonte": "bold",
                # "ls": o y e a linha de base, como no modelo.
                "ancora": "ls", "largura_max": largura_max - x,
                # Instituicao longa fica so com os dois primeiros nomes.
                **({"encurtar": True} if nome == "instituicao" else {}),
                **({"maiusculas": True} if nome == "codigo" else {}),
            }
            for nome, (x, base, _) in CAMPOS.items()
        }
    }
    (DESTINO / "layout.json").write_text(
        json.dumps(layout, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"gravado em {DESTINO}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)
    montar(Path(sys.argv[1]))
