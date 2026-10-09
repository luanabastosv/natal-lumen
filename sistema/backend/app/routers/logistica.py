"""Kits e check-in das criancas no dia do evento.

As compras sairam daqui: viraram as SAIDAS do financeiro, em
routers/financeiro.py, ao lado dos recebimentos da edicao.
"""

import io
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Annotated

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, joinedload

from app.config import config
from app.database import get_db
from app.models import (
    Apadrinhamento,
    Autorizacao,
    Cartao,
    Crianca,
    DiaEvento,
    Instituicao,
    InstituicaoDia,
    Kit,
)
from app.models.tipos import StatusKit
from app.schemas.logistica import (
    CheckinAberto,
    CheckinDesfazer,
    CheckinIn,
    CheckinLinha,
    CheckinOut,
    DiaCheckin,
    InstituicaoKits,
    KitConferir,
    KitMudar,
    MontagemIn,
    MontagemOut,
    KitOut,
    PaginaKits,
    PerfilKits,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos import cuidados
from app.servicos.log import registrar
from app.servicos.oracao import FUSO

router = APIRouter(tags=["logistica"])

BD = Annotated[Session, Depends(get_db)]
Kits = Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_kits"))]
Checkin = Annotated[ContextoAcesso, Depends(exige_permissao("fazer_checkin"))]


# ---------------------------------------------------------------- kits

def _saida_kit(crianca: Crianca, kit: Kit | None) -> dict:
    """Uma linha de kit. Existe para a lista e o lote nunca divergirem.

    Sem ela, a linha devolvida depois de marcar montado tinha menos campos que a
    linha da lista, e a tela ficava com metade dos dados em branco ate a proxima
    busca.
    """
    return {
        "id": kit.id if kit else None,
        "crianca_id": crianca.id,
        "crianca_codigo": crianca.codigo,
        "crianca_nome": crianca.nome,
        "idade": crianca.idade,
        "sexo": crianca.sexo,
        "instituicao_id": crianca.instituicao_id,
        "instituicao": crianca.instituicao.nome,
        "dia_evento": crianca.dia_evento.data if crianca.dia_evento else None,
        "dia_evento_descricao": crianca.dia_evento.descricao if crianca.dia_evento else None,
        "status": kit.status if kit else StatusKit.PENDENTE.value,
        "montado_em": kit.montado_em if kit else None,
        # O nome escrito na montagem da instituicao; sem ele, o de quem marcou
        # no sistema (kits marcados antes da "Montagem + Conferencia").
        "montado_por": (kit.montado_por_nome or (kit.montador.nome if kit.montador else None))
        if kit
        else None,
        "conferido_em": kit.conferido_em if kit else None,
        "conferido_por": (
            kit.conferido_por_nome or (kit.conferente.nome if kit.conferente else None)
        )
        if kit
        else None,
        "desistiu_em": crianca.desistiu_em,
        "checkin_em": crianca.checkin_em,
        "falta_em": crianca.falta_em,
        "observacoes": kit.observacoes if kit else None,
    }


@router.get("/kits", response_model=PaginaKits)
def listar_kits(
    db: BD,
    ctx: Kits,
    edicao_id: int | None = None,
    dia_evento_id: int | None = None,
    # A tela e por abas de instituicao, como a de criancas: a equipe monta uma
    # escola de cada vez, e a caixa de cada uma sai junta.
    instituicao_id: int | None = None,
    situacao: str | None = Query(default=None, pattern="^(pendente|montado)$"),
    # A ordem e do SERVIDOR, e nao do navegador: ordenar so o que ja veio
    # ordenaria a pagina, e nao a lista — numa edicao de mil criancas, clicar em
    # "idade" mostraria as mais novas das cem primeiras, que nao e o que a
    # pergunta quer dizer.
    ordenar_por: str = Query(default="codigo", pattern="^(codigo|nome|idade|sexo|instituicao|montado)$"),
    ordem: str = Query(default="asc", pattern="^(asc|desc)$"),
    pagina: int = Query(default=1, ge=1),
    # O teto alto existe para a IMPRESSAO: o papel sai com a lista inteira do
    # filtro, e uma edicao grande passa de mil criancas. Na tela a pagina
    # continua sendo de 100.
    por_pagina: int = Query(default=100, ge=1, le=2000),
):
    """Lista as criancas com o estado do kit de cada uma.

    Parte das criancas, e nao dos kits: a crianca existe desde a importacao, e o
    kit so ganha registro quando alguem mexe nele. Sem isso a equipe de
    estrutura nao veria quem ainda falta.
    """
    condicao = ctx.filtro_criancas("gerenciar_kits")
    if edicao_id is not None:
        condicao = condicao & (Crianca.edicao_id == edicao_id)
    if dia_evento_id is not None:
        condicao = condicao & (Crianca.dia_evento_id == dia_evento_id)
    if instituicao_id is not None:
        condicao = condicao & (Crianca.instituicao_id == instituicao_id)

    consulta = (
        select(Crianca, Kit)
        .outerjoin(Kit, Kit.crianca_id == Crianca.id)
        .where(condicao)
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
    )

    # Kit sem registro conta como pendente, entao a ordem por "montado" tem de
    # tratar o nulo como pendente — senao as criancas que ninguem tocou cairiam
    # todas no fim, longe das outras pendentes, que e justamente o grupo que a
    # equipe quer junto.
    chaves = {
        "codigo": Crianca.codigo,
        "nome": Crianca.nome,
        "idade": Crianca.idade,
        "sexo": Crianca.sexo,
        "instituicao": Instituicao.nome,
        "montado": func.coalesce(Kit.status, StatusKit.PENDENTE.value),
    }
    chave = chaves[ordenar_por]
    if ordenar_por == "instituicao":
        consulta = consulta.join(Instituicao, Instituicao.id == Crianca.instituicao_id)

    # O codigo e o desempate de todas as ordens: sem ele, duas criancas de mesma
    # idade trocam de lugar entre uma busca e outra, e quem esta conferindo a
    # lista de papel contra a tela perde a linha.
    consulta = consulta.order_by(
        chave.desc() if ordem == "desc" else chave.asc(), Crianca.codigo.asc()
    )

    if situacao == StatusKit.PENDENTE.value:
        # Sem registro de kit tambem conta como pendente.
        consulta = consulta.where((Kit.id.is_(None)) | (Kit.status == situacao))
    elif situacao is not None:
        consulta = consulta.where(Kit.status == situacao)

    linhas = db.execute(consulta.order_by(Crianca.nome)).unique().all()

    resumo: dict[str, int] = defaultdict(int)
    for crianca, kit in linhas:
        estado = kit.status if kit else StatusKit.PENDENTE.value
        # A desistente continua na lista (riscada), mas nao e caixa a montar:
        # conta-la em "a montar" deixava a pilha maior do que o trabalho.
        if estado == StatusKit.PENDENTE.value and crianca.desistiu_em is not None:
            continue
        resumo[estado] += 1

    inicio = (pagina - 1) * por_pagina
    pagina_atual = linhas[inicio : inicio + por_pagina]

    return PaginaKits(
        total=len(linhas),
        pagina=pagina,
        por_pagina=por_pagina,
        resumo=dict(resumo),
        itens=[
            KitOut(
                **_saida_kit(crianca, kit))
            for crianca, kit in pagina_atual
        ],
    )


@router.get("/kits/instituicoes", response_model=list[InstituicaoKits])
def instituicoes_dos_kits(db: BD, ctx: Kits, edicao_id: int):
    """As abas da tela de kits: uma por instituicao, com as confirmadas e o dia.

    Passa pelo mesmo filtro da lista, entao quem alcanca so algumas escolas ve
    so as abas delas.

    Conta a instituicao que tem crianca na edicao, mesmo com zero kits montados:
    e justamente a escola em que nada comecou que a equipe precisa achar.
    """
    alcance = ctx.filtro_criancas("gerenciar_kits") & (Crianca.edicao_id == edicao_id)

    linhas = db.execute(
        select(
            Instituicao.id,
            Instituicao.nome,
            Instituicao.sigla,
            func.count(Crianca.id).label("total"),
            func.count(case((Kit.status == StatusKit.MONTADO.value, 1))).label("montados"),
            func.count(case((Crianca.desistiu_em.is_not(None), 1))).label("desistentes"),
            DiaEvento.data.label("dia_evento"),
            DiaEvento.descricao.label("dia_evento_descricao"),
        )
        .select_from(Crianca)
        .join(Instituicao, Instituicao.id == Crianca.instituicao_id)
        .outerjoin(Kit, Kit.crianca_id == Crianca.id)
        # O dia e da instituicao na edicao (instituicao_dia), e nao o de cada
        # crianca: e ele que diz para quando a pilha da escola tem de estar pronta.
        .outerjoin(
            InstituicaoDia,
            (InstituicaoDia.instituicao_id == Instituicao.id)
            & (InstituicaoDia.edicao_id == edicao_id),
        )
        .outerjoin(DiaEvento, DiaEvento.id == InstituicaoDia.dia_evento_id)
        .where(alcance)
        .group_by(
            Instituicao.id,
            Instituicao.nome,
            Instituicao.sigla,
            DiaEvento.data,
            DiaEvento.descricao,
        )
        .order_by(Instituicao.nome)
    ).all()

    return [
        InstituicaoKits(
            instituicao_id=l.id,
            instituicao=l.nome,
            sigla=l.sigla,
            total=l.total,
            montados=l.montados,
            desistentes=l.desistentes,
            dia_evento=l.dia_evento,
            dia_evento_descricao=l.dia_evento_descricao,
        )
        for l in linhas
    ]


@router.get("/kits/perfil", response_model=list[PerfilKits])
def perfil_dos_kits(db: BD, ctx: Kits, edicao_id: int):
    """Quantas criancas de cada idade e sexo ha em cada instituicao.

    E por idade e sexo que se compra o presente, entao a equipe precisa da
    conta pronta ("3 meninas de 4 anos"), e nao de contar linha por linha.

    A desistente fica de fora: a caixa dela nao se monta, e o presente dela
    nao se compra. Passa pelo mesmo filtro da lista e das abas.
    """
    alcance = (
        ctx.filtro_criancas("gerenciar_kits")
        & (Crianca.edicao_id == edicao_id)
        & Crianca.desistiu_em.is_(None)
    )

    linhas = db.execute(
        select(
            Instituicao.id,
            Instituicao.nome,
            Crianca.idade,
            Crianca.sexo,
            func.count(Crianca.id).label("quantidade"),
        )
        .select_from(Crianca)
        .join(Instituicao, Instituicao.id == Crianca.instituicao_id)
        .where(alcance)
        .group_by(Instituicao.id, Instituicao.nome, Crianca.idade, Crianca.sexo)
        .order_by(Instituicao.nome, Crianca.idade, Crianca.sexo)
    ).all()

    return [
        PerfilKits(
            instituicao_id=l.id,
            instituicao=l.nome,
            idade=l.idade,
            sexo=l.sexo,
            quantidade=l.quantidade,
        )
        for l in linhas
    ]


@router.post("/kits", response_model=list[KitOut])
def mudar_kits(dados: KitMudar, db: BD, ctx: Kits):
    """Muda o estado do kit de varias criancas de uma vez.

    A equipe monta os kits em lote, entao mudar um a um seria lento demais.
    """
    criancas = db.scalars(
        select(Crianca)
        .where(Crianca.id.in_(dados.criancas), ctx.filtro_criancas("gerenciar_kits"))
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
    ).all()

    if len(criancas) != len(set(dados.criancas)):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Ha criancas que voce nao alcanca ou que nao existem."
        )

    # Kit de desistente nao se mexe: a caixa dela nao se monta, e a tela ja
    # trava o checkbox. A regra mora aqui para valer tambem fora da tela.
    desistentes = [c.codigo for c in criancas if c.desistiu_em is not None]
    if desistentes:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Crianca desistente nao tem kit para marcar: {', '.join(desistentes)}.",
        )

    agora = datetime.now(UTC)
    saida = []

    for crianca in criancas:
        # "Procura, e se nao houver cria" e uma corrida quando duas pessoas
        # marcam a MESMA crianca ao mesmo tempo: as duas veem que nao ha kit, as
        # duas inserem, e a segunda esbarra na unicidade de crianca_id — erro
        # 500 na cara de quem so clicou numa caixinha. Ninguem percebia com uma
        # pessoa por vez; com a equipe de estrutura marcando em paralelo na
        # semana do evento, percebe.
        #
        # O INSERT ... ON CONFLICT resolve no banco, que e o unico lugar que
        # enxerga as duas transacoes: quem chega depois nao quebra, apenas nao
        # insere. O status vai no proprio INSERT para a linha ja nascer certa se
        # for esta a insercao que vencer.
        db.execute(
            pg_insert(Kit)
            .values(crianca_id=crianca.id, status=dados.status)
            .on_conflict_do_nothing(index_elements=["crianca_id"])
        )
        kit = db.scalar(select(Kit).where(Kit.crianca_id == crianca.id))

        kit.status = dados.status
        if dados.observacoes is not None:
            kit.observacoes = dados.observacoes

        if dados.status == StatusKit.MONTADO.value:
            kit.montado_em = agora
            kit.montado_por = ctx.usuario.id
        else:
            # Desmarcar limpa a data, senao ficaria hora de montagem num kit que
            # voltou para a fila. E a conferencia vai junto: ela era da caixa
            # que foi desfeita, e a remontada precisa ser conferida de novo.
            kit.montado_em = None
            kit.montado_por = None
            kit.montado_por_nome = None
            kit.conferido_em = None
            kit.conferido_por = None
            kit.conferido_por_nome = None

        db.flush()
        # Recarrega para o nome de quem montou vir certo: trocar o id nao
        # atualiza sozinho o `montador` ja carregado.
        db.refresh(kit)
        saida.append(KitOut(**_saida_kit(crianca, kit)))

    registrar(
        db, "kits_atualizados", usuario_id=ctx.usuario.id,
        tabela="kits",
        detalhes={"status": dados.status, "criancas": [c.id for c in criancas]},
    )
    db.commit()
    return saida


