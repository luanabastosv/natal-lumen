"""Digitalizacao do cartao (OpenCV) e leitura do nome (EasyOCR)."""

import io
import re

import cv2
import numpy as np
from PIL import Image, ImageOps

AVISO_SEM_BORDAS = "bordas nao detectadas"

# Um contorno so e aceito como sendo o cartao se ocupar ao menos esta fatia da foto.
AREA_MINIMA_DO_CARTAO = 0.20

# O leitor do EasyOCR e pesado (carrega os modelos do disco), por isso vive
# num modulo global e e criado uma unica vez, na inicializacao do servidor.
_leitor = None


def iniciar_leitor():
    """Carrega o EasyOCR em portugues. Chamado uma vez, ao subir o servidor."""
    global _leitor
    if _leitor is None:
        import easyocr

        _leitor = easyocr.Reader(["pt"], gpu=False)
    return _leitor


def obter_leitor():
    """Devolve o leitor ja carregado (carrega na hora se ainda nao existir)."""
    return _leitor if _leitor is not None else iniciar_leitor()


# ---------------------------------------------------------------- imagem

def carregar_imagem(conteudo: bytes) -> np.ndarray:
    """Le os bytes enviados e devolve a imagem em BGR, ja na orientacao correta.

    Fotos de celular guardam a rotacao na tag EXIF em vez de girar os pixels;
    exif_transpose aplica essa rotacao para o cartao nao chegar deitado.
    """
    imagem = Image.open(io.BytesIO(conteudo))
    imagem = ImageOps.exif_transpose(imagem)
    imagem = imagem.convert("RGB")
    return cv2.cvtColor(np.array(imagem), cv2.COLOR_RGB2BGR)


def _ordenar_cantos(pontos: np.ndarray) -> np.ndarray:
    """Ordena 4 pontos como topo-esquerda, topo-direita, baixo-direita, baixo-esquerda."""
    pontos = pontos.reshape(4, 2).astype("float32")
    ordenados = np.zeros((4, 2), dtype="float32")

    # A soma x+y e minima no canto superior esquerdo e maxima no inferior direito.
    soma = pontos.sum(axis=1)
    ordenados[0] = pontos[np.argmin(soma)]
    ordenados[2] = pontos[np.argmax(soma)]

    # A diferenca y-x separa os outros dois cantos.
    diferenca = np.diff(pontos, axis=1).ravel()
    ordenados[1] = pontos[np.argmin(diferenca)]
    ordenados[3] = pontos[np.argmax(diferenca)]

    return ordenados


