"""Aproxima as letras dos rotulos "apadrinhamentos de cesta/festa" (rodar depois
de extrair_camadas.py). Assim o texto cabe maior sem sair da arte."""
import numpy as np
from PIL import Image
from scipy import ndimage


def apertar(path, alinhar, fator=0.45, limiar=40):
    a = np.array(Image.open(path)).astype(np.uint8)
    prof = (a > 60).sum(1)
    rows = np.where(prof > 0)[0]
    meio = min(range(rows.min() + a.shape[0] // 4, rows.max() - a.shape[0] // 4), key=lambda r: prof[r])
    lab, n = ndimage.label(a > 10)
    centros = ndimage.center_of_mass(np.ones_like(a), lab, range(1, n + 1))
    linhas = []
    for primeira in (True, False):
        ids = [i + 1 for i, (y, _) in enumerate(centros) if (y < meio) == primeira]
        L = np.where(np.isin(lab, ids), a, 0)
        ys = np.where(L.max(1) > 10)[0]
        L = L[ys.min():ys.max() + 1]
        cols = L.max(0) > 25
        xs = np.where(cols)[0]
        L, cols = L[:, xs.min():xs.max() + 1], cols[xs.min():xs.max() + 1]
        manter, i = [], 0
        while i < len(cols):
            if cols[i]:
                manter.append(i); i += 1; continue
            j = i
            while j < len(cols) and not cols[j]:
                j += 1
            vao = j - i
            novo = max(4, round(vao * fator)) if vao < limiar else round(vao * 0.55)
            manter += list(range(i, i + novo)); i = j
        linhas.append((ys.min(), L[:, manter]))
    W = max(x.shape[1] for _, x in linhas)
    out = np.zeros((a.shape[0] + 20, W), np.uint8)
    for y0, x in linhas:
        faixa = out[y0:y0 + x.shape[0]]
        if alinhar == "esq":
            faixa[:, :x.shape[1]] = np.maximum(faixa[:, :x.shape[1]], x)
        else:
            faixa[:, W - x.shape[1]:] = np.maximum(faixa[:, W - x.shape[1]:], x)
    Image.fromarray(out).save(path)


apertar("assets2/rotulo_cesta.png", "esq")
apertar("assets2/rotulo_festa.png", "dir")
