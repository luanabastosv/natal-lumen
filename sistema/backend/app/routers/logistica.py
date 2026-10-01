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

from app.database import get_db
from app.models import Apadrinhamento, Cartao, Crianca, DiaEvento, Instituicao, Kit
from app.models.tipos import StatusKit
from app.schemas.logistica import (
    CheckinIn,
    CheckinOut,
    InstituicaoKits,
    KitMudar,
    KitOut,
    PaginaKits,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos.log import registrar

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
        "desistiu_em": crianca.desistiu_em,
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
    for _crianca, kit in linhas:
        resumo[kit.status if kit else StatusKit.PENDENTE.value] += 1

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
    """As abas da tela de kits: uma por instituicao, com o que falta montar.

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
        )
        .select_from(Crianca)
        .join(Instituicao, Instituicao.id == Crianca.instituicao_id)
        .outerjoin(Kit, Kit.crianca_id == Crianca.id)
        .where(alcance)
        .group_by(Instituicao.id, Instituicao.nome, Instituicao.sigla)
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
            # voltou para a fila.
            kit.montado_em = None
            kit.montado_por = None

        db.flush()
        saida.append(KitOut(**_saida_kit(crianca, kit)))

    registrar(
        db, "kits_atualizados", usuario_id=ctx.usuario.id,
        tabela="kits",
        detalhes={"status": dados.status, "criancas": [c.id for c in criancas]},
    )
    db.commit()
    return saida


# ---------------------------------------------------------------- check-in

@router.post("/checkin", response_model=CheckinOut)
def fazer_checkin(dados: CheckinIn, db: BD, ctx: Checkin):
    """Registra a chegada da crianca no dia do evento.

    Nao recusa nada: quem esta na porta precisa deixar a crianca entrar. O que
    estiver estranho — dia errado, sem padrinho, kit nao montado — volta como
    aviso na tela.
    """
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

    if crianca.dia_evento and crianca.dia_evento.data != date.today():
        # Na porta o que ajuda e o nome do dia ("Sabado"); a data vai junto
        # porque e ela que resolve a duvida de quem chegou no dia errado.
        data = crianca.dia_evento.data.strftime("%d/%m/%Y")
        dia = f"{crianca.dia_evento.descricao} ({data})" if crianca.dia_evento.descricao else data
        avisos.append(f"O dia dela e {dia}, nao hoje.")
    elif crianca.dia_evento is None:
        avisos.append("Esta crianca nao esta marcada em nenhum dia.")

    # O check-in e feito por tres equipes diferentes, e cada uma recebe so os
    # avisos do proprio assunto — a mesma regra das colunas da planilha, ver
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
