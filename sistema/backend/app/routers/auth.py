"""Rotas de autenticacao: login, logout, sessao e definicao de senha."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import config
from app.database import get_db
from app.models import Edicao, Usuario
from app.models.tipos import TipoToken
from app.schemas.auth import (
    DefinirSenhaIn,
    EsqueciSenhaIn,
    LoginIn,
    MensagemOut,
    UsuarioOut,
    VinculoOut,
)
from app.seguranca.contexto import ContextoAcesso, montar_contexto
from app.seguranca.dependencias import Contexto
from app.seguranca.senhas import conferir, gerar_hash, senha_fraca
from app.seguranca.sessao import apagar_cookies, criar_token, gravar_cookies
from app.servicos import tokens_acesso
from app.servicos.log import registrar

router = APIRouter(prefix="/auth", tags=["autenticacao"])

BD = Annotated[Session, Depends(get_db)]

# Mensagem unica para email inexistente, senha errada ou conta inativa: dizer
# qual dos tres seria entregar a lista de emails validos a quem tenta adivinhar.
CREDENCIAIS_INVALIDAS = "Email ou senha invalidos."


def _bloqueado(usuario: Usuario) -> bool:
    if usuario.bloqueado_ate is None:
        return False
    ate = usuario.bloqueado_ate
    if ate.tzinfo is None:
        ate = ate.replace(tzinfo=UTC)
    return ate > datetime.now(UTC)


def _montar_saida(db: Session, ctx: ContextoAcesso) -> UsuarioOut:
    edicoes = {
        e.id: e
        for e in db.scalars(
            select(Edicao).where(Edicao.id.in_([v.edicao_id for v in ctx.vinculos]))
        ).all()
    }

    vinculos = []
    for vinculo in ctx.vinculos:
        edicao = edicoes.get(vinculo.edicao_id)
        if edicao is None:
            continue
        vinculos.append(
            VinculoOut(
                edicao_id=vinculo.edicao_id,
                edicao=edicao.nome,
                cidade=edicao.cidade.nome,
                ano=edicao.ano,
                perfil=vinculo.perfil,
                permissoes=sorted(vinculo.permissoes),
                instituicoes=(
                    sorted(vinculo.instituicoes)
                    if vinculo.filtrado_por_instituicao
                    else None
                ),
            )
        )

    return UsuarioOut(
        id=ctx.usuario.id,
        nome=ctx.usuario.nome,
        email=ctx.usuario.email,
        admin_geral=ctx.admin_geral,
        permissoes=sorted(ctx.permissoes),
        vinculos=vinculos,
    )


@router.post("/login", response_model=UsuarioOut)
def login(dados: LoginIn, resposta: Response, request: Request, db: BD):
    email = dados.email.lower().strip()
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))

    if usuario is None:
        registrar(db, "login_falhou", detalhes={"email": email, "motivo": "inexistente"})
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, CREDENCIAIS_INVALIDAS)

    if _bloqueado(usuario):
        registrar(db, "login_bloqueado", usuario_id=usuario.id)
        db.commit()
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Conta bloqueada por {config.bloqueio_minutos} minutos apos "
            f"{config.max_tentativas_falhas} tentativas. Tente mais tarde.",
        )

    if not usuario.ativo or not conferir(dados.senha, usuario.senha_hash):
        usuario.tentativas_falhas += 1
        motivo = "inativo" if not usuario.ativo else "senha_errada"

        if usuario.tentativas_falhas >= config.max_tentativas_falhas:
            usuario.bloqueado_ate = datetime.now(UTC) + timedelta(
                minutes=config.bloqueio_minutos
            )
            registrar(db, "conta_bloqueada", usuario_id=usuario.id)

        registrar(
            db,
            "login_falhou",
            usuario_id=usuario.id,
            detalhes={"motivo": motivo, "tentativas": usuario.tentativas_falhas},
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, CREDENCIAIS_INVALIDAS)

    # Sucesso: zera o contador e abre a sessao.
    usuario.tentativas_falhas = 0
    usuario.bloqueado_ate = None
    usuario.ultimo_login = datetime.now(UTC)

    token, csrf = criar_token(usuario.id)
    gravar_cookies(resposta, token, csrf)

    registrar(db, "login", usuario_id=usuario.id)
    db.commit()

    return _montar_saida(db, montar_contexto(db, usuario))


@router.post("/logout", response_model=MensagemOut)
def logout(resposta: Response, db: BD, ctx: Contexto):
    apagar_cookies(resposta)
    registrar(db, "logout", usuario_id=ctx.usuario.id)
    db.commit()
    return MensagemOut(mensagem="Sessao encerrada.")


@router.get("/eu", response_model=UsuarioOut)
def eu(db: BD, ctx: Contexto):
    """Quem esta na sessao, com permissoes e vinculos. O frontend chama ao abrir."""
    return _montar_saida(db, ctx)


@router.post("/definir-senha", response_model=MensagemOut)
def definir_senha(dados: DefinirSenhaIn, db: BD):
    """Define a senha pelo link de primeiro acesso ou de redefinicao."""
    motivo = senha_fraca(dados.senha)
    if motivo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, motivo)

    registro = tokens_acesso.validar(db, dados.token)
    if registro is None:
        registrar(db, "definir_senha_token_invalido")
        db.commit()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Link invalido, ja usado ou expirado. Peca um link novo.",
        )

    usuario = db.get(Usuario, registro.usuario_id)
    if usuario is None or not usuario.ativo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link invalido.")

    usuario.senha_hash = gerar_hash(dados.senha)
    # Definir a senha tambem solta a conta de um bloqueio em curso.
    usuario.tentativas_falhas = 0
    usuario.bloqueado_ate = None
    tokens_acesso.consumir(registro)

    registrar(
        db,
        "senha_definida",
        usuario_id=usuario.id,
        tabela="usuarios",
        registro_id=usuario.id,
        detalhes={"tipo": registro.tipo},
    )
    db.commit()

    return MensagemOut(mensagem="Senha definida. Ja pode entrar.")


@router.post("/esqueci-senha", response_model=MensagemOut)
def esqueci_senha(dados: EsqueciSenhaIn, db: BD):
    """Gera um link de redefinicao.

    Responde sempre a mesma coisa, exista o email ou nao: a resposta nao pode
    revelar quem tem conta no sistema.
    """
    email = dados.email.lower().strip()
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))

    resposta = MensagemOut(
        mensagem="Se este email tiver conta, enviamos um link para redefinir a senha."
    )

    if usuario is None or not usuario.ativo:
        registrar(db, "esqueci_senha", detalhes={"email": email, "encontrado": False})
        db.commit()
        return resposta

    token = tokens_acesso.gerar(db, usuario, TipoToken.REDEFINIR_SENHA, horas=2)
    registrar(db, "esqueci_senha", usuario_id=usuario.id, detalhes={"encontrado": True})
    db.commit()

    # O envio por email entra quando houver servidor de email configurado.
    # Ate la, em desenvolvimento, o link volta na resposta.
    if not config.em_producao:
        resposta.link = f"/acesso/definir-senha?token={token}"

    return resposta