def _encontrar_cantos(imagem: np.ndarray):
    """Procura o maior contorno de 4 lados. Devolve os cantos ou None."""
    altura, largura = imagem.shape[:2]

    # Trabalhar numa copia reduzida acelera a deteccao; os pontos voltam a escala depois.
    escala = 700 / max(altura, largura) if max(altura, largura) > 700 else 1.0
    reduzida = cv2.resize(imagem, None, fx=escala, fy=escala) if escala < 1.0 else imagem

    cinza = cv2.cvtColor(reduzida, cv2.COLOR_BGR2GRAY)
    desfocada = cv2.GaussianBlur(cinza, (5, 5), 0)
    bordas = cv2.Canny(desfocada, 50, 150)

    # Fecha pequenas falhas nas bordas para o contorno do cartao nao sair partido.
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

    Devolve (imagem_digitalizada, aviso). Se nao achar os 4 cantos, devolve a
    imagem original e o aviso "bordas nao detectadas" - nunca levanta erro.
    """
    cantos = _encontrar_cantos(imagem)
    if cantos is None:
        return imagem, AVISO_SEM_BORDAS

    (topo_esq, topo_dir, baixo_dir, baixo_esq) = cantos

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


# ---------------------------------------------------------------- OCR

def ler_textos(imagem: np.ndarray) -> list[dict]:
    """Roda o OCR e devolve os textos com confianca e altura da caixa."""
    resultados = obter_leitor().readtext(imagem)

    textos = []
    for caixa, texto, confianca in resultados:
        ys = [ponto[1] for ponto in caixa]
        xs = [ponto[0] for ponto in caixa]
        textos.append(
            {
                "texto": texto.strip(),
                "confianca": round(float(confianca), 3),
                "altura": round(float(max(ys) - min(ys)), 1),
                # topo e esquerda servem para juntar as caixas da mesma linha e
                # para achar o texto que vem logo depois de "Nome:".
                "topo": round(float(min(ys)), 1),
                "esquerda": round(float(min(xs)), 1),
            }
        )

    return textos


# --- Heuristica do nome sugerido -------------------------------------------
# Isolada de proposito: ajuste os numeros abaixo conforme os cartoes reais.

CONFIANCA_MINIMA = 0.30
TAMANHO_MINIMO = 3
ROTULO_NOME = re.compile(r"\bnomes?\b\s*:?\s*", re.IGNORECASE)


# Duas caixas estao na mesma linha se os topos diferirem menos do que esta
# fracao da altura da caixa. Aumente se nomes continuarem a sair partidos.
TOLERANCIA_MESMA_LINHA = 0.6


def _juntar_mesma_linha(textos: list[dict]) -> list[dict]:
    """Junta as caixas que estao na mesma linha num unico texto.

    O EasyOCR costuma partir "BRUNO LIMA" em duas caixas; sem isto a
    heuristica escolheria apenas "BRUNO".
    """
    linhas: list[list[dict]] = []

    for item in sorted(textos, key=lambda t: (t["topo"], t["esquerda"])):
        for linha in linhas:
            referencia = linha[0]
            limite = TOLERANCIA_MESMA_LINHA * max(referencia["altura"], item["altura"], 1)
            if abs(item["topo"] - referencia["topo"]) <= limite:
                linha.append(item)
                break
        else:
            linhas.append([item])

    juntados = []
    for linha in linhas:
        linha.sort(key=lambda t: t["esquerda"])
        juntados.append(
            {
                "texto": " ".join(t["texto"] for t in linha).strip(),
                "confianca": min(t["confianca"] for t in linha),
                "altura": max(t["altura"] for t in linha),
                "topo": min(t["topo"] for t in linha),
                "esquerda": min(t["esquerda"] for t in linha),
            }
        )

    return juntados


def _parece_nome(texto: str) -> bool:
    """Descarta textos que sao so numeros, datas ou simbolos."""
    letras = sum(1 for c in texto if c.isalpha())
    return letras >= TAMANHO_MINIMO and letras >= len(texto.replace(" ", "")) / 2


def escolher_nome_sugerido(textos: list[dict]) -> str:
    """Escolhe qual dos textos detectados e provavelmente o nome da pessoa.

    Regras, por ordem:
      1. Se o cartao tiver "Nome:", usar o que vem depois do rotulo - na mesma
         caixa, ou na caixa detectada logo abaixo.
      2. Senao, o texto com a maior altura de caixa (nomes sao escritos grandes).
    Textos curtos ou com confianca baixa sao descartados antes.
    """
    linhas = _juntar_mesma_linha(textos)

    candidatos = [
        t
        for t in linhas
        if t["confianca"] >= CONFIANCA_MINIMA
        and len(t["texto"]) >= TAMANHO_MINIMO
        and _parece_nome(t["texto"])
    ]

    # 1. Rotulo "Nome:" em qualquer uma das linhas (inclusive as descartadas acima).
    for indice, item in enumerate(linhas):
        if not ROTULO_NOME.search(item["texto"]):
            continue

        depois_do_rotulo = ROTULO_NOME.sub("", item["texto"], count=1).strip()
        if len(depois_do_rotulo) >= TAMANHO_MINIMO:
            return depois_do_rotulo

        # Rotulo sozinho na caixa: o nome esta na caixa seguinte, abaixo ou ao lado.
        seguintes = sorted(
            (t for i, t in enumerate(linhas) if i != indice and _parece_nome(t["texto"])),
            key=lambda t: t["topo"],
        )
        for seguinte in seguintes:
            if seguinte["topo"] >= item["topo"]:
                return seguinte["texto"]

    # 2. Maior altura de caixa.
    if candidatos:
        return max(candidatos, key=lambda t: t["altura"])["texto"]

    return ""