@router.post("/kits/{crianca_id}/conferir", response_model=KitOut)
def conferir_kit(crianca_id: int, db: BD, ctx: Kits):
    """Marca o kit como conferido por quem clicou.

    So kit montado se confere: conferir e abrir a caixa pronta e checar o que
    tem dentro. Conferir de novo nao troca o nome — o primeiro que conferiu e
    quem responde pela caixa.
    """
    crianca = db.scalar(
        select(Crianca)
        .where(Crianca.id == crianca_id, ctx.filtro_criancas("gerenciar_kits"))
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
    )
    if crianca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")
    if crianca.desistiu_em is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Crianca desistente nao tem kit para conferir."
        )

    kit = db.scalar(select(Kit).where(Kit.crianca_id == crianca.id))
    if kit is None or kit.status != StatusKit.MONTADO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "O kit ainda nao foi montado: nao ha o que conferir."
        )

    if kit.conferido_por is None:
        kit.conferido_em = datetime.now(UTC)
        kit.conferido_por = ctx.usuario.id
        registrar(
            db, "kit_conferido", usuario_id=ctx.usuario.id,
            tabela="kits", registro_id=kit.id,
            detalhes={"crianca": crianca.id},
        )
        db.commit()
        db.refresh(kit)

    return KitOut(**_saida_kit(crianca, kit))


