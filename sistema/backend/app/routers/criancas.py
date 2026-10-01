"""Criancas e importacao das listas enviadas pelas instituicoes.

Dado sensivel (LGPD). Toda consulta aqui passa pelo filtro do contexto, que
limita por edicao, para comissario e monitor tambem por instituicao, e para o
comissario ainda pelas criancas atribuidas a ele.
"""

import json
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import config
from app.database import get_db
from app.models import (
    Apadrinhamento,
    Cartao,
    Crianca,
    DiaEvento,
    Edicao,
    Instituicao,
    InstituicaoDia,
    Kit,
    Padrinho,
    Perfil,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.schemas.cadastros import DependenciasOut
from app.schemas.criancas import (
    ComissarioDoTime,
    CriancaEditar,
    DesistenciaIn,
    CriancaIn,
    CriancaDetalhe,
    CriancaOut,
    CriancasEmLote,
    RenumerarIn,
    CartaoDaCrianca,
    LinhaImportada,
    PadrinhoDaCrianca,
    PaginaCriancas,
    PreviaImportacao,
    ResultadoImportacao,
    ResumoInstituicao,
)
from app.seeds.perfis_permissoes import (
    PERFIL_COMISSARIO,
    PERFIL_COORDENACAO,
    PERFIS_COMISSARIADO,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import Contexto, exige_permissao, exige_qualquer
from app.servicos.apadrinhamento import CONFIRMADO, confirmado
from app.servicos import codigos, dias, exclusao, importador
from app.servicos.nomes import nome_proprio
from app.servicos.upload import ler_limitado
from app.servicos.log import registrar

router = APIRouter(prefix="/criancas", tags=["criancas"])

# A administracao geral nao e um perfil na base — e um atributo da conta. Este
# e o nome que ela usa quando aparece ao lado dos perfis, na lista de quem pode
# responder por uma crianca.
PAPEL_ADMIN_GERAL = "Administracao geral"

BD = Annotated[Session, Depends(get_db)]
Ver = Annotated[ContextoAcesso, Depends(exige_permissao("ver_criancas"))]
Editar = Annotated[ContextoAcesso, Depends(exige_permissao("editar_criancas"))]
# Duas permissoes abrem a porta de editar: a larga, e a estreita de quem so
# redistribui a lista entre o time. Qual delas de fato autoriza a chamada
# depende do que ela esta mudando — ver `_permissoes_da_edicao`.
EditarOuAtribuir = Annotated[
    ContextoAcesso, Depends(exige_qualquer("editar_criancas", "atribuir_comissario"))
]
Importar = Annotated[ContextoAcesso, Depends(exige_permissao("importar_listas"))]

PASTA_IMPORTACOES = config.caminho_arquivos / "importacoes"


# O carregamento padrao da crianca: tudo o que `_saida` le sem voltar ao banco.
# O comissario traz junto os vinculos dele porque o GRUPO mora la — ele e do
# vinculo com a edicao, e nao da pessoa.
CARREGAR = (
    joinedload(Crianca.instituicao),
    joinedload(Crianca.dia_evento),
    joinedload(Crianca.comissario)
    .selectinload(Usuario.edicoes)
    .joinedload(UsuarioEdicao.grupo),
)


def _grupo_do_comissario(crianca: Crianca) -> str | None:
    """O grupo da comunidade de quem responde por esta crianca.

    Procurado pela edicao da crianca, e nao pela pessoa: o mesmo comissario
    pode estar num grupo em Fortaleza e noutro em Caucaia, e o que vale para
    esta crianca e o grupo dele NAQUELA edicao.
    """
    if crianca.comissario is None:
        return None

    for vinculo in crianca.comissario.edicoes:
        if vinculo.edicao_id == crianca.edicao_id:
            return vinculo.grupo.nome if vinculo.grupo else None
    return None


def _ve_padrinho(ctx: ContextoAcesso, edicao_id: int) -> bool:
    """Quem nao capta nao recebe dado de captacao.

    Vale para o monitor e para a estrutura: nenhum dos dois trabalha com
    padrinho, e dado que nao chega a tela e dado que nao vaza por ela. Por
    EDICAO, e nao pelo usuario inteiro: a mesma pessoa pode coordenar uma
    edicao e so monitorar a seguinte.

    Leva junto o comissario responsavel, que e a outra ponta do mesmo assunto:
    quem respondeu por aquela crianca na captacao.
    """
    return ctx.alcanca_edicao(edicao_id, "ver_padrinhos")


def _ve_kit(ctx: ContextoAcesso, edicao_id: int) -> bool:
    """Mesma ideia, do lado da estrutura: so quem monta kit ve o kit."""
    return ctx.alcanca_edicao(edicao_id, "gerenciar_kits")


def _saida(crianca: Crianca, ctx: ContextoAcesso, panorama: dict | None = None) -> CriancaOut:
    extra = panorama or {}
    # As duas perguntas sao feitas aqui, no unico lugar por onde a crianca sai
    # para a tela da lista: assim nao ha rota que esqueca de perguntar.
    padrinho = _ve_padrinho(ctx, crianca.edicao_id)
    kit = _ve_kit(ctx, crianca.edicao_id)
    return CriancaOut(
        id=crianca.id,
        edicao_id=crianca.edicao_id,
        instituicao_id=crianca.instituicao_id,
        instituicao=crianca.instituicao.nome,
        codigo=crianca.codigo,
        nome=crianca.nome,
        idade=crianca.idade,
        sexo=crianca.sexo,
        dia_evento_id=crianca.dia_evento_id,
        dia_evento=crianca.dia_evento.data if crianca.dia_evento else None,
        dia_evento_descricao=crianca.dia_evento.descricao if crianca.dia_evento else None,
        observacoes=crianca.observacoes,
        checkin_em=crianca.checkin_em,
        desistiu_em=crianca.desistiu_em,
        comissario_id=crianca.comissario_id if padrinho else None,
        comissario=(crianca.comissario.nome if crianca.comissario else None) if padrinho else None,
        comissario_grupo=_grupo_do_comissario(crianca) if padrinho else None,
        tem_padrinho_cesta=extra.get("cesta", False) if padrinho else None,
        tem_padrinho_festa=extra.get("festa", False) if padrinho else None,
        promessa_cesta=extra.get("promessa_cesta", False) if padrinho else None,
        promessa_festa=extra.get("promessa_festa", False) if padrinho else None,
        cartoes=extra.get("cartoes", 0),
        kit_status=extra.get("kit", "pendente") if kit else None,
    )


def _panorama(db: Session, ids: list[int]) -> dict[int, dict]:
    """Padrinhos, cartoes e kit de varias criancas, em 3 consultas.

    Buscar isso crianca por crianca daria 4500 consultas numa edicao de 1500 —
    a tela nunca abriria.
    """
    if not ids:
        return {}

    dados: dict[int, dict] = {i: {} for i in ids}

    # Dois estados por tipo, e nao um: a crianca prometida NAO esta apadrinhada
    # (promessa nao e apadrinhamento), mas tambem nao esta livre — o lugar dela
    # naquele tipo esta segurado. Sem distinguir, a lista mostraria a prometida
    # igual a que nao tem ninguem, e alguem tentaria apadrinha-la de novo so
    # para levar um 409 na cara.
    for crianca_id, tipo, pago in db.execute(
        select(
            Apadrinhamento.crianca_id,
            Apadrinhamento.tipo,
            CONFIRMADO.label("pago"),
        ).where(Apadrinhamento.crianca_id.in_(ids))
    ).all():
        dados[crianca_id][tipo if pago else f"promessa_{tipo}"] = True

    for crianca_id, quantos in db.execute(
        select(Cartao.crianca_id, func.count())
        .where(Cartao.crianca_id.in_(ids))
        .group_by(Cartao.crianca_id)
    ).all():
        dados[crianca_id]["cartoes"] = quantos

    for crianca_id, estado in db.execute(
        select(Kit.crianca_id, Kit.status).where(Kit.crianca_id.in_(ids))
    ).all():
        dados[crianca_id]["kit"] = estado

    return dados


def _time(db: Session, edicao_id: int) -> dict[int, tuple[str, set[int], str]]:
    """Quem pode responder por uma crianca desta edicao.

    id -> (nome, instituicoes que ele alcanca, papel).

    O comissario e quem faz isto no dia a dia. Uma instituicao e atendida por
    um TIME — as vezes 2 ou 3 comissarios — mas cada um so alcanca as criancas
    atribuidas a ele: a instituicao (usuario_instituicao) diz ate onde ele
    poderia chegar, e criancas.comissario_id diz onde ele chega de fato. Esta
    lista aqui e de quem PODE receber uma crianca, e quem distribui e a
    coordenacao.

    Coordenacao e administracao geral entram na lista pelo mesmo motivo por que
    entram em todo o resto do sistema: elas fazem tudo o que a equipe faz, e
    sem recorte de instituicao. Captar um padrinho e ficar com a crianca no
    proprio nome e trabalho que a coordenacao tambem pega — e sem isto o nome
    dela nao poderia aparecer na coluna de responsavel.
    """
    edicao = db.get(Edicao, edicao_id)
    if edicao is None:
        return {}

    # O alcance de quem nao e filtrado por instituicao: a cidade da edicao
    # inteira. Sem filtrar por `ativo` de proposito — instituicao desativada
    # ainda pode ter crianca deste ano esperando responsavel.
    da_cidade = set(
        db.scalars(
            select(Instituicao.id).where(Instituicao.cidade_id == edicao.cidade_id)
        ).all()
    )

    time: dict[int, tuple[str, set[int], str]] = {}

    linhas = db.execute(
        select(
            Usuario.id, Usuario.nome, Perfil.nome, UsuarioInstituicao.instituicao_id
        )
        .join(UsuarioEdicao, UsuarioEdicao.usuario_id == Usuario.id)
        .join(Perfil, Perfil.id == UsuarioEdicao.perfil_id)
        .outerjoin(
            UsuarioInstituicao,
            (UsuarioInstituicao.usuario_edicao_id == UsuarioEdicao.id)
            & UsuarioInstituicao.ativo.is_(True),
        )
        .where(
            UsuarioEdicao.edicao_id == edicao_id,
            UsuarioEdicao.ativo.is_(True),
            Usuario.ativo.is_(True),
            # A conta de administracao geral entra pela consulta de baixo, com
            # a cidade inteira na mao, mesmo que tambem tenha vinculo aqui.
            Usuario.admin_geral.is_(False),
            Perfil.nome.in_((*PERFIS_COMISSARIADO, PERFIL_COORDENACAO)),
        )
        .order_by(Usuario.nome)
    ).all()

    for usuario_id, nome, papel, instituicao_id in linhas:
        # So o comissario de base e recortado por instituicao. A coordenacao
        # da captacao, como a da cidade, alcanca todas — e por isso ja nasce
        # com a cidade inteira na mao.
        _, instituicoes, _ = time.setdefault(
            usuario_id,
            (nome, set() if papel == PERFIL_COMISSARIO else set(da_cidade), papel),
        )
        if papel == PERFIL_COMISSARIO and instituicao_id is not None:
            instituicoes.add(instituicao_id)

    # A administracao geral nao tem vinculo com edicao nenhuma — e alcanca
    # todas. Por isso ela nao aparece na consulta de cima: entra aqui.
    for usuario_id, nome in db.execute(
        select(Usuario.id, Usuario.nome)
        .where(Usuario.admin_geral.is_(True), Usuario.ativo.is_(True))
        .order_by(Usuario.nome)
    ).all():
        time[usuario_id] = (nome, set(da_cidade), PAPEL_ADMIN_GERAL)

    return time


def _permissoes_da_edicao(mudancas: set[str]) -> tuple[str, ...]:
    """Quais permissoes podem autorizar esta edicao, da mais larga para a mais
    estreita.

    Mexer SO no responsavel e um poder a parte, de quem coordena a captacao:
    ela redistribui a lista entre o time sem poder criar, renomear nem apagar
    crianca. Qualquer outro campo junto, e volta a ser `editar_criancas`.

    Devolve mais de uma porque a permissao e POR EDICAO: a mesma pessoa pode
    editar tudo numa edicao e so atribuir responsavel na seguinte, e quem
    resolve isso e o filtro de alcance, tentado nesta ordem.
    """
    if mudancas <= {"comissario_id"}:
        return ("editar_criancas", "atribuir_comissario")
    return ("editar_criancas",)


def _buscar_para_editar(
    db: Session, ctx: ContextoAcesso, crianca_id: int, mudancas: set[str]
) -> Crianca:
    """A crianca, se alguma das permissoes de edicao alcancar esta edicao."""
    for permissao in _permissoes_da_edicao(mudancas):
        crianca = db.scalar(
            select(Crianca)
            .where(Crianca.id == crianca_id, ctx.filtro_criancas(permissao))
            .options(*CARREGAR)
        )
        if crianca is not None:
            return crianca
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")


def _conferir_comissario(
    db: Session,
    comissario_id: int,
    criancas: list[Crianca],
    destino: Instituicao | None = None,
) -> None:
    """O responsavel tem de alcancar a instituicao de cada crianca.

    Sem esta conferencia daria para pendurar uma crianca num comissario de
    outra cidade, ou num monitor — e o nome na coluna deixaria de significar
    "e com ele que eu falo sobre esta crianca". Coordenacao e administracao
    geral passam sempre: elas alcancam a cidade inteira.

    `destino` e para o lote que muda de escola e poe responsavel na mesma
    chamada: o que vale e a instituicao onde a crianca vai PARAR, nao a de onde
    ela esta saindo.
    """
    por_edicao: dict[int, dict[int, tuple[str, set[int]]]] = {}
    for crianca in criancas:
        instituicao = destino or crianca.instituicao

        if crianca.edicao_id not in por_edicao:
            por_edicao[crianca.edicao_id] = _time(db, crianca.edicao_id)

        membro = por_edicao[crianca.edicao_id].get(comissario_id)
        if membro is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Esta pessoa nao atende a edicao desta crianca.",
            )
        if instituicao.id not in membro[1]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"{membro[0]} nao esta no time de {instituicao.nome}. "
                "Atribua a instituicao a ele na tela de usuarios primeiro.",
            )


