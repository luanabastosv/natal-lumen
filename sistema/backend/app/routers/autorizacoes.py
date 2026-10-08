"""Autorizacoes: a assinada pelo responsavel de cada crianca.

Sobem pelo envio em lote dos cartoes (`POST /cartoes/lote` com
`tipo=autorizacao`), porque o caminho do papel e o mesmo. Aqui fica o resto:
listar a pasta, abrir a imagem e corrigir o que subiu errado — com as mesmas
permissoes da pilha de cartoes, que e quem recolhe as duas.
"""

from typing import Annotated

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import config
from app.database import get_db
from app.models import Autorizacao, Crianca, Edicao
from app.schemas.autorizacoes import AutorizacaoOut
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos import arquivos, imagens, scanner
from app.servicos.log import registrar
from app.servicos.upload import ler_limitado

router = APIRouter(prefix="/autorizacoes", tags=["autorizacoes"])

BD = Annotated[Session, Depends(get_db)]
Subir = Annotated[ContextoAcesso, Depends(exige_permissao("subir_cartoes"))]
Ver = Annotated[ContextoAcesso, Depends(exige_permissao("ver_criancas"))]


def _filtro(ctx: ContextoAcesso, permissao: str):
    """Autorizacoes das criancas que o usuario alcanca."""
    return Autorizacao.crianca_id.in_(select(Crianca.id).where(ctx.filtro_criancas(permissao)))


def _saida(a: Autorizacao) -> AutorizacaoOut:
    return AutorizacaoOut(
        id=a.id,
        crianca_id=a.crianca_id,
        crianca_codigo=a.crianca.codigo,
        crianca_nome=a.crianca.nome,
        crianca_desistiu_em=a.crianca.desistiu_em,
        instituicao=a.crianca.instituicao.nome,
        criado_em=a.criado_em,
        necessidade_especial=a.necessidade_especial,
        necessidade_especial_qual=a.necessidade_especial_qual,
        restricao_alimentar=a.restricao_alimentar,
        restricao_alimentar_qual=a.restricao_alimentar_qual,
        tem_observacao=a.tem_observacao,
        observacao=a.observacao,
    )


def _buscar(db: Session, ctx: ContextoAcesso, autorizacao_id: int, permissao: str) -> Autorizacao:
    autorizacao = db.scalar(
        select(Autorizacao)
        .where(Autorizacao.id == autorizacao_id, _filtro(ctx, permissao))
        .options(
            joinedload(Autorizacao.crianca).joinedload(Crianca.instituicao),
            joinedload(Autorizacao.crianca).joinedload(Crianca.edicao).joinedload(Edicao.cidade),
        )
    )
    if autorizacao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Autorizacao nao encontrada.")
    return autorizacao


@router.get("", response_model=list[AutorizacaoOut])
def listar(db: BD, ctx: Ver, edicao_id: int, instituicao_id: int):
    """As autorizacoes de uma pasta. Sem paginacao: e uma por crianca, e uma
    escola nao passa de algumas dezenas."""
    de_criancas = select(Crianca.id).where(
        Crianca.edicao_id == edicao_id, Crianca.instituicao_id == instituicao_id
    )
    itens = db.scalars(
        select(Autorizacao)
        .where(_filtro(ctx, "ver_criancas"), Autorizacao.crianca_id.in_(de_criancas))
        .options(joinedload(Autorizacao.crianca).joinedload(Crianca.instituicao))
        .order_by(Autorizacao.criado_em.desc())
    ).all()
    return [_saida(a) for a in itens]


@router.get("/{autorizacao_id}/imagem")
def imagem(autorizacao_id: int, db: BD, ctx: Ver):
    """Unica porta para o arquivo, sempre autenticada."""
    return imagens.servir(_buscar(db, ctx, autorizacao_id, "ver_criancas").arquivo)


@router.get("/{autorizacao_id}/miniatura")
def miniatura(autorizacao_id: int, db: BD, ctx: Ver):
    return imagens.servir_miniatura(_buscar(db, ctx, autorizacao_id, "ver_criancas").arquivo)


@router.delete("/{autorizacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(autorizacao_id: int, db: BD, ctx: Subir):
    """Apaga uma autorizacao subida por engano, e o arquivo dela junto."""
    autorizacao = _buscar(db, ctx, autorizacao_id, "subir_cartoes")
    imagens.apagar_do_disco(autorizacao.arquivo)

    registrar(
        db, "autorizacao_apagada", usuario_id=ctx.usuario.id,
        tabela="autorizacoes", registro_id=autorizacao.id,
        detalhes={"crianca_id": autorizacao.crianca_id},
    )
    db.delete(autorizacao)
    db.commit()


@router.post("/{autorizacao_id}/trocar", response_model=AutorizacaoOut)
async def trocar_imagem(
    autorizacao_id: int,
    db: BD,
    ctx: Subir,
    arquivo: UploadFile = File(...),
):
    """Troca a imagem, sem mexer no resto. Passa pelo mesmo endireitamento da
    pilha, como a troca de cartao."""
    autorizacao = _buscar(db, ctx, autorizacao_id, "subir_cartoes")

    imagens.conferir_nome_da_troca(db, arquivo.filename, autorizacao.crianca)

    conteudo = await ler_limitado(arquivo)
    endireitada, _aviso = scanner.digitalizar(scanner.carregar_imagem(conteudo))

    crianca = autorizacao.crianca
    pasta = arquivos.pasta_das_autorizacoes(crianca.edicao.cidade.nome, crianca.edicao.ano)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = arquivos.caminho_disponivel(
        pasta, arquivos.nome_do_cartao(crianca.instituicao.nome, crianca.nome, "autorizacao")
    )
    if not cv2.imwrite(str(destino), endireitada):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Nao foi possivel guardar a imagem."
        )

    # A antiga so sai DEPOIS de a nova estar no disco.
    antiga = autorizacao.arquivo
    autorizacao.arquivo = str(destino.relative_to(config.caminho_arquivos))
    autorizacao.monitor_id = ctx.usuario.id
    imagens.apagar_do_disco(antiga)

    registrar(
        db, "autorizacao_trocada", usuario_id=ctx.usuario.id,
        tabela="autorizacoes", registro_id=autorizacao.id,
        detalhes={"crianca_id": autorizacao.crianca_id},
    )
    db.commit()
    db.refresh(autorizacao)
    return _saida(autorizacao)
