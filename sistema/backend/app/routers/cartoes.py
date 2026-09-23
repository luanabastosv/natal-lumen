"""Cartoes de agradecimento: digitalizacao, OCR e envio aos padrinhos.

Cada crianca escreve dois cartoes, um para cada padrinho. O destinatario nao
fica gravado no cartao: e encontrado por crianca + tipo -> apadrinhamento ->
padrinho. Assim o cartao pode ser digitalizado antes de haver padrinho.
"""

import base64
import uuid
from datetime import UTC, datetime
from typing import Annotated

import cv2
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import config
from app.database import get_db
from app.models import Apadrinhamento, Cartao, Crianca, Edicao, Padrinho
from app.models.tipos import StatusCartao
from app.schemas.cartoes import (
    AnaliseCartao,
    CartaoOut,
    ConfirmarCartao,
    MarcarEnviados,
    PaginaCartoes,
    TextoDetectado,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos import arquivos, scanner
from app.servicos.upload import ler_limitado
from app.servicos.log import registrar

router = APIRouter(prefix="/cartoes", tags=["cartoes"])

BD = Annotated[Session, Depends(get_db)]
Subir = Annotated[ContextoAcesso, Depends(exige_permissao("subir_cartoes"))]
Enviar = Annotated[ContextoAcesso, Depends(exige_permissao("enviar_cartoes"))]
Ver = Annotated[ContextoAcesso, Depends(exige_permissao("ver_criancas"))]

PASTA_TEMP = config.caminho_arquivos / "cartoes_temp"


def _padrinho_do_cartao(db: Session, cartao: Cartao) -> Padrinho | None:
    """Quem recebe este cartao: crianca + tipo -> apadrinhamento -> padrinho."""
    return db.scalar(
        select(Padrinho)
        .join(Apadrinhamento, Apadrinhamento.padrinho_id == Padrinho.id)
        .where(
            Apadrinhamento.crianca_id == cartao.crianca_id,
            Apadrinhamento.tipo == cartao.tipo,
        )
    )


def _saida(db: Session, cartao: Cartao) -> CartaoOut:
    padrinho = _padrinho_do_cartao(db, cartao)
    return CartaoOut(
        id=cartao.id,
        crianca_id=cartao.crianca_id,
        crianca_nome=cartao.crianca.nome,
        instituicao=cartao.crianca.instituicao.nome,
        tipo=cartao.tipo,
        arquivo=cartao.arquivo,
        texto_ocr=cartao.texto_ocr,
        status=cartao.status,
        criado_em=cartao.criado_em,
        enviado_em=cartao.enviado_em,
        padrinho_id=padrinho.id if padrinho else None,
        padrinho_nome=padrinho.nome if padrinho else None,
        padrinho_whatsapp=padrinho.whatsapp if padrinho else None,
    )


def _filtro(ctx: ContextoAcesso, permissao: str):
    """Cartoes das criancas que o usuario alcanca."""
    return Cartao.crianca_id.in_(select(Crianca.id).where(ctx.filtro_criancas(permissao)))


def _buscar_crianca(db: Session, ctx: ContextoAcesso, crianca_id: int, permissao: str) -> Crianca:
    crianca = db.scalar(
        select(Crianca)
        .where(Crianca.id == crianca_id, ctx.filtro_criancas(permissao))
        .options(
            joinedload(Crianca.instituicao),
            joinedload(Crianca.edicao).joinedload(Edicao.cidade),
        )
    )
    if crianca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")
    return crianca


@router.get("", response_model=PaginaCartoes)
def listar(
    db: BD,
    ctx: Ver,
    crianca_id: int | None = None,
    tipo: str | None = None,
    situacao: str | None = Query(default=None, pattern="^(digitalizado|enviado)$"),
    sem_padrinho: bool = False,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
):
    condicao = _filtro(ctx, "ver_criancas")

    if crianca_id is not None:
        condicao = condicao & (Cartao.crianca_id == crianca_id)
    if tipo is not None:
        condicao = condicao & (Cartao.tipo == tipo)
    if situacao is not None:
        condicao = condicao & (Cartao.status == situacao)

    if sem_padrinho:
        # Cartao ja digitalizado que ainda nao tem para quem ir.
        tem_padrinho = select(Apadrinhamento.id).where(
            Apadrinhamento.crianca_id == Cartao.crianca_id,
            Apadrinhamento.tipo == Cartao.tipo,
        )
        condicao = condicao & ~tem_padrinho.exists()

    total = db.scalar(select(func.count()).select_from(Cartao).where(condicao)) or 0

    itens = db.scalars(
        select(Cartao)
        .where(condicao)
        .options(joinedload(Cartao.crianca).joinedload(Crianca.instituicao))
        .order_by(Cartao.criado_em.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()

    return PaginaCartoes(
        total=total, pagina=pagina, por_pagina=por_pagina,
        itens=[_saida(db, c) for c in itens],
    )


@router.post("/analisar", response_model=AnaliseCartao)
async def analisar(
    db: BD,
    ctx: Subir,
    imagem: UploadFile = File(...),
    codigo: str = Form(..., description="Codigo da crianca escrito no cartao"),
    edicao_id: int = Form(...),
):
    """Digitaliza o cartao e le o nome. Nao grava nada na base ainda."""
    crianca = db.scalar(
        select(Crianca)
        .where(
            func.lower(Crianca.codigo) == codigo.strip().lower(),
            Crianca.edicao_id == edicao_id,
            ctx.filtro_criancas("subir_cartoes"),
        )
        .options(
            joinedload(Crianca.instituicao),
            joinedload(Crianca.edicao).joinedload(Edicao.cidade),
        )
    )
    if crianca is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Nenhuma crianca com este codigo entre as que voce alcanca.",
        )

    conteudo = await ler_limitado(imagem)

    try:
        original = scanner.carregar_imagem(conteudo)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nao foi possivel ler a imagem.")

    digitalizada, aviso = scanner.digitalizar(original)
    textos = scanner.ler_textos(digitalizada)
    sugerido = scanner.escolher_nome_sugerido(textos)

    PASTA_TEMP.mkdir(parents=True, exist_ok=True)
    id_temp = uuid.uuid4().hex
    if not cv2.imwrite(str(PASTA_TEMP / f"{id_temp}.jpg"), digitalizada):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Falha ao guardar a imagem.")

    _, buffer = cv2.imencode(".jpg", digitalizada)

    return AnaliseCartao(
        id=id_temp,
        nome_sugerido=sugerido,
        textos=[TextoDetectado(**{k: t[k] for k in ("texto", "confianca", "altura")}) for t in textos],
        imagem_base64=base64.b64encode(buffer.tobytes()).decode(),
        aviso=aviso,
        crianca_id=crianca.id,
        crianca_nome=crianca.nome,
        instituicao=crianca.instituicao.nome,
    )


@router.post("/confirmar", response_model=CartaoOut, status_code=status.HTTP_201_CREATED)
def confirmar(dados: ConfirmarCartao, db: BD, ctx: Subir):
    """Move a imagem para a pasta da edicao e grava o cartao."""
    if not dados.id.isalnum():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Identificador invalido.")

    caminho_temp = PASTA_TEMP / f"{dados.id}.jpg"
    if not caminho_temp.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Analise nao encontrada. Fotografe o cartao de novo."
        )

    crianca = _buscar_crianca(db, ctx, dados.crianca_id, "subir_cartoes")

    pasta = arquivos.pasta_dos_cartoes(crianca.edicao.cidade.nome, crianca.edicao.ano)
    pasta.mkdir(parents=True, exist_ok=True)

    destino = arquivos.caminho_disponivel(
        pasta, arquivos.nome_do_cartao(crianca.instituicao.nome, crianca.nome, dados.tipo)
    )
    relativo = str(destino.relative_to(config.caminho_arquivos))

    cartao = Cartao(
        crianca_id=crianca.id,
        tipo=dados.tipo,
        arquivo=relativo,
        texto_ocr=dados.texto_ocr,
        monitor_id=ctx.usuario.id,
    )
    db.add(cartao)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Esta crianca ja tem cartao de {dados.tipo}.",
        )

    # So move o arquivo depois de a base aceitar: assim nao fica imagem orfa.
    caminho_temp.replace(destino)

    registrar(
        db, "cartao_digitalizado", usuario_id=ctx.usuario.id,
        tabela="cartoes", registro_id=cartao.id,
        detalhes={"crianca_id": crianca.id, "tipo": dados.tipo, "arquivo": relativo},
    )
    db.commit()

    return _saida(db, db.scalar(
        select(Cartao).where(Cartao.id == cartao.id)
        .options(joinedload(Cartao.crianca).joinedload(Crianca.instituicao))
    ))