def _criancas_da_montagem(db: Session, ctx: ContextoAcesso, edicao_id: int, instituicao_id: int):
    """As criancas da instituicao cujo kit se monta: sem as desistentes."""
    return db.scalars(
        select(Crianca).where(
            ctx.filtro_criancas("gerenciar_kits"),
            Crianca.edicao_id == edicao_id,
            Crianca.instituicao_id == instituicao_id,
            Crianca.desistiu_em.is_(None),
        )
    ).all()


@router.get("/kits/montagem", response_model=MontagemOut)
def montagem_da_instituicao(db: BD, ctx: Kits, edicao_id: int, instituicao_id: int):
    """Os nomes da montagem e da conferencia de uma instituicao, para a janela.

    Os nomes moram em cada kit; aqui volta o que esta escrito neles. Se
    kits diferentes tiverem nomes diferentes (marcados um a um, antes), vale
    o mais frequente.
    """
    criancas = _criancas_da_montagem(db, ctx, edicao_id, instituicao_id)
    kits = db.scalars(select(Kit).where(Kit.crianca_id.in_([c.id for c in criancas]))).all()

    def mais_comum(valores):
        contagem: dict[str, int] = defaultdict(int)
        for v in valores:
            if v:
                contagem[v] += 1
        return max(contagem, key=contagem.get) if contagem else None

    return MontagemOut(
        montado_por=mais_comum(k.montado_por_nome for k in kits),
        conferido_por=mais_comum(k.conferido_por_nome for k in kits),
        kits=len(criancas),
    )