def _buscar(db: Session, ctx: ContextoAcesso, crianca_id: int, permissao: str) -> Crianca:
    """Busca uma crianca ja aplicando o filtro de alcance."""
    crianca = db.scalar(
        select(Crianca)
        .where(Crianca.id == crianca_id, ctx.filtro_criancas(permissao))
        .options(*CARREGAR)
    )
    if crianca is None:
        # Mesma resposta de "nao existe": nao revelar criancas fora do alcance.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")
    return crianca


@router.get("", response_model=PaginaCriancas)
def listar(
    db: BD,
    ctx: Ver,
    edicao_id: int | None = None,
    instituicao_id: int | None = None,
    dia_evento_id: int | None = None,
    comissario_id: int | None = Query(
        default=None, description="So as criancas deste comissario responsavel"
    ),
    sem_comissario: bool = Query(
        default=False, description="So as criancas que ainda nao tem responsavel"
    ),
    busca: str | None = None,
    codigo: str | None = Query(default=None, description="Busca por codigo exato"),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
):
    """Lista as criancas que este usuario alcanca.

    O parametro `codigo` e o escape combinado para o apadrinhamento entre
    cidades: busca por codigo exato alcanca qualquer instituicao das edicoes do
    usuario, mesmo fora das atribuidas a ele, e o uso fica registrado em log.
    Listagens comuns nunca escapam do filtro.
    """
    escapou = bool(codigo)

    if escapou:
        # Escape: solta a instituicao, mas nunca a edicao.
        if ctx.admin_geral:
            condicao = Crianca.id.is_not(None)
        elif ctx.edicoes_com("ver_criancas"):
            condicao = Crianca.edicao_id.in_(ctx.edicoes_com("ver_criancas"))
        else:
            condicao = Crianca.id.is_(None)
        condicao = condicao & (func.lower(Crianca.codigo) == codigo.strip().lower())
    else:
        condicao = ctx.filtro_criancas()

    if edicao_id is not None:
        condicao = condicao & (Crianca.edicao_id == edicao_id)
    if instituicao_id is not None:
        condicao = condicao & (Crianca.instituicao_id == instituicao_id)
    if dia_evento_id is not None:
        condicao = condicao & (Crianca.dia_evento_id == dia_evento_id)
    # Filtrar por responsavel e a mesma informacao que a coluna Comissario, so
    # que pela porta de tras: quem nao recebe a coluna tambem nao pergunta por
    # ela. Sem isto, bastava filtrar "sem responsavel" para descobrir quais
    # criancas ainda nao foram pegas por ninguem.
    # Sem edicao escolhida a pergunta e sobre o usuario inteiro: so passa quem
    # capta em alguma edicao. Com edicao, vale a daquela edicao — a mesma
    # pessoa pode coordenar uma e so monitorar a seguinte.
    capta = _ve_padrinho(ctx, edicao_id) if edicao_id is not None else ctx.pode("ver_padrinhos")
    if (comissario_id is not None or sem_comissario) and not capta:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Este perfil nao trabalha com comissario responsavel.",
        )
    if comissario_id is not None:
        condicao = condicao & (Crianca.comissario_id == comissario_id)
    if sem_comissario:
        condicao = condicao & Crianca.comissario_id.is_(None)

    if busca:
        termo = f"%{busca.strip()}%"
        condicao = condicao & or_(Crianca.nome.ilike(termo), Crianca.codigo.ilike(termo))

    total = db.scalar(select(func.count()).select_from(Crianca).where(condicao)) or 0

    # Conta sobre o filtro inteiro, nao sobre a pagina: a coluna de check-in so
    # existe depois que o evento comeca, e quem esta na pagina 3 tem de ver a
    # mesma planilha de quem esta na 1.
    com_checkin = (
        db.scalar(
            select(func.count())
            .select_from(Crianca)
            .where(condicao, Crianca.checkin_em.is_not(None))
        )
        or 0
    )

    itens = db.scalars(
        select(Crianca)
        .where(condicao)
        .options(*CARREGAR)
        .order_by(Crianca.codigo)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()

    if escapou:
        registrar(
            db, "busca_por_codigo", usuario_id=ctx.usuario.id,
            tabela="criancas",
            detalhes={"codigo": codigo, "encontradas": total},
        )
        db.commit()

    panorama = _panorama(db, [c.id for c in itens])

    return PaginaCriancas(
        total=total, pagina=pagina, por_pagina=por_pagina,
        com_checkin=com_checkin,
        itens=[_saida(c, ctx, panorama.get(c.id)) for c in itens],
    )


@router.get("/resumo-instituicoes", response_model=list[ResumoInstituicao])
def resumo_instituicoes(db: BD, ctx: Ver, edicao_id: int):
    """As abas da tela de criancas, com o que falta em cada instituicao.

    Numa edicao de 20 instituicoes, a coordenacao precisa saber de longe onde
    esta o atraso — nao abrir aba por aba para descobrir.
    """
    alcance = ctx.filtro_criancas("ver_criancas") & (Crianca.edicao_id == edicao_id)
    # A conta tambem e dado: "3 das 4 sem padrinho" numa instituicao pequena
    # diz quase quem sao. Quem nao alcanca a coluna nao alcanca o resumo dela.
    pode_padrinho = _ve_padrinho(ctx, edicao_id)

    # "Com padrinho" quer dizer apadrinhamento que vale: o que so foi prometido
    # e trabalho que ainda falta, e e justamente o atraso que estas abas existem
    # para mostrar.
    com_padrinho = (
        select(Apadrinhamento.crianca_id)
        .where(Apadrinhamento.crianca_id == Crianca.id, CONFIRMADO)
        .exists()
    )
    com_cartao = (
        select(Cartao.crianca_id).where(Cartao.crianca_id == Crianca.id).exists()
    )

    linhas = db.execute(
        select(
            Crianca.instituicao_id,
            Instituicao.nome,
            func.count(Crianca.id),
            func.count(case((~com_padrinho, Crianca.id))),
            func.count(case((~com_cartao, Crianca.id))),
            func.count(case((Crianca.comissario_id.is_(None), Crianca.id))),
        )
        .join(Instituicao, Instituicao.id == Crianca.instituicao_id)
        .where(alcance)
        .group_by(Crianca.instituicao_id, Instituicao.nome)
        .order_by(Instituicao.nome)
    ).all()

    # O dia e da instituicao: uma consulta para todas, em vez de uma por aba.
    dias_marcados = {
        instituicao_id: (dia_id, data, descricao)
        for instituicao_id, dia_id, data, descricao in db.execute(
            select(
                InstituicaoDia.instituicao_id,
                InstituicaoDia.dia_evento_id,
                DiaEvento.data,
                DiaEvento.descricao,
            )
            .join(DiaEvento, DiaEvento.id == InstituicaoDia.dia_evento_id)
            .where(InstituicaoDia.edicao_id == edicao_id)
        ).all()
    }

    return [
        ResumoInstituicao(
            instituicao_id=i, instituicao=nome, criancas=total,
            sem_padrinho=sp if pode_padrinho else None,
            sem_cartao=sc,
            sem_comissario=scom if pode_padrinho else None,
            dia_evento_id=dias_marcados.get(i, (None, None, None))[0],
            dia_evento=dias_marcados.get(i, (None, None, None))[1],
            dia_evento_descricao=dias_marcados.get(i, (None, None, None))[2],
        )
        for i, nome, total, sp, sc, scom in linhas
    ]


@router.get("/comissarios", response_model=list[ComissarioDoTime])
def comissarios_da_edicao(db: BD, ctx: Ver, edicao_id: int):
    """Quem pode responder por uma crianca da edicao, com o alcance de cada um.

    Alimenta o seletor de responsavel na planilha. Sai nome e papel, e mais
    nada: e a lista de quem trabalha na edicao, nao a ficha de ninguem.

    Os comissarios vem primeiro porque sao a escolha do dia a dia; coordenacao
    e administracao geral ficam no fim da lista, onde nao atrapalham quem esta
    distribuindo mil criancas pelo time.

    Pede `ver_padrinhos`, e nao so `ver_criancas`: quem e o responsavel por uma
    crianca e assunto da captacao, e a monitoria e a estrutura nao recebem essa
    coluna nem este seletor. A tela trata a recusa calada — o filtro de
    responsavel simplesmente nao aparece.
    """
    if not _ve_padrinho(ctx, edicao_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Este perfil nao trabalha com comissario responsavel.",
        )
    if not ctx.alcanca_edicao(edicao_id, "ver_criancas"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    membros = [
        ComissarioDoTime(
            id=i, nome=nome, papel=papel, instituicoes=sorted(instituicoes)
        )
        for i, (nome, instituicoes, papel) in _time(db, edicao_id).items()
    ]
    return sorted(membros, key=lambda m: (m.papel != PERFIL_COMISSARIO, m.nome))


@router.post("/lote", response_model=list[CriancaOut])
def editar_em_lote(dados: CriancasEmLote, db: BD, ctx: EditarOuAtribuir):
    """Muda varias criancas de uma vez.

    Distribuir 1500 criancas pelos dias do evento uma a uma nao e trabalho que
    alguem faca — por isso o lote.
    """
    # O lote tambem muda de poder conforme o que mexe: so o responsavel e
    # trabalho de quem coordena a captacao; qualquer outro campo junto volta a
    # pedir `editar_criancas`. Mesma regra do PATCH de uma crianca so.
    mexidos = set(dados.model_dump(exclude_unset=True)) - {"criancas"}
    criancas: list[Crianca] = []
    for permissao in _permissoes_da_edicao(mexidos):
        criancas = list(
            db.scalars(
                select(Crianca)
                .where(Crianca.id.in_(dados.criancas), ctx.filtro_criancas(permissao))
                .options(*CARREGAR)
            ).all()
        )
        if len(criancas) == len(set(dados.criancas)):
            break

    if len(criancas) != len(set(dados.criancas)):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Ha criancas que voce nao alcanca ou que nao existem."
        )

    if dados.instituicao_id is not None:
        instituicao = db.get(Instituicao, dados.instituicao_id)
        if instituicao is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Instituicao nao encontrada.")
        for c in criancas:
            if not ctx.alcanca_instituicao(c.edicao_id, dados.instituicao_id):
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "Esta instituicao nao esta sob sua responsabilidade.",
                )

    # Mandar comissario_id: null limpa o responsavel; nao mandar o campo nao
    # o toca. So model_fields_set separa os dois casos.
    mexe_no_comissario = "comissario_id" in dados.model_fields_set
    if mexe_no_comissario and dados.comissario_id is not None:
        _conferir_comissario(
            db, dados.comissario_id, list(criancas),
            destino=instituicao if dados.instituicao_id is not None else None,
        )

    mudou = []
    for crianca in criancas:
        if dados.instituicao_id is not None:
            crianca.instituicao_id = dados.instituicao_id
            # Mudou de escola: o dia passa a ser o da escola nova.
            crianca.dia_evento_id = dias.dia_da_instituicao(
                db, crianca.edicao_id, dados.instituicao_id
            )
            mudou.append("instituicao_id")

            # E o responsavel cai, se ele nao for do time da escola nova: um
            # nome na coluna que nem alcanca a crianca e pior que nome nenhum.
            if not mexe_no_comissario and crianca.comissario_id is not None:
                membro = _time(db, crianca.edicao_id).get(crianca.comissario_id)
                if membro is None or dados.instituicao_id not in membro[1]:
                    crianca.comissario_id = None
                    mudou.append("comissario_id")

        if mexe_no_comissario:
            crianca.comissario_id = dados.comissario_id
            mudou.append("comissario_id")

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Mudar de instituicao esbarrou num codigo que ja existe la.",
        )

    registrar(
        db, "criancas_em_lote", usuario_id=ctx.usuario.id,
        tabela="criancas",
        detalhes={"quantas": len(criancas), "campos": sorted(set(mudou))},
    )
    db.commit()

    atualizadas = db.scalars(
        select(Crianca)
        .where(Crianca.id.in_([c.id for c in criancas]))
        .options(*CARREGAR)
        .order_by(Crianca.nome)
    ).all()
    panorama = _panorama(db, [c.id for c in atualizadas])
    return [_saida(c, ctx, panorama.get(c.id)) for c in atualizadas]


