"""Sorrisometro: a arte com o progresso dos apadrinhamentos de cesta e de festa.

Gera a peca para o Instagram em dois formatos (feed 1080x1350 e stories
1080x1920) e dois fundos (azul e amarelo). E a Estrelinha quem chama
(ferramenta `gerar_sorrisometro`, routers/estrelinha.py), com os numeros ao vivo.

A arte NAO e desenhada do zero aqui. Os elementos (titulo com "1500", termometro
vazio, Estrela, rotulos) foram recortados da arte que o design fechou no Canva,
por scripts/sorrisometro/, e ficam em app/recursos/sorrisometro/. Este modulo so:
  - enche cada faixa do termometro na altura certa (festa = amarelo, a
    esquerda; cesta = listras, a direita), no estilo que o Firefly propos;
  - desenha o traco do meio do termometro ate o numero, o numero e o rotulo;
  - monta o layout de cada formato sobre o fundo.

Coordenadas "da arte" sao as da arte original do Canva (4563 x 6454 px).
"""

import json
import math
import os
import re
import secrets
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.config import config

AQUI = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(AQUI, "..", "recursos", "sorrisometro")

AMARELO = np.array([230, 177, 68], np.float32)
AMARELO_BORDA = np.array([214, 146, 22], np.float32)
AZUL_LISTRA = np.array([50, 52, 165], np.float32)
AMARELO_CLARO = np.array([245, 193, 83], np.float32)
AMARELO_ESCURO = np.array([241, 181, 44], np.float32)
COR_TEXTO = {"azul": (255, 255, 255), "amarelo": (40, 40, 172)}

# Coordenadas da arte original do Canva (4563 x 6454) usadas como referência.
NUM_ALTURA = 171
MEIO_X = 2292          # linha do meio do termômetro
G_X0, G_Y0, G_X1, G_Y1 = 0, 1650, 4563, 6400   # área do grupo "barra + marcadores"

# Layouts em pixels finais (largura 1080). k = escala ref -> final.
LAYOUTS = {
    # título: k=540/2290 para o "1500" (centro em x=2290 na arte) ficar alinhado com o termômetro
    "feed": dict(tam=(1080, 1350),
                 titulo=dict(k=0.2358, x=0, y=10),
                 estrela=dict(k=0.21, x=745, y=1010),
                 barra=dict(k=0.2, topo=395, cx=540),
                 limite=1255, texto=1.25),
    "stories": dict(tam=(1080, 1920),
                    titulo=dict(k=0.2358, x=0, y=150),
                    estrela=dict(k=0.30, x=640, y=1500),
                    barra=dict(k=0.2412, topo=560, cx=540),
                    limite=1600, texto=1.25),
}


def ruido1d(n, escala, amp, seed):
    rng = np.random.default_rng(seed)
    x = np.arange(n, dtype=np.float32)
    out = np.zeros(n, np.float32)
    for k in range(4):
        out += math.pow(0.55, k) * np.sin(2 * math.pi * (k + 1) / escala * x + rng.uniform(0, 6.28))
    return out / 1.9 * amp


# ---------- preenchimento da barra (no espaço S da barra) ----------

def mascara(path):
    m = Image.open(path).convert("L").point(lambda v: 255 if v > 127 else 0)
    m = m.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(0.8))
    return np.array(m).astype(np.float32) / 255.0


def nivel(m, contagem, total):
    ys = np.where(m.max(1) > 0.5)[0]
    y0, y1 = ys.min(), ys.max()
    return y1 - (y1 - y0) * max(0.0, min(1.0, contagem / total))


def textura(rgb):
    lum = rgb.mean(2)
    return np.clip(lum / max(lum.mean(), 1), 0.85, 1.08)[..., None]