@router.put("/kits/montagem", response_model=MontagemOut)
def salvar_montagem(dados: MontagemIn, db: BD, ctx: Kits):
    """Grava quem montou e quem conferiu os kits da instituicao — todos de uma vez.

    A montagem acontece por escola: a equipe separa a pilha de uma
    instituicao, monta tudo e outra pessoa confere tudo. Marcar caixa por
    caixa no sistema era trabalho a toa. Aqui os dois nomes valem para todos
    os kits da instituicao, sem as desistentes (o kit delas nao se monta):

        montado_por preenchido   todos montados, com esse nome
        montado_por vazio        todos voltam a "a montar" (e sem conferencia)
        conferido_por preenchido todos conferidos — exige o montado_por
        conferido_por vazio      a conferencia sai, a montagem fica

    Salvar de novo com outros nomes corrige os nomes e mantem a hora da
    primeira montagem.
    """
    montado = (dados.montado_por or "").strip() or None
    conferido = (dados.conferido_por or "").strip() or None
    if conferido and not montado:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Diga quem montou antes de dizer quem conferiu.",
        )

    criancas = _criancas_da_montagem(db, ctx, dados.edicao_id, dados.instituicao_id)
    agora = datetime.now(UTC)
    for crianca in criancas:
        # O mesmo INSERT ... ON CONFLICT do marcar um a um: duas pessoas
        # salvando ao mesmo tempo nao estouram a unicidade.
        db.execute(
            pg_insert(Kit)
            .values(crianca_id=crianca.id, status=StatusKit.PENDENTE.value)
            .on_conflict_do_nothing(index_elements=["crianca_id"])
        )
        kit = db.scalar(select(Kit).where(Kit.crianca_id == crianca.id))

        if montado:
            if kit.status != StatusKit.MONTADO.value or kit.montado_em is None:
                kit.montado_em = agora
            kit.status = StatusKit.MONTADO.value
            kit.montado_por = ctx.usuario.id
            kit.montado_por_nome = montado
        else:
            kit.status = StatusKit.PENDENTE.value
            kit.montado_em = None
            kit.montado_por = None
            kit.montado_por_nome = None

        if conferido:
            if kit.conferido_em is None:
                kit.conferido_em = agora
            kit.conferido_por = ctx.usuario.id
            kit.conferido_por_nome = conferido
        else:
            kit.conferido_em = None
            kit.conferido_por = None
            kit.conferido_por_nome = None

    registrar(
        db, "kits_montagem", usuario_id=ctx.usuario.id,
        tabela="kits",
        detalhes={
            "instituicao_id": dados.instituicao_id, "kits": len(criancas),
            "montado_por": montado, "conferido_por": conferido,
        },
    )
    db.commit()
    return MontagemOut(montado_por=montado, conferido_por=conferido, kits=len(criancas))


