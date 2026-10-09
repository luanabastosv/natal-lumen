"""Digitalizacao do cartao: corrige a perspectiva da foto.

O cartao chega como foto de celular, torta e com o fundo da mesa em volta.
Aqui ele vira uma imagem so do cartao, endireitada.

Houve OCR aqui — o EasyOCR lia o nome escrito no cartao para o monitor
conferir. Saiu. Duas razoes: errava (num cartao de teste com "BRUNO" escrito,
leu "INPI"), e a identificacao passou a ser pelo CODIGO no nome do arquivo,
que e exato. Junto com ele sairam 609 MB de disco (torch, torchvision,
easyocr) e 884 MB de RAM por worker — o app inteiro cabe em 152 MB agora.

O que sobrou custa ~1 ms por cartao.
"""

import io
import re

import cv2
import numpy as np
from PIL import Image, ImageOps

AVISO_SEM_BORDAS = "bordas nao detectadas"

# Um contorno so e aceito como o cartao se ocupar ao menos esta fatia da foto.
AREA_MINIMA_DO_CARTAO = 0.20

# A partir de quao "comprida" a imagem ja e o proprio cartao, e nao uma foto
# dele sobre a mesa. O cartao do Natal Lumen e estreito (uns 0,42 de largura
# por altura); foto de celular e 0,75 (4:3) ou 0,56 (16:9). Imagem mais
# estreita que isto chegou escaneada ou ja recortada — e nela o maior
# contorno de quatro lados e o QUADRO BRANCO de dentro do cartao, nao a borda
# dele: "endireitar" cortava a moldura, o nome e o codigo da crianca.
PROPORCAO_DE_CARTAO_PRONTO = 0.52

# ---------------------------------------------------------------- imagem

def carregar_imagem(conteudo: bytes) -> np.ndarray:
    """Le os bytes e devolve a imagem em BGR, ja na orientacao correta.

    Fotos de celular guardam a rotacao na tag EXIF em vez de girar os pixels;
    sem exif_transpose o cartao chega deitado.
    """
    imagem = Image.open(io.BytesIO(conteudo))
    imagem = ImageOps.exif_transpose(imagem)
    return cv2.cvtColor(np.array(imagem.convert("RGB")), cv2.COLOR_RGB2BGR)


def _ordenar_cantos(pontos: np.ndarray) -> np.ndarray:
    """Ordena 4 pontos: topo-esquerda, topo-direita, baixo-direita, baixo-esquerda."""
    pontos = pontos.reshape(4, 2).astype("float32")
    ordenados = np.zeros((4, 2), dtype="float32")

    soma = pontos.sum(axis=1)
    ordenados[0] = pontos[np.argmin(soma)]
    ordenados[2] = pontos[np.argmax(soma)]

    diferenca = np.diff(pontos, axis=1).ravel()
    ordenados[1] = pontos[np.argmin(diferenca)]
    ordenados[3] = pontos[np.argmax(diferenca)]

    return ordenados


def _encontrar_cantos(imagem: np.ndarray):
    """Procura o maior contorno de 4 lados. Devolve os cantos ou None."""
    altura, largura = imagem.shape[:2]

    escala = 700 / max(altura, largura) if max(altura, largura) > 700 else 1.0
    reduzida = cv2.resize(imagem, None, fx=escala, fy=escala) if escala < 1.0 else imagem

    cinza = cv2.cvtColor(reduzida, cv2.COLOR_BGR2GRAY)
    desfocada = cv2.GaussianBlur(cinza, (5, 5), 0)
    bordas = cv2.Canny(desfocada, 50, 150)
    bordas = cv2.dilate(bordas, np.ones((3, 3), np.uint8), iterations=1)

    contornos, _ = cv2.findContours(bordas, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contornos = sorted(contornos, key=cv2.contourArea, reverse=True)[:10]

    area_reduzida = reduzida.shape[0] * reduzida.shape[1]

    for contorno in contornos:
        perimetro = cv2.arcLength(contorno, True)
        aproximado = cv2.approxPolyDP(contorno, 0.02 * perimetro, True)

        if len(aproximado) != 4 or not cv2.isContourConvex(aproximado):
            continue
        if cv2.contourArea(aproximado) < AREA_MINIMA_DO_CARTAO * area_reduzida:
            continue

        return _ordenar_cantos(aproximado) / escala

    return None


def digitalizar(imagem: np.ndarray):
    """Corrige a perspectiva do cartao.

    Devolve (imagem, aviso). Sem os 4 cantos, devolve a foto original com o
    aviso — nunca levanta erro, porque uma foto torta ainda serve.

    Imagem que ja e o cartao (escaneada, ou recortada antes de subir) passa
    intacta: ver PROPORCAO_DE_CARTAO_PRONTO.
    """
    altura, largura = imagem.shape[:2]
    if min(altura, largura) / max(altura, largura) < PROPORCAO_DE_CARTAO_PRONTO:
        return imagem, None

    cantos = _encontrar_cantos(imagem)
    if cantos is None:
        return imagem, AVISO_SEM_BORDAS

    topo_esq, topo_dir, baixo_dir, baixo_esq = cantos

    largura = int(max(np.linalg.norm(baixo_dir - baixo_esq), np.linalg.norm(topo_dir - topo_esq)))
    altura = int(max(np.linalg.norm(topo_dir - baixo_dir), np.linalg.norm(topo_esq - baixo_esq)))

    if largura < 50 or altura < 50:
        return imagem, AVISO_SEM_BORDAS

    destino = np.array(
        [[0, 0], [largura - 1, 0], [largura - 1, altura - 1], [0, altura - 1]],
        dtype="float32",
    )
    matriz = cv2.getPerspectiveTransform(cantos, destino)
    return cv2.warpPerspective(imagem, matriz, (largura, altura)), None