def preencher_amarelo(rgb, m, y_top, S):
    H, W, _ = rgb.shape
    xs = np.where(m.max(0) > 0.01)[0]
    x0, x1 = xs.min(), xs.max() + 1
    cols = np.full(W, y_top, np.float32)
    cols[x0:x1] += ruido1d(x1 - x0, 110 * S, 9 * S, 7)
    yy = np.arange(H, dtype=np.float32)[:, None]
    dentro = np.clip(yy - cols[None, :] + 0.5, 0, 1)
    e = 7 * S
    borda = np.clip(1 - np.abs(yy - cols[None, :] - e) / e, 0, 1)[..., None]
    cor = AMARELO[None, None] * textura(rgb)
    cor = cor * (1 - borda * 0.75) + AMARELO_BORDA * borda * 0.75
    a = (m * dentro)[..., None]
    rgb[:] = rgb * (1 - a) + cor * a


def preencher_listras(rgb, m, y_top, S):
    H, W, _ = rgb.shape
    xs = np.where(m.max(0) > 0.01)[0]
    x0, x1 = xs.min(), xs.max() + 1
    periodo = (x1 - x0) * 0.50
    subida = math.tan(math.radians(36))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    trem = ruido1d(H, 260 * S, 0.035, 11)[:, None] + ruido1d(W, 90 * S, 0.02, 12)[None, :]
    fase = ((yy + (xx - x0) * subida) / periodo + trem) % 1.0
    aa = 1.0 / periodo
    azul = np.clip((0.54 - fase) / aa, 0, 1) * np.clip(fase / aa + 0.5, 0, 1)
    onda = np.zeros(W, np.float32)
    onda[x0:x1] = ruido1d(x1 - x0, 140 * S, 4 * S, 13)
    topo = y_top + onda[None, :]
    dentro = np.clip(yy - topo + 0.5, 0, 1)
    tampa = np.clip(topo + 16 * S - yy + 0.5, 0, 1) * dentro
    azul = np.maximum(azul, tampa)
    cor = AZUL_LISTRA[None, None] * textura(rgb)
    a = (m * dentro * azul)[..., None]
    rgb[:] = rgb * (1 - a) + cor * a


# ---------- grupo: barra + marcadores + números (espaço S) ----------