@router.post("/kits/conferir", response_model=list[KitOut])
def conferir_kits(dados: KitConferir, db: BD, ctx: Kits):
    """Confere varios kits de uma vez — o "conferir todos" da escola.

    Em lote, o que nao tem o que conferir (nao montado, ou de desistente) e PULADO em vez de recusar o pedido
    inteiro: na pilha de sessenta, um kit que alguem desmontou no meio do
    caminho nao pode impedir a conferencia dos outros cinquenta e nove. Os ja
    conferidos tambem ficam como estavam: o nome e de quem conferiu primeiro.
    """
    criancas = db.scalars(
        select(Crianca)
        .where(Crianca.id.in_(dados.criancas), ctx.filtro_criancas("gerenciar_kits"))
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
    ).all()
    if len(criancas) != len(set(dados.criancas)):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Ha criancas que voce nao alcanca ou que nao existem."
        )

    kits = {
        k.crianca_id: k
        for k in db.scalars(select(Kit).where(Kit.crianca_id.in_([c.id for c in criancas])))
    }
    agora = datetime.now(UTC)
    conferidos = []
    desistentes = {c.id for c in criancas if c.desistiu_em is not None}
    for kit in kits.values():
        if (
            kit.status == StatusKit.MONTADO.value
            and kit.conferido_por is None
            and kit.crianca_id not in desistentes
        ):
            kit.conferido_em = agora
            kit.conferido_por = ctx.usuario.id
            conferidos.append(kit.crianca_id)

    if conferidos:
        registrar(
            db, "kits_conferidos", usuario_id=ctx.usuario.id,
            tabela="kits", detalhes={"criancas": conferidos},
        )
        db.commit()
        for kit in kits.values():
            db.refresh(kit)

    return [KitOut(**_saida_kit(c, kits.get(c.id))) for c in criancas]


