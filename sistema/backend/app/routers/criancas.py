"""Criancas e importacao das listas enviadas pelas instituicoes.

Dado sensivel (LGPD). Toda consulta aqui passa pelo filtro do contexto, que
limita por edicao e, para comissario e monitor, tambem por instituicao.
"""

import json
import uuid
from collections import defaultdict
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
)
from app.schemas.criancas import (
    CriancaEditar,
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
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import Contexto, exige_permissao
from app.servicos import codigos, dias, importador
from app.servicos.upload import ler_limitado
from app.servicos.log import registrar

router = APIRouter(prefix="/criancas", tags=["criancas"])

BD = Annotated[Session, Depends(get_db)]
Ver = Annotated[ContextoAcesso, Depends(exige_permissao("ver_criancas"))]
Editar = Annotated[ContextoAcesso, Depends(exige_permissao("editar_criancas"))]
Importar = Annotated[ContextoAcesso, Depends(exige_permissao("importar_listas"))]

PASTA_IMPORTACOES = config.caminho_arquivos / "importacoes"


def _saida(crianca: Crianca, panorama: dict | None = None) -> CriancaOut:
    extra = panorama or {}
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
        observacoes=crianca.observacoes,
        checkin_em=crianca.checkin_em,
        tem_padrinho_cesta=extra.get("cesta", False),
        tem_padrinho_festa=extra.get("festa", False),
        cartoes=extra.get("cartoes", 0),
        kit_status=extra.get("kit", "pendente"),
    )


def _panorama(db: Session, ids: list[int]) -> dict[int, dict]:
    """Padrinhos, cartoes e kit de varias criancas, em 3 consultas.

    Buscar isso crianca por crianca daria 4500 consultas numa edicao de 1500 —
    a tela nunca abriria.
    """
    if not ids:
        return {}

    dados: dict[int, dict] = {i: {} for i in ids}

    for crianca_id, tipo in db.execute(
        select(Apadrinhamento.crianca_id, Apadrinhamento.tipo)
        .where(Apadrinhamento.crianca_id.in_(ids))
    ).all():
        dados[crianca_id][tipo] = True

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


def _buscar(db: Session, ctx: ContextoAcesso, crianca_id: int, permissao: str) -> Crianca:
    """Busca uma crianca ja aplicando o filtro de alcance."""
    crianca = db.scalar(
        select(Crianca)
        .where(Crianca.id == crianca_id, ctx.filtro_criancas(permissao))
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
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

    if busca:
        termo = f"%{busca.strip()}%"
        condicao = condicao & or_(Crianca.nome.ilike(termo), Crianca.codigo.ilike(termo))

    total = db.scalar(select(func.count()).select_from(Crianca).where(condicao)) or 0

    itens = db.scalars(
        select(Crianca)
        .where(condicao)
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
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
        itens=[_saida(c, panorama.get(c.id)) for c in itens],
    )


@router.get("/resumo-instituicoes", response_model=list[ResumoInstituicao])
def resumo_instituicoes(db: BD, ctx: Ver, edicao_id: int):
    """As abas da tela de criancas, com o que falta em cada instituicao.

    Numa edicao de 20 instituicoes, a coordenacao precisa saber de longe onde
    esta o atraso — nao abrir aba por aba para descobrir.
    """
    alcance = ctx.filtro_criancas("ver_criancas") & (Crianca.edicao_id == edicao_id)

    com_padrinho = (
        select(Apadrinhamento.crianca_id)
        .where(Apadrinhamento.crianca_id == Crianca.id)
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
        )
        .join(Instituicao, Instituicao.id == Crianca.instituicao_id)
        .where(alcance)
        .group_by(Crianca.instituicao_id, Instituicao.nome)
        .order_by(Instituicao.nome)
    ).all()

    # O dia e da instituicao: uma consulta para todas, em vez de uma por aba.
    dias_marcados = {
        instituicao_id: (dia_id, data)
        for instituicao_id, dia_id, data in db.execute(
            select(InstituicaoDia.instituicao_id, InstituicaoDia.dia_evento_id, DiaEvento.data)
            .join(DiaEvento, DiaEvento.id == InstituicaoDia.dia_evento_id)
            .where(InstituicaoDia.edicao_id == edicao_id)
        ).all()
    }

    return [
        ResumoInstituicao(
            instituicao_id=i, instituicao=nome, criancas=total,
            sem_padrinho=sp, sem_cartao=sc,
            dia_evento_id=dias_marcados.get(i, (None, None))[0],
            dia_evento=dias_marcados.get(i, (None, None))[1],
        )
        for i, nome, total, sp, sc in linhas
    ]