def grupo(cesta, festa, total, cor_txt, limite_ref, limite_cesta_ref, meta, tz=1.0):
    S = meta["S"]
    sx = lambda v: (v - G_X0) * S
    sy = lambda v: (v - G_Y0) * S
    G = Image.new("RGBA", (round((G_X1 - G_X0) * S), round((G_Y1 - G_Y0) * S)), (0, 0, 0, 0))

    barra = Image.open(f"{ASSETS}/barra.png").convert("RGBA")
    bx0, by0 = meta["barra"][0], meta["barra"][1]
    arr = np.array(barra).astype(np.float32)
    rgb = arr[..., :3].copy()
    mf, mc = mascara(f"{ASSETS}/faixa_festa.png"), mascara(f"{ASSETS}/faixa_cesta.png")
    yf, yc_ = nivel(mf, festa, total), nivel(mc, cesta, total)
    if festa > 0:
        preencher_amarelo(rgb, mf, yf, S)
    if cesta > 0:
        preencher_listras(rgb, mc, yc_, S)
    arr[..., :3] = rgb
    G.alpha_composite(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)), (round(sx(bx0)), round(sy(by0))))

    # níveis em coordenadas da arte original
    y_festa = by0 + yf / S
    y_cesta = by0 + yc_ / S

    # números: tamanho para algarismos com NUM_ALTURA px (na arte original)
    d = ImageDraw.Draw(G)
    t = ImageFont.truetype(f"{ASSETS}/GochiHand-Regular.ttf", 200)
    bb = d.textbbox((0, 0), "0123456789", font=t)
    fonte = ImageFont.truetype(f"{ASSETS}/GochiHand-Regular.ttf", round(200 * NUM_ALTURA * tz * S / (bb[3] - bb[1])))
    alt = d.textbbox((0, 0), "0123456789", font=fonte)
    fmt = lambda n: f"{n:,}".replace(",", ".")

    def linha(x0, x1, y, esp=42):
        s = 4
        esp_s = esp * S
        pad = esp_s
        w, h = (sx(x1) - sx(x0) + 2 * pad), 2 * pad
        lay = Image.new("L", (round(w * s), round(h * s)), 0)
        dd = ImageDraw.Draw(lay)
        r = esp_s * s / 2
        ya = pad * s
        dd.rectangle([pad * s, ya - r, (pad + sx(x1) - sx(x0)) * s, ya + r], fill=255)
        for cx in (pad * s, (pad + sx(x1) - sx(x0)) * s):
            dd.ellipse([cx - r, ya - r, cx + r, ya + r], fill=255)
        lay = lay.resize((round(w), round(h)), Image.LANCZOS)
        G.paste(cor_txt + (255,), (round(sx(x0) - pad), round(sy(y) - pad)), lay)

    def numero(txt, y_centro, x, alinhar):
        tb = d.textbbox((0, 0), txt, font=fonte)
        h = alt[3] - alt[1]
        topo = sy(y_centro) - h / 2
        px = sx(x) - tb[0] if alinhar == "esq" else sx(x) - (tb[2] - tb[0]) - tb[0]
        d.text((px, topo - alt[1]), txt, font=fonte, fill=cor_txt)
        return G_Y0 + topo / S, G_Y0 + (topo + h) / S   # em coords da arte

    def rotulo(nome, x, y_ref, dir_=None):
        a = Image.open(f"{ASSETS}/rotulo_{nome}.png")
        if tz != 1.0:
            a = a.resize((round(a.width * tz), round(a.height * tz)), Image.LANCZOS)
        if dir_ is not None:                     # alinhado à direita em dir_
            x = dir_ - a.width / S
        lay = Image.new("RGBA", a.size, cor_txt + (0,))
        lay.putalpha(a)
        G.alpha_composite(lay, (round(sx(x)), round(sy(y_ref))))

    ROT_H = 243 * tz  # altura útil do rótulo (arte original)
    NH = NUM_ALTURA * tz

    # FESTA (esquerda)
    linha(1708, MEIO_X, y_festa)
    yn, yr = y_festa - 5, y_festa + 132 * tz
    if yr + ROT_H + 20 > limite_ref:          # não cabe embaixo: bloco sobe para cima do traço
        yr = y_festa - 60 - ROT_H
        yn = yr - 30 * tz - NH / 2
    numero(fmt(festa), yn, 1594, "dir")
    rotulo("festa", 470, yr, dir_=1612)

    # CESTA (direita): número em cima, rótulo embaixo
    linha(MEIO_X, 2840, y_cesta)
    yn, yr = y_cesta + 4, y_cesta + 140 * tz
    if yr + ROT_H + 20 > limite_cesta_ref:   # esbarraria na Estrela ou no rodapé
        yr = y_cesta - 60 - ROT_H
        yn = yr - 30 * tz - NH / 2
    numero(fmt(cesta), yn, 2991, "esq")
    rotulo("cesta", 2950, yr)
    return G


# ---------- fundos ----------

def fundo_azul(W, H, escala):
    tile = Image.open(f"{ASSETS}/textura_azul.png").convert("RGB")
    tile = tile.resize((round(tile.width * escala), round(tile.height * escala)), Image.LANCZOS)
    tw, th = tile.size
    big = Image.new("RGB", (tw * 2, th * 2))
    big.paste(tile, (0, 0)); big.paste(tile.transpose(Image.FLIP_LEFT_RIGHT), (tw, 0))
    big.paste(tile.transpose(Image.FLIP_TOP_BOTTOM), (0, th)); big.paste(tile.transpose(Image.ROTATE_180), (tw, th))
    out = Image.new("RGB", (W, H))
    for y in range(0, H, th * 2):
        for x in range(0, W, tw * 2):
            out.paste(big, (x, y))
    return out


def fundo_amarelo(W, H, u):
    """Amarelo liso (tom da Estrela), só com um grão bem leve de papel."""
    grao = np.array(fundo_azul(W, H, u / 2).convert("L")).astype(np.float32)
    grao = (grao - grao.mean()) / max(grao.std(), 1)
    img = np.zeros((H, W, 3), np.float32) + AMARELO_ESCURO
    img = img * (1 + 0.012 * grao[..., None])
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


# ---------- montagem ----------

FORMATOS = tuple(LAYOUTS)
FUNDOS = ("azul", "amarelo")