# ---------------------------------------------------------------- check-in

def _hoje() -> date:
    """O dia de hoje no fuso do evento.

    O servidor roda em UTC: com `date.today()` o check-in de um sabado a noite
    fecharia as 21h de Brasilia, porque em UTC ja seria domingo.
    """
    return datetime.now(FUSO).date()


def _dias_da_edicao(db: Session, edicao_id: int) -> list[DiaEvento]:
    return list(
        db.scalars(
            select(DiaEvento).where(DiaEvento.edicao_id == edicao_id).order_by(DiaEvento.data)
        ).all()
    )


def _exige_dia_do_evento(db: Session, edicao_id: int, ctx: ContextoAcesso) -> None:
    """Recusa o check-in fora dos dias do evento da edicao.

    Fica no backend, e nao so na tela: e aqui que a regra vale de verdade. Sem
    isso, um toque perdido na lista uma semana antes marcaria a crianca como
    presente — e no dia ela apareceria como "ja tinha feito check-in".

    A administracao geral passa em qualquer dia: e quem testa e acompanha o
    sistema, e precisa ver a tela funcionando antes do evento. Para todos os
    outros perfis a trava continua.
    """
    if ctx.admin_geral or config.checkin_liberado:
        return
    if not any(d.data == _hoje() for d in _dias_da_edicao(db, edicao_id)):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "O check-in so abre no dia do evento desta edicao.",
        )


@router.get("/checkin/aberto", response_model=CheckinAberto)
def checkin_aberto(db: BD, ctx: Checkin, edicao_id: int):
    """Se hoje e um dos dias do evento desta edicao. A tela pergunta antes de abrir."""
    if not ctx.alcanca_edicao(edicao_id, "fazer_checkin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")
    hoje = _hoje()
    dias = _dias_da_edicao(db, edicao_id)
    no_dia = any(d.data == hoje for d in dias)
    liberado = ctx.admin_geral or config.checkin_liberado
    return CheckinAberto(
        aberto=no_dia or liberado,
        hoje=hoje,
        dias=[DiaCheckin(data=d.data, descricao=d.descricao) for d in dias],
        fora_do_dia=liberado and not no_dia,
    )


def _cuidados(db: Session, ids: list[int]) -> dict[int, str]:
    """Os cuidados que a autorizacao avisa, por crianca, numa frase."""
    autorizacoes = db.scalars(select(Autorizacao).where(Autorizacao.crianca_id.in_(ids))).all()
    return {a.crianca_id: texto for a in autorizacoes if (texto := cuidados.resumo(a))}


def _linha_checkin(c: Crianca, aviso: str | None = None) -> CheckinLinha:
    return CheckinLinha(
        crianca_id=c.id,
        codigo=c.codigo,
        nome=c.nome,
        instituicao_id=c.instituicao_id,
        instituicao=c.instituicao.nome,
        checkin_em=c.checkin_em,
        falta_em=c.falta_em,
        cuidados=aviso,
        desistiu_em=c.desistiu_em,
    )


def _crianca_do_checkin(db: Session, ctx: ContextoAcesso, crianca_id: int, edicao_id: int):
    """A crianca, se quem pede faz check-in nela; senao, 404."""
    crianca = db.scalar(
        select(Crianca)
        .where(
            Crianca.id == crianca_id,
            Crianca.edicao_id == edicao_id,
            ctx.filtro_criancas("fazer_checkin"),
        )
        .options(joinedload(Crianca.instituicao))
    )
    if crianca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")
    return crianca