@router.post("/lote", response_model=list[CriancaOut])
def editar_em_lote(dados: CriancasEmLote, db: BD, ctx: Editar):
    """Muda varias criancas de uma vez.

    Distribuir 1500 criancas pelos dias do evento uma a uma nao e trabalho que
    alguem faca — por isso o lote.
    """
    criancas = db.scalars(
        select(Crianca)
        .where(Crianca.id.in_(dados.criancas), ctx.filtro_criancas("editar_criancas"))
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
    ).all()

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

    mudou = []
    for crianca in criancas:
        if dados.instituicao_id is not None:
            crianca.instituicao_id = dados.instituicao_id
            # Mudou de escola: o dia passa a ser o da escola nova.
            crianca.dia_evento_id = dias.dia_da_instituicao(
                db, crianca.edicao_id, dados.instituicao_id
            )
            mudou.append("instituicao_id")

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
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
        .order_by(Crianca.nome)
    ).all()
    panorama = _panorama(db, [c.id for c in atualizadas])
    return [_saida(c, panorama.get(c.id)) for c in atualizadas]


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
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
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
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
        .order_by(Crianca.codigo)
    ).all()
    panorama = _panorama(db, [c.id for c in atualizadas])
    return [_saida(c, panorama.get(c.id)) for c in atualizadas]


@router.get("/{crianca_id}", response_model=CriancaDetalhe)
def detalhe(crianca_id: int, db: BD, ctx: Ver):
    """Ficha da crianca: apadrinhamento, cartoes e kit numa consulta so."""
    crianca = db.scalar(
        select(Crianca)
        .where(Crianca.id == crianca_id, ctx.filtro_criancas("ver_criancas"))
        .options(
            joinedload(Crianca.instituicao),
            joinedload(Crianca.dia_evento),
            joinedload(Crianca.edicao),
        )
    )
    if crianca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")

    # O contato do padrinho e dado de quem doa, nao da crianca: quem so tem
    # ver_criancas fica sabendo QUE ha padrinho, mas nao quem e nem o telefone.
    pode_contato = ctx.pode("ver_padrinhos")

    apadrinhamentos = db.execute(
        select(Apadrinhamento, Padrinho)
        .join(Padrinho, Padrinho.id == Apadrinhamento.padrinho_id)
        .where(Apadrinhamento.crianca_id == crianca.id)
        .order_by(Apadrinhamento.tipo)
    ).all()

    padrinhos = [
        PadrinhoDaCrianca(
            apadrinhamento_id=a.id,
            tipo=a.tipo,
            valor=a.valor,
            pago=a.pagamento_id is not None,
            padrinho_id=p.id,
            nome=p.nome if pode_contato else "(sem permissao para ver)",
            whatsapp=p.whatsapp if pode_contato else None,
            email=p.email if pode_contato else None,
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
        observacoes=crianca.observacoes,
        checkin_em=crianca.checkin_em,
        padrinhos=padrinhos,
        cartoes=[
            CartaoDaCrianca(
                id=c.id, tipo=c.tipo, status=c.status,
                criado_em=c.criado_em, enviado_em=c.enviado_em,
            )
            for c in cartoes
        ],
        kit_status=kit.status if kit else "pendente",
        kit_entregue_em=kit.entregue_em if kit else None,
        pode_ver_contato=pode_contato,
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
    crianca.nome = " ".join(crianca.nome.split())
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
    return _saida(_buscar(db, ctx, crianca.id, "editar_criancas"))


@router.patch("/{crianca_id}", response_model=CriancaOut)
def editar(crianca_id: int, dados: CriancaEditar, db: BD, ctx: Editar):
    crianca = _buscar(db, ctx, crianca_id, "editar_criancas")

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        setattr(crianca, campo, " ".join(valor.split()) if campo == "nome" and valor else valor)

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
    return _saida(_buscar(db, ctx, crianca_id, "editar_criancas"))


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