@router.post("/renumerar", response_model=list[CriancaOut])
def renumerar(dados: RenumerarIn, db: BD, ctx: Editar):
    """Refaz os codigos de uma instituicao, na ordem do projeto.

    Serve para listas que entraram antes da regra existir, ou depois de
    corrigir idades e sexos que vieram errados da planilha.

    Atencao: os codigos MUDAM. Crachas ja impressos e listas ja distribuidas
    ficam desatualizados.
    """
    if not ctx.alcanca_edicao(dados.edicao_id, "editar_criancas"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Voce nao edita esta edicao.")
    if not ctx.alcanca_instituicao(dados.edicao_id, dados.instituicao_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Esta instituicao nao esta sob sua responsabilidade."
        )

    instituicao = db.get(Instituicao, dados.instituicao_id)
    if instituicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instituicao nao encontrada.")

    sigla = dados.sigla.strip().upper() if dados.sigla else instituicao.sigla
    if not sigla:
        usadas = set(
            db.scalars(
                select(Instituicao.sigla).where(
                    Instituicao.cidade_id == instituicao.cidade_id,
                    Instituicao.sigla.is_not(None),
                )
            ).all()
        )
        sigla = codigos.sugerir_sigla(instituicao.nome, usadas)

    criancas = db.scalars(
        select(Crianca)
        .where(
            Crianca.edicao_id == dados.edicao_id,
            Crianca.instituicao_id == dados.instituicao_id,
        )
        .options(*CARREGAR)
    ).all()

    if not criancas:
        return []

    # Codigo temporario primeiro: sem isto, atribuir ES00 a quem hoje e ES05
    # esbarraria na restricao de unicidade no meio do caminho.
    for i, crianca in enumerate(criancas):
        crianca.codigo = f"~{i}"
    db.flush()

    for crianca, codigo in codigos.gerar_codigos(criancas, sigla):
        crianca.codigo = codigo

    instituicao.sigla = sigla

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta sigla ja esta em uso por outra instituicao da cidade.",
        )

    registrar(
        db, "criancas_renumeradas", usuario_id=ctx.usuario.id,
        tabela="criancas",
        detalhes={
            "edicao_id": dados.edicao_id,
            "instituicao_id": dados.instituicao_id,
            "sigla": sigla,
            "quantas": len(criancas),
        },
    )
    db.commit()

    atualizadas = db.scalars(
        select(Crianca)
        .where(
            Crianca.edicao_id == dados.edicao_id,
            Crianca.instituicao_id == dados.instituicao_id,
        )
        .options(*CARREGAR)
        .order_by(Crianca.codigo)
    ).all()
    panorama = _panorama(db, [c.id for c in atualizadas])
    return [_saida(c, ctx, panorama.get(c.id)) for c in atualizadas]