def desenhar(cesta: int, festa: int, total: int, formato: str, fundo: str, escala: int = 1) -> Image.Image:
    """A arte pronta. escala=1 sai em 1080 de largura; escala=2, em 2160 (alta)."""
    if formato not in LAYOUTS or fundo not in FUNDOS:
        raise ValueError(f"Formato ({', '.join(FORMATOS)}) ou fundo ({', '.join(FUNDOS)}) invalido.")
    if total <= 0:
        raise ValueError("O total precisa ser maior que zero.")
    meta = json.load(open(f"{ASSETS}/meta.json"))
    S = meta["S"]
    L = LAYOUTS[formato]
    R = 2  # desenha em 2x e reduz no fim
    W, H = L["tam"][0] * R, L["tam"][1] * R

    canvas = (fundo_azul(W, H, 0.2367 * R / S) if fundo == "azul" else fundo_amarelo(W, H, R)).convert("RGBA")

    def colar(img, k, x, y):
        f = k * R / S
        im = img.resize((round(img.width * f), round(img.height * f)), Image.LANCZOS)
        canvas.alpha_composite(im, (round(x * R), round(y * R)))

    t = L["titulo"]
    colar(Image.open(f"{ASSETS}/titulo.png").convert("RGBA"), t["k"], t["x"], t["y"])

    b = L["barra"]
    k = b["k"]
    ox = b["cx"] - 2293 * k
    oy = b["topo"] - meta["barra"][1] * k
    limite_ref = (L["limite"] - oy) / k
    e = L["estrela"]
    topo_estrela_ref = (e["y"] - oy) / k
    G = grupo(cesta, festa, total, COR_TEXTO[fundo], limite_ref,
              min(limite_ref, topo_estrela_ref - 60), meta, L.get("texto", 1.0))
    colar(G, k, ox + G_X0 * k, oy + G_Y0 * k)

    colar(Image.open(f"{ASSETS}/estrela.png").convert("RGBA"), e["k"], e["x"], e["y"])
    final = canvas.convert("RGB")
    if escala == R:
        return final
    return final.resize((L["tam"][0] * escala, L["tam"][1] * escala), Image.LANCZOS)


# ---------- arquivos publicados ----------
#
# Excecao consciente a regra de app/servicos/arquivos.py ("nada em ARQUIVOS_DIR
# e servido publicamente"): a pasta sorrisometro/ sai por uma rota sem login
# (GET /estrelinha/sorrisometro/{nome}), porque o link vai para o Instagram, o
# Metricool e quem mais a coordenacao quiser. Pode porque a arte so tem duas
# contagens agregadas, nada de crianca nem de padrinho; o nome tem 96 bits
# aleatorios (ninguem adivinha) e a rota so aceita nomes no formato abaixo.

DIAS_GUARDADOS = 60
NOME_VALIDO = re.compile(r"^\d{4}-\d{2}-\d{2}-(feed|stories)-(azul|amarelo)-[A-Za-z0-9_-]{16}\.png$")


def pasta():
    p = config.caminho_arquivos / "sorrisometro"
    p.mkdir(parents=True, exist_ok=True)
    return p


def limpar_antigos(dias: int = DIAS_GUARDADOS) -> None:
    limite = time.time() - dias * 86400
    for arq in pasta().glob("*.png"):
        if NOME_VALIDO.match(arq.name) and arq.stat().st_mtime < limite:
            arq.unlink(missing_ok=True)


def salvar(img: Image.Image, formato: str, fundo: str) -> str:
    """Grava a arte (PNG, sem perda) e devolve o nome do arquivo."""
    hoje = datetime.now(ZoneInfo("America/Fortaleza")).strftime("%Y-%m-%d")
    nome = f"{hoje}-{formato}-{fundo}-{secrets.token_urlsafe(12)}.png"
    img.save(pasta() / nome, optimize=True)
    return nome


def caminho_publicado(nome: str):
    """Caminho do arquivo, ou None se o nome nao for de um sorrisometro."""
    if not NOME_VALIDO.match(nome):
        return None
    arq = pasta() / nome
    return arq if arq.is_file() else None
