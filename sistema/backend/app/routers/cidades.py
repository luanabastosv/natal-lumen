"""Cidades. So a administracao geral cria e edita."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cidade, Edicao
from app.schemas.cadastros import CidadeIn, CidadeOut, DependenciasOut
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import Contexto, exige_admin_geral
from app.servicos import exclusao
from app.seguranca.reconfirmar import exigir_senha
from app.servicos.log import registrar

router = APIRouter(prefix="/cidades", tags=["cadastros"])

BD = Annotated[Session, Depends(get_db)]
Admin = Annotated[ContextoAcesso, Depends(exige_admin_geral)]


def _buscar(db: Session, cidade_id: int) -> Cidade:
    cidade = db.get(Cidade, cidade_id)
    if cidade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cidade nao encontrada.")
    return cidade


@router.get("", response_model=list[CidadeOut])
def listar(db: BD, ctx: Contexto):
    """Admin ve todas; os demais, so as cidades das edicoes que alcancam."""
    consulta = select(Cidade).order_by(Cidade.nome)

    if not ctx.admin_geral:
        if not ctx.edicoes:
            return []
        consulta = consulta.where(
            Cidade.id.in_(select(Edicao.cidade_id).where(Edicao.id.in_(ctx.edicoes)))
        )

    return db.scalars(consulta).all()


@router.post("", response_model=CidadeOut, status_code=status.HTTP_201_CREATED)
def criar(dados: CidadeIn, db: BD, ctx: Admin):
    cidade = Cidade(nome=dados.nome.strip(), uf=dados.uf.upper(), ativo=dados.ativo)
    db.add(cidade)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ja existe uma cidade com este nome nesta UF."
        )

    registrar(
        db, "cidade_criada", usuario_id=ctx.usuario.id,
        tabela="cidades", registro_id=cidade.id,
        detalhes={"nome": cidade.nome, "uf": cidade.uf},
    )
    db.commit()
    db.refresh(cidade)
    return cidade


@router.patch("/{cidade_id}", response_model=CidadeOut)
def editar(cidade_id: int, dados: CidadeIn, db: BD, ctx: Admin):
    cidade = _buscar(db, cidade_id)

    cidade.nome = dados.nome.strip()
    cidade.uf = dados.uf.upper()
    cidade.ativo = dados.ativo

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ja existe uma cidade com este nome nesta UF."
        )

    registrar(
        db, "cidade_editada", usuario_id=ctx.usuario.id,
        tabela="cidades", registro_id=cidade.id,
    )
    db.commit()
    db.refresh(cidade)
    return cidade


@router.get("/{cidade_id}/dependencias", response_model=DependenciasOut)
def dependencias(cidade_id: int, db: BD, ctx: Admin):
    """O que seria apagado junto com a cidade. A tela pergunta isto antes."""
    cidade = _buscar(db, cidade_id)
    return exclusao.resumir(
        db, cidade.id, f"{cidade.nome} ({cidade.uf})", exclusao.alcance_da_cidade(cidade_id)
    )


@router.delete("/{cidade_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(
    cidade_id: int,
    db: BD,
    ctx: Admin,
    confirmar: Annotated[bool, Query()] = False,
    # A senha de quem apaga, de novo: ver seguranca/reconfirmar.py.
    senha: Annotated[str | None, Body(embed=True)] = None,
):
    """Apaga a cidade e, com ela, as edicoes e instituicoes que estao dentro.

    `confirmar` existe para a exclusao nunca acontecer por engano fora da
    tela: com dados pendurados, o pedido sem confirmacao volta 409 com a conta
    de quantos sao. O frontend so chega aqui depois de mostrar essa conta no
    modal.
    """
    cidade = _buscar(db, cidade_id)
    # Apagar a cidade leva as edicoes junto: a mesma senha de novo.
    exigir_senha(db, ctx, senha, "apagar_cidade")
    # Lido antes do DELETE: depois dele o objeto nao pode mais ser consultado.
    nome, uf = cidade.nome, cidade.uf

    resumo = exclusao.resumir(db, cidade_id, nome, exclusao.alcance_da_cidade(cidade_id))
    if resumo.total and not confirmar:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{nome} tem {resumo.total} registro(s) ligados a ela. "
            "Confirme a exclusao para apagar tudo junto.",
        )

    orfaos = exclusao.apagar_cidade(db, cidade_id)

    registrar(
        db, "cidade_apagada", usuario_id=ctx.usuario.id,
        tabela="cidades", registro_id=cidade_id,
        detalhes={
            "nome": nome,
            "uf": uf,
            "levou": {item.chave: item.quantidade for item in resumo.itens},
        },
    )
    db.commit()
    exclusao.remover_arquivos(orfaos)
