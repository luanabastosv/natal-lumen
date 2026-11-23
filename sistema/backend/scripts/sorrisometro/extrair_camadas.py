"""Separa os elementos da arte do Canva do fundo azul (rodar uma vez).
Saída em assets2/, na escala S=1.0 (resolucao cheia) da arte original (4563 px de largura)."""
import json
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

S = 1.0
BG = np.array([43, 43, 182], np.float32)

a = np.array(Image.open("assets/base.png").convert("RGB")).astype(np.float32)
H, W, _ = a.shape
dist = np.sqrt(((a - BG) ** 2).sum(2))

hard = dist > 75
lab, n = ndimage.label(hard)
tam = ndimage.sum(np.ones_like(dist), lab, index=np.arange(1, n + 1))
manter = np.zeros(n + 1, bool)
manter[1:] = tam > 600
hard = manter[lab]
cheio = ndimage.binary_fill_holes(hard)
zona = np.zeros_like(hard)
zona[300:1600, 1300:4000] = True       # papel do título e "1500" (letras azuis)
zona[1660:, :] = True                  # barra e Estrela
hard = np.where(zona, cheio, hard)

# alfa suave na borda + "descontaminação" do azul de fundo
borda = ndimage.binary_dilation(hard, iterations=3) & ~ndimage.binary_erosion(hard, iterations=3)
alfa = hard.astype(np.float32)
soft = np.clip((dist - 25) / 110, 0, 1)
alfa[borda] = soft[borda]
# recua a borda ~2px para não sobrar fio azul
alfa = np.array(Image.fromarray((alfa * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(0.8))).astype(np.float32) / 255
al = np.maximum(alfa, 1e-3)[..., None]
cor = np.clip((a - (1 - al) * BG) / al, 0, 255)

rgba = np.dstack([cor, alfa * 255]).astype(np.uint8)
img = Image.fromarray(rgba, "RGBA")

grupos = {
    "titulo": (0, 0, W, 1660),
    "barra": (1700, 1660, 2900, 6050),
    "estrela": (2860, 4820, 4500, 6300),
}
meta = {}
for nome, (x0, y0, x1, y1) in grupos.items():
    sub = np.array(img.crop((x0, y0, x1, y1)))
    ys, xs = np.where(sub[..., 3] > 8)
    bx0, by0, bx1, by1 = x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1
    c = img.crop((bx0, by0, bx1, by1))
    c = c.resize((round(c.width * S), round(c.height * S)), Image.LANCZOS)
    c.save(f"assets2/{nome}.png")
    meta[nome] = [int(bx0), int(by0), int(bx1), int(by1)]

# máscaras das faixas recortadas no mesmo enquadramento da barra
bx0, by0, bx1, by1 = meta["barra"]
for f in ("festa", "cesta"):
    m = Image.open(f"assets/faixa_{f}.png").crop((bx0, by0, bx1, by1))
    m.resize((round(m.width * S), round(m.height * S)), Image.LANCZOS).save(f"assets2/faixa_{f}.png")

# rótulos: só alfa (recolorível)
for f, pos in (("cesta", (2950, 3400)), ("festa", (470, 4450))):
    r = Image.open(f"assets/rotulo_{f}.png")
    al = np.array(r.getchannel("A")).astype(np.float32) / 255
    forte = al > 0.45
    lb, nn = ndimage.label(ndimage.binary_dilation(forte, iterations=2))
    tam = ndimage.sum(forte, lb, index=np.arange(1, nn + 1))
    ok = np.zeros(nn + 1, bool); ok[1:] = tam > 150
    al = al * ok[lb] * (al > 0.2)
    r = Image.fromarray(np.dstack([np.full(al.shape + (3,), 255, np.uint8), (al * 255).astype(np.uint8)]), "RGBA")
    r.resize((round(r.width * S), round(r.height * S)), Image.LANCZOS).getchannel("A").save(f"assets2/rotulo_{f}.png")

# textura azul limpa (para fundo)
tile = Image.open("assets/base.png").crop((0, 1700, 1700, 4000))
tile.resize((round(tile.width * S), round(tile.height * S)), Image.LANCZOS).save("assets2/textura_azul.png")

meta["S"] = S
json.dump(meta, open("assets2/meta.json", "w"), indent=1)
print(meta)
