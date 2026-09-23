"""API do sistema de cartoes de monitoria."""

import base64
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import cv2
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

import scanner
from database import BASE_DIR, Cartao, Instituicao, criar_tabelas, get_db
from utils import caminho_disponivel, montar_nome_arquivo

PASTA_TEMP = BASE_DIR / "cartoes_temp"
PASTA_FINAL = BASE_DIR / "cartoes_digitalizados"

ORIGENS_PERMITIDAS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    PASTA_TEMP.mkdir(exist_ok=True)
    PASTA_FINAL.mkdir(exist_ok=True)
    criar_tabelas()
    print("Carregando o EasyOCR (pode demorar na primeira vez)...")
    scanner.iniciar_leitor()
    print("Pronto. API em http://localhost:8000")
    yield


app = FastAPI(title="Cartoes Monitoria", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENS_PERMITIDAS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- schemas

class InstituicaoOut(BaseModel):
    id: int
    nome: str


class TextoDetectado(BaseModel):
    texto: str
    confianca: float
    altura: float


class AnaliseOut(BaseModel):
    id: str
    nome_sugerido: str
    textos: list[TextoDetectado]
    imagem_base64: str
    aviso: str | None = None


class ConfirmacaoIn(BaseModel):
    id: str
    instituicao_id: int
    nome: str


class CartaoOut(BaseModel):
    id: int
    nome: str
    instituicao_id: int
    instituicao: str
    caminho_arquivo: str
    criado_em: datetime


# ---------------------------------------------------------------- rotas

@app.get("/instituicoes", response_model=list[InstituicaoOut])
def listar_instituicoes(db: Session = Depends(get_db)):
    return db.query(Instituicao).order_by(Instituicao.nome).all()


@app.post("/cartoes/analisar", response_model=AnaliseOut)
async def analisar_cartao(
    imagem: UploadFile = File(...),
    instituicao_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Digitaliza o cartao e le o nome, sem gravar nada na base de dados ainda."""
    if not db.get(Instituicao, instituicao_id):
        raise HTTPException(404, "Instituicao nao encontrada.")

    conteudo = await imagem.read()
    if not conteudo:
        raise HTTPException(400, "Arquivo de imagem vazio.")

    try:
        original = scanner.carregar_imagem(conteudo)
    except Exception:
        raise HTTPException(400, "Nao foi possivel ler a imagem enviada.")

    digitalizada, aviso = scanner.digitalizar(original)
    textos = scanner.ler_textos(digitalizada)
    nome_sugerido = scanner.escolher_nome_sugerido(textos)

    # Guarda na pasta temporaria; o arquivo so ganha o nome definitivo na confirmacao.
    id_temporario = uuid.uuid4().hex
    caminho_temp = PASTA_TEMP / f"{id_temporario}.jpg"
    if not cv2.imwrite(str(caminho_temp), digitalizada):
        raise HTTPException(500, "Falha ao guardar a imagem digitalizada.")

    _, buffer = cv2.imencode(".jpg", digitalizada)

    return AnaliseOut(
        id=id_temporario,
        nome_sugerido=nome_sugerido,
        textos=[TextoDetectado(**t) for t in textos],
        imagem_base64=base64.b64encode(buffer.tobytes()).decode(),
        aviso=aviso,
    )


@app.post("/cartoes/confirmar", response_model=CartaoOut)
def confirmar_cartao(dados: ConfirmacaoIn, db: Session = Depends(get_db)):
    """Move a imagem para a pasta final com o nome INSTITUICAO_NOME.jpg e grava o registro."""
    nome = dados.nome.strip()
    if not nome:
        raise HTTPException(400, "O nome nao pode ficar vazio.")

    instituicao = db.get(Instituicao, dados.instituicao_id)
    if not instituicao:
        raise HTTPException(404, "Instituicao nao encontrada.")

    # uuid4().hex e sempre hexadecimal: recusar o resto impede subir na arvore de pastas.
    if not dados.id.isalnum():
        raise HTTPException(400, "Id temporario invalido.")

    caminho_temp = PASTA_TEMP / f"{dados.id}.jpg"
    if not caminho_temp.is_file():
        raise HTTPException(404, "Analise nao encontrada. Envie a foto novamente.")

    destino = caminho_disponivel(PASTA_FINAL, montar_nome_arquivo(instituicao.nome, nome))
    caminho_temp.replace(destino)

    cartao = Cartao(
        nome=nome,
        instituicao_id=instituicao.id,
        caminho_arquivo=str(destino.relative_to(BASE_DIR)),
    )
    db.add(cartao)
    db.commit()
    db.refresh(cartao)

    return _serializar(cartao)


@app.get("/cartoes", response_model=list[CartaoOut])
def listar_cartoes(db: Session = Depends(get_db)):
    cartoes = db.query(Cartao).order_by(Cartao.criado_em.desc()).all()
    return [_serializar(c) for c in cartoes]


def _serializar(cartao: Cartao) -> CartaoOut:
    return CartaoOut(
        id=cartao.id,
        nome=cartao.nome,
        instituicao_id=cartao.instituicao_id,
        instituicao=cartao.instituicao.nome,
        caminho_arquivo=cartao.caminho_arquivo,
        criado_em=cartao.criado_em,
    )