@router.get("/{crianca_id}", response_model=CriancaDetalhe)
def detalhe(crianca_id: int, db: BD, ctx: Ver):
    """Ficha da crianca: apadrinhamento, cartoes e kit numa consulta so."""
    crianca = db.scalar(
        select(Crianca)
        .where(Crianca.id == crianca_id, ctx.filtro_criancas("ver_criancas"))
        .options(*CARREGAR, joinedload(Crianca.edicao))
    )
    if crianca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")

    # Padrinho e dado de quem doa, nao da crianca. Quem nao capta nao recebe
    # nada dessa parte — nem os nomes, nem os valores, nem quantos sao: a conta
    # sozinha ja entrega o que a lista esconde ("1 de 2") e, numa crianca so,
    # entrega tudo. A tela poe no lugar uma linha dizendo de quem e esse pedaco.
    pode_contato = _ve_padrinho(ctx, crianca.edicao_id)
    pode_kit = _ve_kit(ctx, crianca.edicao_id)

    apadrinhamentos = db.execute(
        select(Apadrinhamento, Padrinho)
        .join(Padrinho, Padrinho.id == Apadrinhamento.padrinho_id)
        .where(Apadrinhamento.crianca_id == crianca.id)
        .order_by(Apadrinhamento.tipo)
    ).all()

    padrinhos = [] if not pode_contato else [
        PadrinhoDaCrianca(
            apadrinhamento_id=a.id,
            tipo=a.tipo,
            valor=a.valor,
            pago=confirmado(a),
            padrinho_id=p.id,
            nome=p.nome,
            whatsapp=p.whatsapp,
            email=p.email,
        )
        for a, p in apadrinhamentos
    ]

    cartoes = db.scalars(
        select(Cartao).where(Cartao.crianca_id == crianca.id).order_by(Cartao.tipo)
    ).all()

    kit = db.scalar(select(Kit).where(Kit.crianca_id == crianca.id))

    return CriancaDetalhe(
        id=crianca.id,
        edicao_id=crianca.edicao_id,
        edicao=crianca.edicao.nome,
        instituicao_id=crianca.instituicao_id,
        instituicao=crianca.instituicao.nome,
        codigo=crianca.codigo,
        nome=crianca.nome,
        idade=crianca.idade,
        sexo=crianca.sexo,
        dia_evento=crianca.dia_evento.data if crianca.dia_evento else None,
        dia_evento_descricao=crianca.dia_evento.descricao if crianca.dia_evento else None,
        observacoes=crianca.observacoes,
        checkin_em=crianca.checkin_em,
        desistiu_em=crianca.desistiu_em,
        comissario_id=crianca.comissario_id if pode_contato else None,
        comissario=(
            (crianca.comissario.nome if crianca.comissario else None) if pode_contato else None
        ),
        comissario_grupo=_grupo_do_comissario(crianca) if pode_contato else None,
        padrinhos=padrinhos,
        cartoes=[
            CartaoDaCrianca(
                id=c.id, tipo=c.tipo, status=c.status,
                criado_em=c.criado_em, enviado_em=c.enviado_em,
            )
            for c in cartoes
        ],
        kit_status=(kit.status if kit else "pendente") if pode_kit else None,
        kit_montado_em=(kit.montado_em if kit else None) if pode_kit else None,
        ve_captacao=pode_contato,
    )