@router.get("/checkin/lista", response_model=list[CheckinLinha])
def lista_do_checkin(db: BD, ctx: Checkin, edicao_id: int):
    """As criancas que este usuario pode receber, para confirmar uma a uma.

    E a tela do monitor: ele responde por uma ou duas instituicoes e faz o
    check-in a caminho do evento, no celular, com a lista na mao — em vez de
    digitar codigo por codigo. Passa pelo mesmo filtro do check-in, entao cada
    um ve so as instituicoes dele.
    """
    _exige_dia_do_evento(db, edicao_id, ctx)
    criancas = db.scalars(
        select(Crianca)
        .join(Instituicao, Instituicao.id == Crianca.instituicao_id)
        .where(Crianca.edicao_id == edicao_id, ctx.filtro_criancas("fazer_checkin"))
        .options(joinedload(Crianca.instituicao))
        .order_by(Instituicao.nome, Crianca.codigo)
    ).all()

    avisos = _cuidados(db, [c.id for c in criancas])
    return [_linha_checkin(c, avisos.get(c.id)) for c in criancas]


@router.post("/checkin/falta", response_model=CheckinLinha)
def marcar_falta(dados: CheckinDesfazer, db: BD, ctx: Checkin):
    """Marca que a crianca NAO foi ao evento.

    O monitor fecha a lista da turma dele com as duas respostas: quem chegou
    e quem faltou. Sem isso, "sem check-in" misturava quem faltou com quem so
    ainda nao tinha sido conferido. Faltar tira o check-in, se houver: a
    crianca chegou OU faltou. Mesmas regras do check-in.
    """
    _exige_dia_do_evento(db, dados.edicao_id, ctx)
    crianca = _crianca_do_checkin(db, ctx, dados.crianca_id, dados.edicao_id)

    if crianca.falta_em is None:
        crianca.falta_em = datetime.now(UTC)
        crianca.falta_por = ctx.usuario.id
        crianca.checkin_em = None
        crianca.checkin_por = None
        registrar(
            db, "checkin_falta", usuario_id=ctx.usuario.id,
            tabela="criancas", registro_id=crianca.id,
        )
        db.commit()
    return _linha_checkin(crianca, _cuidados(db, [crianca.id]).get(crianca.id))


@router.post("/checkin/desfazer", response_model=CheckinLinha)
def desfazer_checkin(dados: CheckinDesfazer, db: BD, ctx: Checkin):
    """Tira o check-in de uma crianca — o toque errado na lista, o codigo
    trocado na porta.

    Mesmas regras do check-in: so quem faz check-in, so nas criancas que
    alcanca, e so no dia do evento (a administracao geral, em qualquer dia).
    Fica no log quem desfez e a hora que estava gravada, para nada sumir sem
    rastro.
    """
    _exige_dia_do_evento(db, dados.edicao_id, ctx)
    crianca = _crianca_do_checkin(db, ctx, dados.crianca_id, dados.edicao_id)

    # Desfaz o que estiver marcado: a chegada ou a falta. A crianca volta a
    # "sem marcacao".
    if crianca.checkin_em is not None or crianca.falta_em is not None:
        registrar(
            db, "checkin_desfeito", usuario_id=ctx.usuario.id,
            tabela="criancas", registro_id=crianca.id,
            detalhes={
                "checkin_em": crianca.checkin_em.isoformat() if crianca.checkin_em else None,
                "falta_em": crianca.falta_em.isoformat() if crianca.falta_em else None,
            },
        )
        crianca.checkin_em = None
        crianca.checkin_por = None
        crianca.falta_em = None
        crianca.falta_por = None
        db.commit()

    return _linha_checkin(crianca, _cuidados(db, [crianca.id]).get(crianca.id))


