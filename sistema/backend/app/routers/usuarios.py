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
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import config
from app.database import get_db
from app.models import (
    Crianca,
    Edicao,
    Instituicao,
    Perfil,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.models.tipos import TipoToken
from app.schemas.cadastros import DependenciasOut
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
from app.seeds.perfis_permissoes import (
    PERFIL_COMISSARIO,
    PERFIL_COORDENACAO,
    PERFIS_COM_GRUPO,
    PERFIS_FILTRADOS_POR_INSTITUICAO,
)
from app.seguranca.dependencias import exige_permissao
from app.servicos import coordenacao, exclusao, grupos, tokens_acesso
from app.servicos.log import registrar
from app.servicos.nomes import nome_proprio

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

BD = Annotated[Session, Depends(get_db)]
Gestor = Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_usuarios"))]


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
                grupo_id=v.grupo_id,
                grupo=v.grupo.nome if v.grupo else None,
                usa_grupo=v.perfil.nome in PERFIS_COM_GRUPO,
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
        pediu_senha_em=usuario.pediu_senha_em,
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
            selectinload(Usuario.edicoes).selectinload(UsuarioEdicao.grupo),
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


def _conferir_pode_apagar(db: Session, ctx: ContextoAcesso, usuario: Usuario) -> None:
    """Apagar e mais restrito que editar, por tres motivos diferentes.

    A propria conta: quem se apagasse sairia do sistema no meio do clique, sem
    ter como voltar.

    A ultima administracao geral: sem ela ninguem cria cidade, edicao nem outra
    administracao — seria um sistema trancado por fora, sem conserto pela tela.

    Conta com vinculo fora do alcance: a coordenacao gerencia a equipe DAS SUAS
    edicoes. Se a pessoa tambem trabalha noutra cidade, apagar a conta levaria
    junto um acesso que esta coordenacao nunca teve autoridade para tirar — o
    caminho ali e desativar o vinculo desta edicao, nao apagar a pessoa.
    """
    if usuario.id == ctx.usuario.id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Voce nao pode apagar a propria conta.",
        )

    if usuario.admin_geral:
        outras = db.scalar(
            select(func.count())
            .select_from(Usuario)
            .where(
                Usuario.admin_geral.is_(True),
                Usuario.ativo.is_(True),
                Usuario.id != usuario.id,
            )
        )
        if not outras:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Esta e a ultima conta de administracao geral ativa: sem ela "
                "ninguem mais administra o sistema.",
            )

    if not ctx.admin_geral:
        geridas = set(_edicoes_geridas(ctx))
        fora = [v for v in usuario.edicoes if v.edicao_id not in geridas]
        if fora:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Esta pessoa tambem tem acesso a uma edicao que voce nao "
                "gerencia. Desative o vinculo desta edicao em vez de apagar a conta.",
            )


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


def _definir_grupo(
    db: Session, vinculo: UsuarioEdicao, perfil: Perfil, nome: str | None
) -> None:
    """Nomeia o grupo da comunidade pelo qual este comissario responde.

    O nome chega escrito a mao. O grupo da cidade com esse nome e reaproveitado
    se ja existir — e a comparacao ignora acento e caixa, senao "Elyon" e
    "élyon" vira dois — e criado se for a primeira vez.

    Perfil que nao e comissario nao guarda grupo: trocar de comissario para
    monitor apaga o nome, do mesmo jeito que a lista de instituicoes deixa de
    valer para a coordenacao. Um grupo pendurado num vinculo que nao o usa
    reapareceria sozinho no dia em que a pessoa voltasse a ser comissaria.
    """
    if perfil.nome not in PERFIS_COM_GRUPO or not (nome or "").strip():
        vinculo.grupo_id = None
        return

    edicao = db.get(Edicao, vinculo.edicao_id)
    grupo = grupos.achar_ou_criar(db, edicao.cidade_id, nome)
    vinculo.grupo_id = grupo.id if grupo else None