@router.post("", response_model=CriancaOut, status_code=status.HTTP_201_CREATED)
def criar(dados: CriancaIn, db: BD, ctx: Editar):
    if not ctx.alcanca_edicao(dados.edicao_id, "editar_criancas"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Voce nao edita esta edicao.")
    if not ctx.alcanca_instituicao(dados.edicao_id, dados.instituicao_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Esta instituicao nao esta sob sua responsabilidade."
        )

    crianca = Crianca(**dados.model_dump())
    crianca.nome = nome_proprio(crianca.nome)
    # O dia vem da instituicao, nunca do formulario.
    crianca.dia_evento_id = dias.dia_da_instituicao(
        db, dados.edicao_id, dados.instituicao_id
    )
    db.add(crianca)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ja existe uma crianca com este codigo nesta instituicao e edicao.",
        )

    registrar(
        db, "crianca_criada", usuario_id=ctx.usuario.id,
        tabela="criancas", registro_id=crianca.id,
        detalhes={"codigo": crianca.codigo, "edicao_id": crianca.edicao_id},
    )
    db.commit()
    return _saida(_buscar(db, ctx, crianca.id, "editar_criancas"), ctx)


@router.patch("/{crianca_id}", response_model=CriancaOut)
def editar(crianca_id: int, dados: CriancaEditar, db: BD, ctx: EditarOuAtribuir):
    # A mudanca e lida ANTES de buscar: e ela que diz qual permissao esta
    # sendo exercida, e portanto qual alcance vale.
    mudancas = dados.model_dump(exclude_unset=True)
    crianca = _buscar_para_editar(db, ctx, crianca_id, set(mudancas))

    # O responsavel passa pela conferencia do time antes de entrar.
    if mudancas.get("comissario_id") is not None:
        _conferir_comissario(db, mudancas["comissario_id"], [crianca])

    for campo, valor in mudancas.items():
        setattr(crianca, campo, nome_proprio(valor) if campo == "nome" and valor else valor)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ja existe uma crianca com este codigo aqui."
        )

    registrar(
        db, "crianca_editada", usuario_id=ctx.usuario.id,
        tabela="criancas", registro_id=crianca.id,
        detalhes={"campos": sorted(mudancas)},
    )
    db.commit()
    return _saida(_buscar_para_editar(db, ctx, crianca_id, set(mudancas)), ctx)