@router.post("/checkin", response_model=CheckinOut)
def fazer_checkin(dados: CheckinIn, db: BD, ctx: Checkin):
    """Registra a chegada da crianca no dia do evento.

    Nao recusa nada: quem esta na porta precisa deixar a crianca entrar. O que
    estiver estranho — dia errado, sem padrinho, kit nao montado — volta como
    aviso na tela.
    """
    _exige_dia_do_evento(db, dados.edicao_id, ctx)
    crianca = db.scalar(
        select(Crianca)
        .where(
            func.lower(Crianca.codigo) == dados.codigo.strip().lower(),
            Crianca.edicao_id == dados.edicao_id,
            ctx.filtro_criancas("fazer_checkin"),
        )
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
    )
    if crianca is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Nenhuma crianca com este codigo entre as que voce alcanca.",
        )

    avisos: list[str] = []
    ja_tinha = crianca.checkin_em is not None

    if ja_tinha:
        avisos.append("Esta crianca ja tinha feito check-in.")

    if crianca.dia_evento and crianca.dia_evento.data != _hoje():
        # Na porta o que ajuda e o nome do dia ("Sabado"); a data vai junto
        # porque e ela que resolve a duvida de quem chegou no dia errado.
        data = crianca.dia_evento.data.strftime("%d/%m/%Y")
        dia = f"{crianca.dia_evento.descricao} ({data})" if crianca.dia_evento.descricao else data
        avisos.append(f"O dia dela e {dia}, nao hoje.")
    elif crianca.dia_evento is None:
        avisos.append("Esta crianca nao esta marcada em nenhum dia.")

    # O check-in e feito pela monitoria e pela coordenacao, e cada uma recebe
    # so os avisos do proprio assunto — a mesma regra das colunas da planilha, ver
    # `_saida` em routers/criancas.py. Na pratica: a monitoria na porta nao fica
    # sabendo do kit nem do padrinho daquela crianca.
    ve_kit = ctx.alcanca_edicao(crianca.edicao_id, "gerenciar_kits")
    ve_padrinho = ctx.alcanca_edicao(crianca.edicao_id, "ver_padrinhos")

    kit = db.scalar(select(Kit).where(Kit.crianca_id == crianca.id))
    kit_status = kit.status if kit else StatusKit.PENDENTE.value
    if kit_status == StatusKit.PENDENTE.value and ve_kit:
        avisos.append("O kit dela ainda nao esta montado.")

    if ve_padrinho:
        padrinhos = db.scalar(
            select(func.count())
            .select_from(Apadrinhamento)
            .where(Apadrinhamento.crianca_id == crianca.id)
        )
        if not padrinhos:
            avisos.append("Esta crianca nao tem padrinho.")

    cartoes = db.scalar(
        select(func.count()).select_from(Cartao).where(Cartao.crianca_id == crianca.id)
    )
    if cartoes < 2:
        avisos.append(f"Tem {cartoes} de 2 cartoes digitalizados.")

    if not ja_tinha:
        crianca.checkin_em = datetime.now(UTC)
        crianca.checkin_por = ctx.usuario.id
    # Chegou: se estava marcada como falta (o monitor se adiantou), deixa de
    # estar.
    crianca.falta_em = None
    crianca.falta_por = None

    registrar(
        db, "checkin", usuario_id=ctx.usuario.id,
        tabela="criancas", registro_id=crianca.id,
        detalhes={"codigo": crianca.codigo, "repetido": ja_tinha},
    )
    db.commit()

    return CheckinOut(
        crianca_id=crianca.id,
        nome=crianca.nome,
        idade=crianca.idade,
        instituicao=crianca.instituicao.nome,
        dia_evento=crianca.dia_evento.data if crianca.dia_evento else None,
        dia_evento_descricao=crianca.dia_evento.descricao if crianca.dia_evento else None,
        ja_tinha_checkin=ja_tinha,
        checkin_em=crianca.checkin_em,
        kit_status=kit_status if ve_kit else None,
        avisos=avisos,
    )


@router.get("/checkin/qrcode/{crianca_id}")
def qrcode_da_crianca(crianca_id: int, db: BD, ctx: Checkin):
    """QR com o codigo da crianca, para colar no cracha e ler na porta."""
    crianca = db.scalar(
        select(Crianca).where(Crianca.id == crianca_id, ctx.filtro_criancas("fazer_checkin"))
    )
    if crianca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")

    imagem = qrcode.make(f"{crianca.edicao_id}:{crianca.codigo}")
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="image/png")