def _soltar_criancas_fora_do_alcance(db: Session, vinculo: UsuarioEdicao) -> int:
    """Solta as criancas que estavam no nome dele e que ele nao alcanca mais.

    criancas.comissario_id diz quem responde por cada crianca. Ele deixa de
    alcancar quando a instituicao sai da atribuicao, quando o vinculo e
    desativado ou quando o perfil deixa de responder por crianca — e nos tres
    casos um nome que nao enxerga mais a crianca e pior que nenhum.

    Chamar DEPOIS de gravar a mudanca no vinculo (precisa do estado novo).
    """
    # A coordenacao ativa alcanca a edicao inteira: crianca no nome dela nunca
    # sai do alcance por instituicao, porque instituicao nao a limita.
    if vinculo.ativo and vinculo.perfil.nome == PERFIL_COORDENACAO:
        return 0

    ainda_alcanca: set[int] = set()
    if vinculo.ativo and vinculo.perfil.nome == PERFIL_COMISSARIO:
        ainda_alcanca = {i.instituicao_id for i in vinculo.instituicoes if i.ativo}

    condicoes = [
        Crianca.edicao_id == vinculo.edicao_id,
        Crianca.comissario_id == vinculo.usuario_id,
    ]
    if ainda_alcanca:
        condicoes.append(Crianca.instituicao_id.not_in(ainda_alcanca))

    soltas = db.execute(
        update(Crianca).where(*condicoes).values(comissario_id=None)
    ).rowcount
    return soltas or 0