@router.get("/{cartao_id}/imagem")
def imagem_do_cartao(cartao_id: int, db: BD, ctx: Ver):
    """Devolve a imagem. Unica porta para os arquivos, sempre autenticada."""
    cartao = db.scalar(
        select(Cartao).where(Cartao.id == cartao_id, _filtro(ctx, "ver_criancas"))
    )
    if cartao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cartao nao encontrado.")

    try:
        caminho = arquivos.dentro_da_pasta(cartao.arquivo)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo nao encontrado.")

    if not caminho.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo nao encontrado.")

    return FileResponse(caminho, media_type="image/jpeg")


@router.post("/enviados", response_model=list[CartaoOut])
def marcar_enviados(dados: MarcarEnviados, db: BD, ctx: Enviar):
    """Marca os cartoes como enviados aos padrinhos."""
    cartoes = db.scalars(
        select(Cartao)
        .where(Cartao.id.in_(dados.cartoes), _filtro(ctx, "ver_criancas"))
        .options(joinedload(Cartao.crianca).joinedload(Crianca.instituicao))
    ).all()

    if len(cartoes) != len(set(dados.cartoes)):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Ha cartoes que voce nao alcanca ou que nao existem."
        )

    sem_padrinho = [c.id for c in cartoes if _padrinho_do_cartao(db, c) is None]
    if sem_padrinho:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{len(sem_padrinho)} cartao(oes) ainda nao tem padrinho para receber.",
        )

    agora = datetime.now(UTC)
    for cartao in cartoes:
        cartao.status = StatusCartao.ENVIADO.value
        cartao.enviado_por = ctx.usuario.id
        cartao.enviado_em = agora

    registrar(
        db, "cartoes_enviados", usuario_id=ctx.usuario.id,
        tabela="cartoes",
        detalhes={"cartoes": [c.id for c in cartoes]},
    )
    db.commit()

    return [_saida(db, c) for c in cartoes]