@router.patch("/{crianca_id}/desistencia", response_model=CriancaOut)
def desistencia(crianca_id: int, dados: DesistenciaIn, db: BD, ctx: Editar):
    """Marca (ou desmarca) que a crianca desistiu de ir ao evento.

    Nao apaga nada: o kit, os cartoes e o apadrinhamento dela continuam onde
    estavam. E so uma marca, para a planilha mostrar riscado quem nao vai mais
    sem perder o nome de vista. Desmarcar devolve tudo como era.
    """
    crianca = _buscar(db, ctx, crianca_id, "editar_criancas")

    ja_estava = crianca.desistiu_em is not None
    if dados.desistiu and not ja_estava:
        crianca.desistiu_em = datetime.now(UTC)
        crianca.desistiu_por = ctx.usuario.id
    elif not dados.desistiu:
        crianca.desistiu_em = None
        crianca.desistiu_por = None

    if dados.desistiu != ja_estava:
        registrar(
            db,
            "crianca_desistiu" if dados.desistiu else "crianca_voltou",
            usuario_id=ctx.usuario.id,
            tabela="criancas",
            registro_id=crianca.id,
            detalhes={"codigo": crianca.codigo, "nome": crianca.nome},
        )
    db.commit()

    panorama = _panorama(db, [crianca.id])
    return _saida(
        _buscar(db, ctx, crianca_id, "editar_criancas"), ctx, panorama.get(crianca.id)
    )


