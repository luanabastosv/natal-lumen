"""Limpa a arte do Canva e gera base, rótulos e máscaras (rodar uma vez, ver README.md)."""
import numpy as np
from PIL import Image, ImageFilter

ref = Image.open("ref.png").convert("RGB")
a = np.array(ref).astype(np.float32)
out = a.copy()


def patch(dst_box, dy, feather=40):
    """Copia a região deslocada dy linhas (fonte = destino + dy), com borda suavizada."""
    x0, y0, x1, y1 = dst_box
    src = a[y0 + dy:y1 + dy, x0:x1]
    h, w = y1 - y0, x1 - x0
    m = np.ones((h, w), np.float32)
    for i in range(feather):
        f = (i + 1) / (feather + 1)
        m[i, :] = np.minimum(m[i, :], f); m[-1 - i, :] = np.minimum(m[-1 - i, :], f)
        m[:, i] = np.minimum(m[:, i], f); m[:, -1 - i] = np.minimum(m[:, -1 - i], f)
    m = m[..., None]
    out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - m) + src * m


# 1) recortes brancos (rótulos) com alfa, antes de apagar
def white_cut(box, name):
    x0, y0, x1, y1 = box
    reg = a[y0:y1, x0:x1]
    alpha = np.clip((reg[..., 0] - 50) / (240 - 50), 0, 1)
    rgba = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    Image.fromarray(rgba).save(name)


white_cut((2950, 3400, 4110, 3660), "assets/rotulo_cesta.png")   # topo-esq em (2950,3400)
white_cut((470, 4450, 1630, 4710), "assets/rotulo_festa.png")    # topo-esq em (470,4450)

# 2) fundo azul: apagar números/rótulos/traço fora da barra
patch((380, 4140, 1835, 4780), -1500, feather=60)      # lado esquerdo (festa)
patch((2768, 3120, 4300, 3740), -1150, feather=60)     # lado direito (cesta)

# 3) dentro da barra: reconstruir com faixa de outra altura que tem tracinho no mesmo lugar
patch((1560, 4268, 2283, 4370), -168, feather=14)      # marcador festa (tracinho 4326 <- 4158)
patch((2299, 3210, 2920, 3312), -162, feather=14)      # marcador cesta (tracinho 3242 <- 3080)

Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save("assets/base.png")
print("ok")

# 4) máscaras das duas faixas do termômetro: flood fill no papel claro, a
#    partir de um ponto dentro de cada faixa (as linhas azul-marinho fecham a área)
from scipy import ndimage  # noqa: E402

base = np.array(Image.open("assets/base.png").convert("RGB")).astype(int)
claro = base.sum(2) > 560
rotulos, _ = ndimage.label(claro)
for nome, (x, y) in {"festa": (2150, 4000), "cesta": (2430, 4000)}.items():
    m = rotulos == rotulos[y, x]
    Image.fromarray((m * 255).astype(np.uint8)).save(f"assets/faixa_{nome}.png")
print("mascaras ok")
