"""Usuarios, vinculos com edicoes e atribuicao de instituicoes.

Regras que esta rota faz valer:
  - a coordenacao so mexe em usuarios das SUAS edicoes;
  - so a administracao geral cria coordenadores de cidade;
  - a instituicao atribuida tem de ser da mesma cidade da edicao — o banco nao
    consegue exigir isso com uma chave estrangeira, porque cruza duas tabelas.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import config
from app.database import get_db
from app.models import (
    Edicao,
    Instituicao,
    Perfil,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.models.tipos import TipoToken
from app.schemas.usuarios import (
    UsuarioCriado,
    UsuarioDetalhe,
    UsuarioEditar,
    UsuarioIn,
    VinculoDetalhe,
    VinculoEditar,
    VinculoIn,
)
from app.seguranca.contexto import ContextoAcesso
from app.seeds.perfis_permissoes import PERFIS_FILTRADOS_POR_INSTITUICAO
from app.seguranca.dependencias import exige_permissao
from app.servicos import tokens_acesso
from app.servicos.log import registrar

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

BD = Annotated[Session, Depends(get_db)]
Gestor = Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_usuarios"))]

PERFIL_COORDENACAO = "Coordenacao"


# ---------------------------------------------------------------- apoio

def _edicoes_geridas(ctx: ContextoAcesso) -> list[int]:
    return ctx.edicoes_com("gerenciar_usuarios")


def _saida(db: Session, usuario: Usuario) -> UsuarioDetalhe:
    vinculos = []
    for v in usuario.edicoes:
        vinculos.append(
            VinculoDetalhe(
                id=v.id,
                edicao_id=v.edicao_id,
                edicao=v.edicao.nome,
                cidade=v.edicao.cidade.nome,
                ano=v.edicao.ano,
                perfil_id=v.perfil_id,
                perfil=v.perfil.nome,
                ativo=v.ativo,
                instituicoes=sorted(i.instituicao_id for i in v.instituicoes if i.ativo),
                filtrado_por_instituicao=v.perfil.nome in PERFIS_FILTRADOS_POR_INSTITUICAO,
            )
        )

    bloqueado_ate = usuario.bloqueado_ate
    if bloqueado_ate is not None and bloqueado_ate.tzinfo is None:
        bloqueado_ate = bloqueado_ate.replace(tzinfo=UTC)

    return UsuarioDetalhe(
        id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        whatsapp=usuario.whatsapp,
        admin_geral=usuario.admin_geral,
        ativo=usuario.ativo,
        tem_senha=usuario.tem_senha,
        bloqueado=bool(bloqueado_ate and bloqueado_ate > datetime.now(UTC)),
        ultimo_login=usuario.ultimo_login,
        criado_em=usuario.criado_em,
        vinculos=sorted(vinculos, key=lambda v: (-v.ano, v.cidade)),
    )


def _carregar(db: Session, usuario_id: int) -> Usuario | None:
    return db.scalar(
        select(Usuario)
        .where(Usuario.id == usuario_id)
        .options(
            selectinload(Usuario.edicoes).selectinload(UsuarioEdicao.perfil),
            selectinload(Usuario.edicoes)
            .selectinload(UsuarioEdicao.edicao)
            .joinedload(Edicao.cidade),
            selectinload(Usuario.edicoes).selectinload(UsuarioEdicao.instituicoes),
        )
    )


def _conferir_alcance(ctx: ContextoAcesso, usuario: Usuario) -> None:
    """A coordenacao so mexe em quem tem vinculo com uma edicao dela."""
    if ctx.admin_geral:
        return

    if usuario.admin_geral:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Apenas a administracao geral mexe em contas de administracao.",
        )

    geridas = set(_edicoes_geridas(ctx))
    if not any(v.edicao_id in geridas for v in usuario.edicoes):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario nao encontrado.")


def _conferir_perfil(db: Session, ctx: ContextoAcesso, perfil_id: int) -> Perfil:
    perfil = db.get(Perfil, perfil_id)
    if perfil is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil nao encontrado.")

    if perfil.nome == PERFIL_COORDENACAO and not ctx.admin_geral:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Apenas a administracao geral define coordenadores de cidade.",
        )

    return perfil


def _conferir_edicao(ctx: ContextoAcesso, edicao_id: int) -> None:
    if ctx.admin_geral:
        return
    if edicao_id not in _edicoes_geridas(ctx):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Voce nao gerencia usuarios desta edicao."
        )


def _conferir_instituicoes(db: Session, edicao_id: int, ids: list[int]) -> None:
    """A instituicao tem de ser da mesma cidade da edicao.

    Nenhuma chave estrangeira consegue exigir isto: instituicoes apontam para
    cidade, edicoes tambem, e a regra cruza as duas. Fica aqui.
    """
    if not ids:
        return

    edicao = db.get(Edicao, edicao_id)
    achadas = db.scalars(select(Instituicao).where(Instituicao.id.in_(set(ids)))).all()

    if len(achadas) != len(set(ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instituicao nao encontrada.")

    fora = [i.nome for i in achadas if i.cidade_id != edicao.cidade_id]
    if fora:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Estas instituicoes nao sao da cidade da edicao: {', '.join(fora)}.",
        )


def _definir_instituicoes(db: Session, vinculo: UsuarioEdicao, ids: list[int]) -> None:
    """Deixa a atribuicao igual a lista pedida."""
    desejadas = set(ids)
    atuais = {i.instituicao_id: i for i in vinculo.instituicoes}

    for instituicao_id, ligacao in atuais.items():
        ligacao.ativo = instituicao_id in desejadas

    for instituicao_id in desejadas - set(atuais):
        db.add(
            UsuarioInstituicao(
                usuario_edicao_id=vinculo.id, instituicao_id=instituicao_id
            )
        )


def _gerar_link(db: Session, usuario: Usuario) -> tuple[str, datetime]:
    token = tokens_acesso.gerar(db, usuario, TipoToken.PRIMEIRO_ACESSO)
    expira = datetime.now(UTC) + timedelta(hours=config.token_primeiro_acesso_horas)
    return f"/acesso/definir-senha?token={token}", expira


# ---------------------------------------------------------------- rotas

@router.get("", response_model=list[UsuarioDetalhe])
def listar(db: BD, ctx: Gestor):
    consulta = select(Usuario).options(
        selectinload(Usuario.edicoes).selectinload(UsuarioEdicao.perfil),
        selectinload(Usuario.edicoes)
        .selectinload(UsuarioEdicao.edicao)
        .joinedload(Edicao.cidade),
        selectinload(Usuario.edicoes).selectinload(UsuarioEdicao.instituicoes),
    )

    if not ctx.admin_geral:
        geridas = _edicoes_geridas(ctx)
        if not geridas:
            return []
        consulta = consulta.where(
            Usuario.id.in_(
                select(UsuarioEdicao.usuario_id).where(
                    UsuarioEdicao.edicao_id.in_(geridas)
                )
            )
        )

    usuarios = db.scalars(consulta.order_by(Usuario.nome)).unique().all()
    return [_saida(db, u) for u in usuarios]


@router.post("", response_model=UsuarioCriado, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioIn, vinculo: VinculoIn, db: BD, ctx: Gestor):
    """Cria a conta e devolve o link de primeiro acesso.

    A conta nasce sem senha. O link e de uso unico e vale 72 horas — a
    coordenacao o entrega ao voluntario (por WhatsApp, em geral).
    """
    _conferir_edicao(ctx, vinculo.edicao_id)
    perfil = _conferir_perfil(db, ctx, vinculo.perfil_id)
    _conferir_instituicoes(db, vinculo.edicao_id, vinculo.instituicoes)

    email = dados.email.lower().strip()
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ja existe uma conta com este email."
        )

    usuario = Usuario(nome=dados.nome.strip(), email=email, whatsapp=dados.whatsapp)
    db.add(usuario)
    db.flush()

    ligacao = UsuarioEdicao(
        usuario_id=usuario.id, edicao_id=vinculo.edicao_id, perfil_id=perfil.id
    )
    db.add(ligacao)
    db.flush()
    _definir_instituicoes(db, ligacao, vinculo.instituicoes)

    link, expira = _gerar_link(db, usuario)

    registrar(
        db, "usuario_criado", usuario_id=ctx.usuario.id,
        tabela="usuarios", registro_id=usuario.id,
        detalhes={
            "email": email,
            "perfil": perfil.nome,
            "edicao_id": vinculo.edicao_id,
        },
    )
    db.commit()

    return UsuarioCriado(usuario=_saida(db, _carregar(db, usuario.id)), link=link, expira_em=expira)


@router.patch("/{usuario_id}", response_model=UsuarioDetalhe)
def editar(usuario_id: int, dados: UsuarioEditar, db: BD, ctx: Gestor):
    usuario = _carregar(db, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario nao encontrado.")
    _conferir_alcance(ctx, usuario)

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        setattr(usuario, campo, valor.strip() if campo == "nome" and valor else valor)

    registrar(
        db, "usuario_editado", usuario_id=ctx.usuario.id,
        tabela="usuarios", registro_id=usuario.id,
        detalhes={"campos": sorted(mudancas)},
    )
    db.commit()
    return _saida(db, _carregar(db, usuario_id))


@router.post("/{usuario_id}/link-de-acesso", response_model=UsuarioCriado)
def novo_link(usuario_id: int, db: BD, ctx: Gestor):
    """Gera um link novo. Invalida o anterior e solta a conta de um bloqueio."""
    usuario = _carregar(db, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario nao encontrado.")
    _conferir_alcance(ctx, usuario)

    usuario.bloqueado_ate = None
    usuario.tentativas_falhas = 0
    link, expira = _gerar_link(db, usuario)

    registrar(
        db, "link_de_acesso_gerado", usuario_id=ctx.usuario.id,
        tabela="usuarios", registro_id=usuario.id,
    )
    db.commit()

    return UsuarioCriado(usuario=_saida(db, _carregar(db, usuario_id)), link=link, expira_em=expira)


@router.post("/{usuario_id}/vinculos", response_model=UsuarioDetalhe, status_code=status.HTTP_201_CREATED)
def criar_vinculo(usuario_id: int, dados: VinculoIn, db: BD, ctx: Gestor):
    usuario = _carregar(db, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario nao encontrado.")
    _conferir_alcance(ctx, usuario)
    _conferir_edicao(ctx, dados.edicao_id)
    perfil = _conferir_perfil(db, ctx, dados.perfil_id)
    _conferir_instituicoes(db, dados.edicao_id, dados.instituicoes)

    vinculo = UsuarioEdicao(
        usuario_id=usuario.id, edicao_id=dados.edicao_id, perfil_id=perfil.id
    )
    db.add(vinculo)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Este usuario ja tem vinculo com esta edicao."
        )

    _definir_instituicoes(db, vinculo, dados.instituicoes)

    registrar(
        db, "vinculo_criado", usuario_id=ctx.usuario.id,
        tabela="usuario_edicao", registro_id=vinculo.id,
        detalhes={"usuario_id": usuario.id, "edicao_id": dados.edicao_id, "perfil": perfil.nome},
    )
    db.commit()
    return _saida(db, _carregar(db, usuario_id))


@router.patch("/{usuario_id}/vinculos/{vinculo_id}", response_model=UsuarioDetalhe)
def editar_vinculo(
    usuario_id: int, vinculo_id: int, dados: VinculoEditar, db: BD, ctx: Gestor
):
    usuario = _carregar(db, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario nao encontrado.")
    _conferir_alcance(ctx, usuario)

    vinculo = db.get(UsuarioEdicao, vinculo_id)
    if vinculo is None or vinculo.usuario_id != usuario_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vinculo nao encontrado.")

    _conferir_edicao(ctx, vinculo.edicao_id)

    if dados.perfil_id is not None:
        vinculo.perfil_id = _conferir_perfil(db, ctx, dados.perfil_id).id

    if dados.ativo is not None:
        vinculo.ativo = dados.ativo

    if dados.instituicoes is not None:
        _conferir_instituicoes(db, vinculo.edicao_id, dados.instituicoes)
        _definir_instituicoes(db, vinculo, dados.instituicoes)

    registrar(
        db, "vinculo_editado", usuario_id=ctx.usuario.id,
        tabela="usuario_edicao", registro_id=vinculo.id,
        detalhes={"campos": sorted(dados.model_dump(exclude_unset=True))},
    )
    db.commit()
    return _saida(db, _carregar(db, usuario_id))