def _espelhos(vinculos: list[UsuarioEdicao]) -> dict:
    """As outras edicoes da cidade que a mudanca alcancou, para o log.

    Vai para o log porque e o unico rastro de uma mudanca que ninguem pediu
    tela nenhuma: quem nomeia a coordenacao escolhe uma edicao e o sistema mexe
    nas outras. Sem isto, o acesso apareceria do nada em 2027.
    """
    if not vinculos:
        return {}
    return {"edicoes_alcancadas": sorted(v.edicao_id for v in vinculos)}


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
        selectinload(Usuario.edicoes).selectinload(UsuarioEdicao.grupo),
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

    usuario = Usuario(nome=nome_proprio(dados.nome), email=email, whatsapp=dados.whatsapp)
    db.add(usuario)
    db.flush()

    ligacao = UsuarioEdicao(
        usuario_id=usuario.id, edicao_id=vinculo.edicao_id, perfil_id=perfil.id
    )
    db.add(ligacao)
    db.flush()
    _definir_instituicoes(db, ligacao, vinculo.instituicoes)
    _definir_grupo(db, ligacao, perfil, vinculo.grupo)

    # A coordenacao e da cidade, nao do ano: o vinculo se repete em todas as
    # edicoes ativas dela.
    espelhados = (
        coordenacao.espelhar(db, ligacao) if perfil.nome == PERFIL_COORDENACAO else []
    )

    link, expira = _gerar_link(db, usuario)

    registrar(
        db, "usuario_criado", usuario_id=ctx.usuario.id,
        tabela="usuarios", registro_id=usuario.id,
        detalhes={
            "email": email,
            "perfil": perfil.nome,
            "edicao_id": vinculo.edicao_id,
            **_espelhos(espelhados),
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
        setattr(usuario, campo, nome_proprio(valor) if campo == "nome" and valor else valor)

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
    _definir_grupo(db, vinculo, perfil, dados.grupo)

    espelhados = (
        coordenacao.espelhar(db, vinculo) if perfil.nome == PERFIL_COORDENACAO else []
    )

    registrar(
        db, "vinculo_criado", usuario_id=ctx.usuario.id,
        tabela="usuario_edicao", registro_id=vinculo.id,
        detalhes={
            "usuario_id": usuario.id,
            "edicao_id": dados.edicao_id,
            "perfil": perfil.nome,
            **_espelhos(espelhados),
        },
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

    perfil = db.get(Perfil, vinculo.perfil_id)
    # Lido antes da troca: quem SAI da coordenacao precisa ter o alcance de
    # cidade desfeito, e depois de mudar o perfil nao ha mais como saber disso.
    era_coordenacao = perfil.nome == PERFIL_COORDENACAO

    # Mexer num vinculo de coordenacao E definir a coordenacao da cidade, e
    # isso e da administracao geral — a mesma regra que ja vale para cria-lo.
    # Sem esta linha, uma coordenacao suspenderia a colega e o acesso cairia na
    # cidade inteira, incluindo os anos em que ela nem trabalha.
    if era_coordenacao and not ctx.admin_geral:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Apenas a administracao geral mexe no acesso da coordenacao.",
        )

    if dados.perfil_id is not None:
        perfil = _conferir_perfil(db, ctx, dados.perfil_id)
        vinculo.perfil_id = perfil.id

    if dados.ativo is not None:
        vinculo.ativo = dados.ativo

    if dados.instituicoes is not None:
        _conferir_instituicoes(db, vinculo.edicao_id, dados.instituicoes)
        _definir_instituicoes(db, vinculo, dados.instituicoes)

    # O grupo tambem e mexido quando o perfil deixa de ser comissario sem que a
    # tela tenha mandado campo nenhum: quem nao usa grupo nao guarda grupo.
    pedidos = dados.model_dump(exclude_unset=True)
    if "grupo" in pedidos or perfil.nome not in PERFIS_COM_GRUPO:
        _definir_grupo(db, vinculo, perfil, dados.grupo)

    # O estado novo precisa estar na sessao antes de conferir o que ele ainda
    # alcanca; sem o flush, as instituicoes recem-atribuidas nao apareceriam.
    db.flush()
    db.refresh(vinculo)
    soltas = _soltar_criancas_fora_do_alcance(db, vinculo)

    # O alcance de cidade anda junto com este vinculo: continuar coordenacao
    # leva o perfil e o `ativo` para as outras edicoes ativas da cidade — e e
    # por isso que suspender aqui suspende na cidade inteira. Sair dela desativa
    # os espelhos, que so existiam por causa da coordenacao.
    if perfil.nome == PERFIL_COORDENACAO:
        espelhados = coordenacao.espelhar(db, vinculo)
    elif era_coordenacao:
        espelhados = coordenacao.encerrar(db, vinculo)
    else:
        espelhados = []

    for espelho in espelhados:
        db.refresh(espelho)
        soltas += _soltar_criancas_fora_do_alcance(db, espelho)

    registrar(
        db, "vinculo_editado", usuario_id=ctx.usuario.id,
        tabela="usuario_edicao", registro_id=vinculo.id,
        detalhes={
            "campos": sorted(pedidos),
            **({"criancas_soltas": soltas} if soltas else {}),
            **_espelhos(espelhados),
        },
    )
    db.commit()
    return _saida(db, _carregar(db, usuario_id))


@router.get("/{usuario_id}/dependencias", response_model=DependenciasOut)
def dependencias(usuario_id: int, db: BD, ctx: Gestor):
    """O que some junto com a conta. A tela pergunta isto antes de apagar."""
    usuario = _carregar(db, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario nao encontrado.")
    _conferir_alcance(ctx, usuario)
    _conferir_pode_apagar(db, ctx, usuario)

    return exclusao.resumir_usuario(db, usuario)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(usuario_id: int, db: BD, ctx: Gestor):
    """Apaga a conta de vez.

    Desativar costuma ser o certo e e o que a tela oferece primeiro: guarda o
    historico de quem fez o que. Apagar existe para a conta que nunca deveria
    ter sido criada — o email errado, a pessoa que desistiu antes de comecar.
    """
    usuario = _carregar(db, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario nao encontrado.")
    _conferir_alcance(ctx, usuario)
    _conferir_pode_apagar(db, ctx, usuario)

    # Contado ANTES do delete: depois nenhuma crianca aponta mais para ele. Vai
    # para o log porque e o rastro que sobra — as criancas continuam la, sem
    # responsavel, e alguem vai precisar saber quantas foram e de quem eram.
    orfas = exclusao.criancas_sob_responsabilidade(db, usuario.id)

    registrar(
        db, "usuario_apagado", usuario_id=ctx.usuario.id,
        tabela="usuarios", registro_id=usuario.id,
        detalhes={
            "nome": usuario.nome,
            "email": usuario.email,
            "edicoes": sorted(v.edicao_id for v in usuario.edicoes),
            **({"criancas_sem_responsavel": orfas} if orfas else {}),
        },
    )
    db.delete(usuario)
    db.commit()
