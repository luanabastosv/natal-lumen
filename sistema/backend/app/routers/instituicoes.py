"""Instituicoes. Pertencem a uma cidade e persistem entre anos."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Cidade, Crianca, DiaEvento, Edicao, Instituicao, InstituicaoDia
from app.schemas.cadastros import (
    DependenciasOut,
    InstituicaoEditar,
    InstituicaoIn,
    InstituicaoOut,
)
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import Contexto, exige_permissao
from app.servicos import codigos, exclusao
from app.servicos.log import registrar

router = APIRouter(prefix="/instituicoes", tags=["cadastros"])

BD = Annotated[Session, Depends(get_db)]
Cadastros = Annotated[ContextoAcesso, Depends(exige_permissao("gerenciar_cadastros"))]


def _saida(inst: Instituicao, extra: dict | None = None) -> InstituicaoOut:
    extra = extra or {}
    return InstituicaoOut(
        id=inst.id,
        cidade_id=inst.cidade_id,
        cidade=inst.cidade.nome,
        nome=inst.nome,
        sigla=inst.sigla,
        responsavel=inst.responsavel,
        telefone=inst.telefone,
        endereco=inst.endereco,
        ativo=inst.ativo,
        dia_evento_id=extra.get("dia_evento_id"),
        dia_evento=extra.get("dia_evento"),
        dia_evento_descricao=extra.get("dia_evento_descricao"),
        onibus=extra.get("onibus", 0),
        criancas=extra.get("criancas", 0),
        codigos_atualizados=extra.get("codigos_atualizados", 0),
    )


def _cidades_do_usuario(db: Session, ctx: ContextoAcesso) -> list[int]:
    """Cidades das edicoes que o usuario alcanca."""
    if not ctx.edicoes:
        return []
    return list(
        db.scalars(select(Edicao.cidade_id).where(Edicao.id.in_(ctx.edicoes))).all()
    )


def _conferir_cidade(db: Session, ctx: ContextoAcesso, cidade_id: int) -> None:
    if ctx.admin_geral:
        return
    if cidade_id not in _cidades_do_usuario(db, ctx):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Esta instituicao nao e de uma cidade sua."
        )


def _buscar(db: Session, ctx: ContextoAcesso, instituicao_id: int) -> Instituicao:
    inst = db.get(Instituicao, instituicao_id)
    if inst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instituicao nao encontrada.")

    _conferir_cidade(db, ctx, inst.cidade_id)
    return inst


@router.get("", response_model=list[InstituicaoOut])
def listar(
    db: BD,
    ctx: Contexto,
    cidade_id: int | None = None,
    edicao_id: int | None = None,
):
    """Lista as instituicoes das cidades que o usuario alcanca.

    Nao filtra pelas instituicoes atribuidas em usuario_instituicao: o nome da
    instituicao nao e dado sensivel, e comissarios precisam ver a lista para
    entender de onde vem cada crianca. O filtro fino vale para as criancas.
    """
    consulta = (
        select(Instituicao)
        .options(joinedload(Instituicao.cidade))
        .order_by(Instituicao.nome)
    )

    if not ctx.admin_geral:
        cidades = _cidades_do_usuario(db, ctx)
        if not cidades:
            return []
        consulta = consulta.where(Instituicao.cidade_id.in_(cidades))

    if cidade_id is not None:
        consulta = consulta.where(Instituicao.cidade_id == cidade_id)

    if edicao_id is not None:
        # Com uma edicao escolhida, so as instituicoes da cidade dela fazem
        # sentido: as outras nao podem ter dia nesta edicao, e mostra-las so
        # levaria a um erro na cara do usuario.
        edicao = db.get(Edicao, edicao_id)
        if edicao is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")
        consulta = consulta.where(Instituicao.cidade_id == edicao.cidade_id)

    instituicoes = db.scalars(consulta).all()

    # Com uma edicao escolhida, a listagem traz o dia marcado e quantas
    # criancas ha nela — e o que a tela de cadastro precisa mostrar.
    extras: dict[int, dict] = {}
    if edicao_id is not None:
        for inst_id, dia_id, data, descricao, onibus in db.execute(
            select(
                InstituicaoDia.instituicao_id,
                InstituicaoDia.dia_evento_id,
                DiaEvento.data,
                DiaEvento.descricao,
                InstituicaoDia.onibus,
            )
            .join(DiaEvento, DiaEvento.id == InstituicaoDia.dia_evento_id)
            .where(InstituicaoDia.edicao_id == edicao_id)
        ).all():
            extras.setdefault(inst_id, {})["dia_evento_id"] = dia_id
            extras[inst_id]["dia_evento"] = data
            extras[inst_id]["dia_evento_descricao"] = descricao
            extras[inst_id]["onibus"] = onibus

        for inst_id, quantas in db.execute(
            select(Crianca.instituicao_id, func.count())
            .where(Crianca.edicao_id == edicao_id)
            .group_by(Crianca.instituicao_id)
        ).all():
            extras.setdefault(inst_id, {})["criancas"] = quantas

    return [_saida(i, extras.get(i.id)) for i in instituicoes]


@router.post("", response_model=InstituicaoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: InstituicaoIn, db: BD, ctx: Cadastros):
    if db.get(Cidade, dados.cidade_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cidade nao encontrada.")

    _conferir_cidade(db, ctx, dados.cidade_id)

    inst = Instituicao(**dados.model_dump())
    inst.nome = inst.nome.strip()

    if inst.sigla:
        inst.sigla = inst.sigla.strip().upper()
    else:
        # Sugerida a partir do nome, evitando as que a cidade ja usa.
        usadas = set(
            db.scalars(
                select(Instituicao.sigla).where(
                    Instituicao.cidade_id == inst.cidade_id,
                    Instituicao.sigla.is_not(None),
                )
            ).all()
        )
        inst.sigla = codigos.sugerir_sigla(inst.nome, usadas)

    db.add(inst)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta cidade ja tem uma instituicao com este nome ou com esta sigla.",
        )

    registrar(
        db, "instituicao_criada", usuario_id=ctx.usuario.id,
        tabela="instituicoes", registro_id=inst.id,
        detalhes={"nome": inst.nome, "cidade_id": inst.cidade_id},
    )
    db.commit()
    db.refresh(inst)
    return _saida(inst)


def _passar_codigos_para(db: Session, inst: Instituicao, antiga: str, nova: str) -> int:
    """Troca a sigla nos codigos das criancas desta instituicao.

    Mudar a sigla no cadastro e nao mexer nos codigos deixava a planilha das
    criancas com o prefixo antigo — ES04 numa instituicao que hoje e SL. O
    numero de cada crianca nao muda: so o prefixo. Renumerar e outra coisa, que
    muda a ordem, e continua sendo a pedido, em /criancas/renumerar.

    Vale para todas as edicoes: a sigla e da instituicao e nao e de um ano so.
    """
    criancas = db.scalars(
        select(Crianca).where(Crianca.instituicao_id == inst.id)
    ).all()

    trocas = []
    for crianca in criancas:
        novo = codigos.trocar_sigla(crianca.codigo, antiga, nova)
        if novo and novo != crianca.codigo:
            trocas.append((crianca, novo))

    if not trocas:
        return 0

    # Codigo temporario primeiro: a unicidade e por edicao + instituicao +
    # codigo, e escrever direto esbarraria em quem ja tem o codigo de destino
    # no meio do caminho.
    for i, (crianca, _) in enumerate(trocas):
        crianca.codigo = f"~{i}"
    db.flush()

    for crianca, novo in trocas:
        crianca.codigo = novo

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Trocar a sigla para {nova} esbarra em codigos que ja existem nesta "
            "instituicao. Confira os codigos das criancas antes de mudar a sigla.",
        )

    return len(trocas)


@router.patch("/{instituicao_id}", response_model=InstituicaoOut)
def editar(instituicao_id: int, dados: InstituicaoEditar, db: BD, ctx: Cadastros):
    inst = _buscar(db, ctx, instituicao_id)

    sigla_antiga = inst.sigla

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        if campo == "nome" and valor:
            valor = valor.strip()
        if campo == "sigla" and valor:
            valor = valor.strip().upper()
        setattr(inst, campo, valor)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta cidade ja tem uma instituicao com este nome ou com esta sigla.",
        )

    # A sigla e o prefixo do codigo das criancas: trocar uma sem a outra deixa
    # a planilha apontando para uma sigla que nao existe mais.
    trocados = 0
    if sigla_antiga and inst.sigla and inst.sigla != sigla_antiga:
        trocados = _passar_codigos_para(db, inst, sigla_antiga, inst.sigla)

    registrar(
        db, "instituicao_editada", usuario_id=ctx.usuario.id,
        tabela="instituicoes", registro_id=inst.id,
        detalhes={"campos": sorted(mudancas)},
    )
    if trocados:
        registrar(
            db, "criancas_nova_sigla", usuario_id=ctx.usuario.id,
            tabela="criancas", registro_id=inst.id,
            detalhes={
                "instituicao_id": inst.id,
                "de": sigla_antiga,
                "para": inst.sigla,
                "quantas": trocados,
            },
        )
    db.commit()
    db.refresh(inst)
    return _saida(inst, {"codigos_atualizados": trocados})


@router.get("/{instituicao_id}/dependencias", response_model=DependenciasOut)
def dependencias(instituicao_id: int, db: BD, ctx: Cadastros):
    """O que seria apagado junto com a instituicao. A tela pergunta isto antes.

    A conta e de TODAS as edicoes, nao so da que esta aberta na tela: o
    cadastro da instituicao e um so e atravessa os anos, entao apaga-lo leva
    tambem a lista que ela mandou nos anos anteriores.
    """
    inst = _buscar(db, ctx, instituicao_id)
    return exclusao.resumir(
        db, inst.id, inst.nome, exclusao.alcance_da_instituicao(instituicao_id)
    )


@router.delete("/{instituicao_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(
    instituicao_id: int,
    db: BD,
    ctx: Cadastros,
    confirmar: Annotated[bool, Query()] = False,
):
    """Apaga a instituicao e as criancas dela, de todos os anos.

    Desativar (`ativo=false`) continua sendo o caminho normal para uma
    instituicao que so nao participa este ano — isso guarda o historico. Apagar
    e para a que nunca deveria ter entrado: some com a lista inteira dela.

    `confirmar` existe para a exclusao nunca acontecer por engano fora da tela:
    com dados pendurados, o pedido sem confirmacao volta 409 com a conta de
    quantos sao.
    """
    inst = _buscar(db, ctx, instituicao_id)
    # Lidos antes do DELETE: depois dele o objeto nao pode mais ser consultado.
    nome, cidade_id = inst.nome, inst.cidade_id

    resumo = exclusao.resumir(
        db, instituicao_id, nome, exclusao.alcance_da_instituicao(instituicao_id)
    )
    if resumo.total and not confirmar:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{nome} tem {resumo.total} registro(s) ligados a ela. "
            "Confirme a exclusao para apagar tudo junto.",
        )

    orfaos = exclusao.apagar_instituicao(db, instituicao_id)

    registrar(
        db, "instituicao_apagada", usuario_id=ctx.usuario.id,
        tabela="instituicoes", registro_id=instituicao_id,
        detalhes={
            "nome": nome,
            "cidade_id": cidade_id,
            "levou": {item.chave: item.quantidade for item in resumo.itens},
        },
    )
    db.commit()
    exclusao.remover_arquivos(orfaos)