@router.get("/{crianca_id}/dependencias", response_model=DependenciasOut)
def dependencias(crianca_id: int, db: BD, ctx: Editar):
    """O que seria apagado junto com a crianca. A tela pergunta isto antes.

    Apagar uma crianca nao e apagar uma linha: vao junto o cartao que ela
    escreveu, o kit ja montado e o apadrinhamento de quem se ofereceu para
    ela. Quem clica precisa ver essa lista antes de decidir.
    """
    crianca = _buscar(db, ctx, crianca_id, "editar_criancas")
    return exclusao.resumir(
        db, crianca.id, crianca.nome, exclusao.alcance_da_crianca(crianca.id)
    )


@router.delete("/{crianca_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(crianca_id: int, db: BD, ctx: Editar):
    crianca = _buscar(db, ctx, crianca_id, "editar_criancas")

    registrar(
        db, "crianca_apagada", usuario_id=ctx.usuario.id,
        tabela="criancas", registro_id=crianca.id,
        detalhes={"nome": crianca.nome, "codigo": crianca.codigo},
    )
    db.delete(crianca)
    db.commit()


# ---------------------------------------------------------------- importacao

def _numerar(db: Session, linhas: list, edicao_id: int) -> None:
    """Preenche o codigo das linhas que vieram sem ele.

    Cada instituicao numera a propria sequencia, continuando de onde a ultima
    importacao parou — duas listas da mesma escola nao colidem.
    """
    por_instituicao: dict[int, list] = defaultdict(list)
    for linha in linhas:
        if linha.instituicao_id is not None and not linha.codigo:
            por_instituicao[linha.instituicao_id].append(linha)

    for instituicao_id, do_grupo in por_instituicao.items():
        instituicao = db.get(Instituicao, instituicao_id)
        sigla = instituicao.sigla
        if not sigla:
            # Instituicao cadastrada antes da sigla existir: monta agora.
            usadas = set(
                db.scalars(
                    select(Instituicao.sigla).where(
                        Instituicao.cidade_id == instituicao.cidade_id,
                        Instituicao.sigla.is_not(None),
                    )
                ).all()
            )
            sigla = codigos.sugerir_sigla(instituicao.nome, usadas)
            instituicao.sigla = sigla
            db.flush()

        ja_usados = list(
            db.scalars(
                select(Crianca.codigo).where(
                    Crianca.edicao_id == edicao_id,
                    Crianca.instituicao_id == instituicao_id,
                )
            ).all()
        )
        inicio = codigos.proximo_numero(ja_usados, sigla)

        for linha, codigo in codigos.gerar_codigos(do_grupo, sigla, inicio):
            linha.codigo = codigo


@router.post("/importar", response_model=PreviaImportacao)
async def importar_previa(
    db: BD,
    ctx: Importar,
    arquivo: UploadFile = File(...),
    edicao_id: int = Form(...),
    instituicao_id: int | None = Form(default=None),
):
    """Le a planilha e devolve a previa. Nao grava nada ainda."""
    if not ctx.alcanca_edicao(edicao_id, "importar_listas"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Voce nao importa nesta edicao.")

    edicao = db.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    conteudo = await ler_limitado(arquivo)

    try:
        leitura = importador.ler_planilha(conteudo, arquivo.filename or "lista.xlsx")
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    if not leitura.linhas:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "A planilha nao tem nenhuma linha."
        )

    instituicoes = {
        i.id: i.nome
        for i in db.scalars(
            select(Instituicao).where(Instituicao.cidade_id == edicao.cidade_id)
        ).all()
    }

    importador.casar_instituicoes(leitura.linhas, instituicoes, instituicao_id)

    # Planilha sem coluna de codigo: a aplicacao numera, na ordem do projeto —
    # meninas primeiro, depois idade, depois ordem alfabetica.
    if "codigo" not in leitura.colunas_encontradas:
        _numerar(db, leitura.linhas, edicao_id)

    importador.marcar_repetidas_no_arquivo(leitura.linhas)

    ja_cadastrados = {
        f"{inst}|{cod.lower()}"
        for inst, cod in db.execute(
            select(Crianca.instituicao_id, Crianca.codigo).where(Crianca.edicao_id == edicao_id)
        ).all()
    }
    importador.marcar_ja_cadastradas(leitura.linhas, ja_cadastrados)

    nomes = list(
        db.scalars(select(Crianca.nome).where(Crianca.edicao_id == edicao_id)).all()
    )
    importador.marcar_nomes_parecidos(leitura.linhas, nomes)

    # Guarda a leitura para a confirmacao nao depender de reenviar o arquivo.
    PASTA_IMPORTACOES.mkdir(parents=True, exist_ok=True)
    id_previa = uuid.uuid4().hex
    (PASTA_IMPORTACOES / f"{id_previa}.json").write_text(
        json.dumps(
            {
                "edicao_id": edicao_id,
                "usuario_id": ctx.usuario.id,
                "linhas": [
                    {
                        "codigo": l.codigo, "nome": l.nome, "idade": l.idade,
                        "sexo": l.sexo, "instituicao_id": l.instituicao_id,
                        "observacoes": l.observacoes, "valida": l.valida,
                    }
                    for l in leitura.linhas
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    registrar(
        db, "importacao_analisada", usuario_id=ctx.usuario.id,
        tabela="criancas",
        detalhes={
            "edicao_id": edicao_id,
            "arquivo": arquivo.filename,
            "linhas": len(leitura.linhas),
            "validas": len(leitura.validas),
        },
    )
    db.commit()

    return PreviaImportacao(
        id=id_previa,
        total=len(leitura.linhas),
        validas=len(leitura.validas),
        com_erro=sum(1 for l in leitura.linhas if l.erros),
        com_aviso=sum(1 for l in leitura.linhas if l.avisos and not l.erros),
        colunas_reconhecidas=leitura.colunas_encontradas,
        colunas_ignoradas=leitura.colunas_ignoradas,
        linhas=[
            LinhaImportada(
                linha=l.linha, codigo=l.codigo, nome=l.nome, idade=l.idade, sexo=l.sexo,
                instituicao_id=l.instituicao_id,
                instituicao=instituicoes.get(l.instituicao_id),
                observacoes=l.observacoes, erros=l.erros, avisos=l.avisos, valida=l.valida,
            )
            for l in leitura.linhas
        ],
    )


@router.post("/importar/{id_previa}/confirmar", response_model=ResultadoImportacao)
def importar_confirmar(id_previa: str, db: BD, ctx: Importar):
    """Grava as linhas validas da previa."""
    if not id_previa.isalnum():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Identificador invalido.")

    caminho = PASTA_IMPORTACOES / f"{id_previa}.json"
    if not caminho.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Analise nao encontrada. Envie a planilha de novo."
        )

    guardado = json.loads(caminho.read_text(encoding="utf-8"))

    if guardado["usuario_id"] != ctx.usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta analise e de outro usuario.")
    if not ctx.alcanca_edicao(guardado["edicao_id"], "importar_listas"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Voce nao importa nesta edicao.")

    importadas = 0
    for linha in guardado["linhas"]:
        if not linha["valida"]:
            continue
        db.add(
            Crianca(
                edicao_id=guardado["edicao_id"],
                instituicao_id=linha["instituicao_id"],
                codigo=linha["codigo"],
                nome=linha["nome"],
                # Planilhas sem idade ou sexo ficam com o padrao, para a
                # coordenacao completar depois na tela.
                idade=linha["idade"] if linha["idade"] is not None else 0,
                sexo=linha["sexo"] or "F",
                observacoes=linha["observacoes"],
            )
        )
        importadas += 1

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Alguma crianca desta lista ja foi cadastrada enquanto voce conferia. "
            "Envie a planilha de novo.",
        )

    # As que acabaram de entrar herdam o dia que a instituicao ja tinha.
    dias.aplicar_a_novas(
        db,
        guardado["edicao_id"],
        {l["instituicao_id"] for l in guardado["linhas"] if l["valida"] and l["instituicao_id"]},
    )

    registrar(
        db, "importacao_confirmada", usuario_id=ctx.usuario.id,
        tabela="criancas",
        detalhes={"edicao_id": guardado["edicao_id"], "importadas": importadas},
    )
    db.commit()
    caminho.unlink(missing_ok=True)

    return ResultadoImportacao(
        importadas=importadas, ignoradas=len(guardado["linhas"]) - importadas
    )
