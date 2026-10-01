"""Padrinhos, apadrinhamentos e pagamentos.

Um padrinho pertence a uma edicao (cidade + ano) e nao persiste entre anos.
Pode apadrinhar varias criancas, inclusive de outra cidade — e nesse caso o
registro fica visivel pelos dois lados: pela edicao do padrinho e pela da
crianca.

Quem liga as duas pontas e o comissario, e cada apadrinhamento guarda qual foi
(`apadrinhamentos.comissario_id`): o mesmo padrinho recebe criancas de
comissarios diferentes, e sem isso ninguem sabe quem cobra o que. O outro lado
da mesma moeda e a regra em `criar_apadrinhamento`: o comissario so apadrinha
as criancas da propria lista.
"""

from decimal import Decimal

DOIS_DECIMAIS = Decimal("0.01")
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models import Apadrinhamento, Crianca, Edicao, EnvioCartao, Padrinho, Pagamento
from app.models.tipos import TipoApadrinhamento
from app.schemas.cadastros import DependenciasOut
from app.schemas.padrinhos import (
    ApadrinhamentoEditar,
    ApadrinhamentoIn,
    ApadrinhamentoResumo,
    EnvioCartaoOut,
    PadrinhoEditar,
    PadrinhoIn,
    PadrinhoOut,
    PaginaPadrinhos,
    PaginaPagamentos,
    PagamentoEditar,
    PagamentoIn,
    PagamentoOut,
)
from app.servicos.apadrinhamento import confirmado
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos import agradecimento, comprovantes, exclusao, whatsapp
from app.servicos.log import registrar
from app.servicos.nomes import nome_proprio

router = APIRouter(tags=["padrinhos"])

BD = Annotated[Session, Depends(get_db)]
Ver = Annotated[ContextoAcesso, Depends(exige_permissao("ver_padrinhos"))]
Editar = Annotated[ContextoAcesso, Depends(exige_permissao("editar_padrinhos"))]
# Registrar o pagamento do proprio padrinho — o comissario tem. E o que
# CONFIRMA o apadrinhamento dele: sem isto, o que ele capta nao aparece em
# numero nenhum ate a coordenacao passar por ali.
Pagar = Annotated[
    ContextoAcesso, Depends(exige_permissao("registrar_pagamentos_padrinho"))
]
# Mexer no dinheiro ja registrado: conferir e apagar. So a coordenacao — quem
# registra o dinheiro nao e quem audita o registro.
Auditar = Annotated[ContextoAcesso, Depends(exige_permissao("registrar_pagamentos"))]
# Desfazer engano de captacao: apagar padrinho, e desfazer apadrinhamento MESMO
# ja pago. So a coordenacao.
Excluir = Annotated[ContextoAcesso, Depends(exige_permissao("excluir_padrinhos"))]


# ---------------------------------------------------------------- alcance

def _edicoes(ctx: ContextoAcesso, permissao: str) -> list[int]:
    return ctx.edicoes_com(permissao)


def _filtro_padrinhos(ctx: ContextoAcesso, permissao: str):
    """Padrinhos das edicoes que o usuario alcanca.

    Tambem alcanca o padrinho de outra edicao que apadrinhou uma crianca de uma
    edicao sua — e o caso entre cidades, visivel pelos dois lados.
    """
    if ctx.admin_geral:
        return Padrinho.id.is_not(None)

    edicoes = _edicoes(ctx, permissao)
    if not edicoes:
        return Padrinho.id.is_(None)

    pelo_lado_da_crianca = select(Apadrinhamento.padrinho_id).join(
        Crianca, Crianca.id == Apadrinhamento.crianca_id
    ).where(Crianca.edicao_id.in_(edicoes))

    return or_(
        Padrinho.edicao_id.in_(edicoes),
        Padrinho.id.in_(pelo_lado_da_crianca),
    )


def _e_meu(ctx: ContextoAcesso, db: Session, apadrinhamento: Apadrinhamento) -> bool:
    """Se este apadrinhamento pode ser MEXIDO por quem esta pedindo.

    Um padrinho recebe criancas de varios comissarios, e cada apadrinhamento
    guarda quem o registrou. O comissario de base so mexe nos proprios: editar
    ou desfazer o do colega mudaria o trabalho — e o numero — de outra pessoa,
    sem ela saber.

    Quem NAO e filtrado crianca a crianca (a coordenacao da captacao, a
    coordenacao da cidade, a administracao geral) passa sempre: e justamente
    para isso que existe quem coordena. Ver `so_proprias_criancas` em
    seguranca/contexto.py, que e o mesmo teste que o painel usa.
    """
    crianca = db.get(Crianca, apadrinhamento.crianca_id)
    if crianca is None or not ctx.so_proprias_criancas(crianca.edicao_id):
        return True
    return apadrinhamento.comissario_id == ctx.usuario.id


DO_COLEGA = (
    "Este apadrinhamento foi registrado por outra pessoa do time. "
    "Peca a quem coordena a captacao."
)


def _saida(padrinho: Padrinho) -> PadrinhoOut:
    resumos = []
    combinado = Decimal("0")
    pago = Decimal("0")

    for a in padrinho.apadrinhamentos:
        quitado = a.pagamento_id is not None
        # O mais recente manda: uma falha seguida de reenvio bem-sucedido
        # tem de aparecer como enviado.
        ultimo = max(a.envios, key=lambda e: e.criado_em, default=None)
        combinado += a.valor
        if quitado:
            pago += a.valor
        resumos.append(
            ApadrinhamentoResumo(
                id=a.id,
                crianca_id=a.crianca_id,
                crianca_primeiro_nome=a.crianca.primeiro_nome,
                crianca_codigo=a.crianca.codigo,
                crianca_nome=a.crianca.nome,
                crianca_idade=a.crianca.idade,
                tipo=a.tipo,
                valor=a.valor,
                pago=quitado,
                vai_ao_evento=a.vai_ao_evento,
                comissario_id=a.comissario_id,
                comissario=a.comissario.nome if a.comissario else None,
                cartao_status=ultimo.status if ultimo else None,
                cartao_enviado_em=ultimo.criado_em if ultimo else None,
            )
        )

    return PadrinhoOut(
        id=padrinho.id,
        edicao_id=padrinho.edicao_id,
        edicao=padrinho.edicao.nome,
        cidade=padrinho.edicao.cidade.nome,
        ano=padrinho.edicao.ano,
        nome=padrinho.nome,
        whatsapp=padrinho.whatsapp,
        email=padrinho.email,
        observacoes=padrinho.observacoes,
        membro_ser_feliz=padrinho.membro_ser_feliz,
        interesse_mensal=padrinho.interesse_mensal,
        criado_em=padrinho.criado_em,
        apadrinhamentos=resumos,
        # Quantizados para o total sair sempre com duas casas: sem isto um
        # padrinho sem pagamento devolvia "0" e outro devolvia "240.00".
        total_combinado=combinado.quantize(DOIS_DECIMAIS),
        total_pago=pago.quantize(DOIS_DECIMAIS),
    )


def _carregar(db: Session, padrinho_id: int, ctx: ContextoAcesso, permissao: str) -> Padrinho:
    padrinho = db.scalar(
        select(Padrinho)
        .where(Padrinho.id == padrinho_id, _filtro_padrinhos(ctx, permissao))
        .options(
            joinedload(Padrinho.edicao).joinedload(Edicao.cidade),
            selectinload(Padrinho.apadrinhamentos).joinedload(Apadrinhamento.crianca),
            selectinload(Padrinho.apadrinhamentos).joinedload(Apadrinhamento.comissario),
            selectinload(Padrinho.apadrinhamentos).selectinload(Apadrinhamento.envios),
        )
    )
    if padrinho is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Padrinho nao encontrado.")
    return padrinho


# ---------------------------------------------------------------- padrinhos

@router.get("/padrinhos", response_model=PaginaPadrinhos)
def listar_padrinhos(
    db: BD,
    ctx: Ver,
    edicao_id: int | None = None,
    busca: str | None = None,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
):
    condicao = _filtro_padrinhos(ctx, "ver_padrinhos")

    if edicao_id is not None:
        condicao = condicao & (Padrinho.edicao_id == edicao_id)
    if busca:
        termo = f"%{busca.strip()}%"
        condicao = condicao & or_(
            Padrinho.nome.ilike(termo),
            Padrinho.whatsapp.ilike(termo),
            Padrinho.email.ilike(termo),
        )

    total = db.scalar(select(func.count()).select_from(Padrinho).where(condicao)) or 0

    itens = db.scalars(
        select(Padrinho)
        .where(condicao)
        .options(
            joinedload(Padrinho.edicao).joinedload(Edicao.cidade),
            selectinload(Padrinho.apadrinhamentos).joinedload(Apadrinhamento.crianca),
            selectinload(Padrinho.apadrinhamentos).joinedload(Apadrinhamento.comissario),
            selectinload(Padrinho.apadrinhamentos).selectinload(Apadrinhamento.envios),
        )
        .order_by(Padrinho.nome)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).unique().all()

    return PaginaPadrinhos(
        total=total, pagina=pagina, por_pagina=por_pagina,
        itens=[_saida(p) for p in itens],
    )


@router.post("/padrinhos", response_model=PadrinhoOut, status_code=status.HTTP_201_CREATED)
def criar_padrinho(dados: PadrinhoIn, db: BD, ctx: Editar):
    if not ctx.alcanca_edicao(dados.edicao_id, "editar_padrinhos"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Voce nao capta padrinhos nesta edicao.")

    padrinho = Padrinho(
        edicao_id=dados.edicao_id,
        nome=nome_proprio(dados.nome),
        whatsapp=dados.whatsapp,
        email=dados.email,
        observacoes=dados.observacoes,
        membro_ser_feliz=dados.membro_ser_feliz,
        interesse_mensal=dados.interesse_mensal,
        criado_por=ctx.usuario.id,
    )
    db.add(padrinho)
    db.flush()

    registrar(
        db, "padrinho_criado", usuario_id=ctx.usuario.id,
        tabela="padrinhos", registro_id=padrinho.id,
        detalhes={"nome": padrinho.nome, "edicao_id": padrinho.edicao_id},
    )
    db.commit()
    return _saida(_carregar(db, padrinho.id, ctx, "editar_padrinhos"))


@router.get("/padrinhos/{padrinho_id}", response_model=PadrinhoOut)
def detalhe_padrinho(padrinho_id: int, db: BD, ctx: Ver):
    return _saida(_carregar(db, padrinho_id, ctx, "ver_padrinhos"))


@router.patch("/padrinhos/{padrinho_id}", response_model=PadrinhoOut)
def editar_padrinho(padrinho_id: int, dados: PadrinhoEditar, db: BD, ctx: Editar):
    padrinho = _carregar(db, padrinho_id, ctx, "editar_padrinhos")

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        setattr(padrinho, campo, nome_proprio(valor) if campo == "nome" and valor else valor)

    registrar(
        db, "padrinho_editado", usuario_id=ctx.usuario.id,
        tabela="padrinhos", registro_id=padrinho.id,
        detalhes={"campos": sorted(mudancas)},
    )
    db.commit()
    return _saida(_carregar(db, padrinho_id, ctx, "editar_padrinhos"))


# ---------------------------------------------------------- apadrinhamentos

def _fora_do_alcance(crianca: Crianca) -> str:
    """Por que esta crianca nao e desta pessoa, em portugues.

    A decisao ja foi tomada pelo filtro do contexto; isto e so o recado. Os
    casos estao separados porque cada um manda procurar outra pessoa: a
    coordenacao, que distribui a lista, ou o colega que ja tem a crianca.
    """
    if crianca.comissario_id is None:
        return (
            "Esta crianca ainda nao tem comissario responsavel. Fale com a "
            "coordenacao para recebe-la na sua lista."
        )
    if crianca.comissario is not None:
        return (
            f"Esta crianca esta na lista de {crianca.comissario.nome}. Cada "
            "comissario so apadrinha as criancas atribuidas a ele."
        )
    return "Esta crianca nao esta na sua lista."


@router.post("/apadrinhamentos", response_model=PadrinhoOut, status_code=status.HTTP_201_CREATED)
def criar_apadrinhamento(dados: ApadrinhamentoIn, db: BD, ctx: Editar):
    """Liga uma crianca a um padrinho, num dos dois tipos."""
    padrinho = _carregar(db, dados.padrinho_id, ctx, "editar_padrinhos")

    crianca = db.scalar(
        select(Crianca)
        .where(Crianca.id == dados.crianca_id)
        .options(joinedload(Crianca.edicao), joinedload(Crianca.comissario))
    )
    if crianca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")

    # A crianca precisa estar numa edicao que o usuario alcanca — nao
    # necessariamente a mesma do padrinho, porque entre cidades e permitido.
    if not ctx.alcanca_edicao(crianca.edicao_id, "editar_padrinhos"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Voce nao registra apadrinhamento nesta edicao."
        )

    # Alcancar a edicao nao basta: o comissario so apadrinha as criancas
    # atribuidas a ele. Sem esta conferencia, a busca por codigo — que e um
    # escape de proposito, para achar crianca de outra instituicao — virava um
    # jeito de apadrinhar a crianca do colega, e o padrinho terminava com
    # criancas que ninguem sabia de quem eram.
    #
    # A conferencia reusa a MESMA condicao SQL que filtra a lista de criancas,
    # e nao uma copia da regra: assim os dois caminhos nao podem divergir. Para
    # a coordenacao ela continua valendo a edicao inteira.
    no_alcance = db.scalar(
        select(Crianca.id).where(
            Crianca.id == crianca.id, ctx.filtro_criancas("editar_padrinhos")
        )
    )
    if no_alcance is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _fora_do_alcance(crianca))

    valor = dados.valor
    if valor is None:
        # Copiado da edicao da CRIANCA: e a edicao que define quanto custa a
        # cesta e a festa daquele evento.
        valor = (
            crianca.edicao.valor_cesta
            if dados.tipo == TipoApadrinhamento.CESTA
            else crianca.edicao.valor_festa
        )

    apadrinhamento = Apadrinhamento(
        crianca_id=crianca.id,
        padrinho_id=padrinho.id,
        tipo=dados.tipo,
        valor=valor,
        comissario_id=ctx.usuario.id,
        vai_ao_evento=dados.vai_ao_evento,
    )
    db.add(apadrinhamento)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Esta crianca ja tem padrinho de {dados.tipo}.",
        )

    registrar(
        db, "apadrinhamento_criado", usuario_id=ctx.usuario.id,
        tabela="apadrinhamentos", registro_id=apadrinhamento.id,
        detalhes={
            "crianca_id": crianca.id, "padrinho_id": padrinho.id,
            "tipo": dados.tipo, "valor": str(valor),
        },
    )
    db.commit()
    return _saida(_carregar(db, padrinho.id, ctx, "editar_padrinhos"))


def _apadrinhamento_do_cartao(db: Session, apadrinhamento_id: int, ctx: ContextoAcesso):
    """Busca o apadrinhamento conferindo os dois alcances que o cartao exige."""
    apadrinhamento = db.scalar(
        select(Apadrinhamento)
        .join(Padrinho, Apadrinhamento.padrinho_id == Padrinho.id)
        .where(
            Apadrinhamento.id == apadrinhamento_id,
            _filtro_padrinhos(ctx, "ver_padrinhos"),
        )
        .options(
            joinedload(Apadrinhamento.crianca).joinedload(Crianca.instituicao),
            joinedload(Apadrinhamento.crianca).joinedload(Crianca.dia_evento),
            joinedload(Apadrinhamento.padrinho)
            .joinedload(Padrinho.edicao)
            .joinedload(Edicao.cidade),
        )
    )
    if apadrinhamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Apadrinhamento nao encontrado.")

    # O cartao leva nome, codigo e instituicao da crianca — mais do que a tela
    # de padrinhos mostra de proposito. Por isso exige tambem ver_criancas, e
    # na edicao DA CRIANCA: quem so cuida de padrinhos nao le a ficha dela por
    # este caminho.
    if not ctx.alcanca_edicao(apadrinhamento.crianca.edicao_id, "ver_criancas"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Voce precisa alcancar as criancas desta edicao para gerar o cartao.",
        )

    # O cartao agradece quem doou. Enquanto o apadrinhamento e so promessa nao
    # ha doacao para agradecer, e mandar o agradecimento antes do dinheiro e
    # cobrar ao contrario. Barra aqui — no lugar por onde passam tanto o baixar
    # quanto o enviar — e nao em cada rota.
    if not confirmado(apadrinhamento):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este apadrinhamento ainda e uma promessa: nao ha pagamento "
            "registrado. O cartao de agradecimento so sai depois que a "
            "coordenacao registrar o pagamento.",
        )
    return apadrinhamento


def _montar_cartao(apadrinhamento) -> tuple[bytes, str]:
    """PNG do cartao e o nome do arquivo. Montado na hora, nada fica guardado."""
    crianca = apadrinhamento.crianca
    edicao = apadrinhamento.padrinho.edicao
    png = agradecimento.gerar(
        crianca_nome=crianca.nome,
        crianca_codigo=crianca.codigo,
        instituicao=crianca.instituicao.nome,
        dia_evento=crianca.dia_evento.data if crianca.dia_evento else None,
        cidade=edicao.cidade.nome,
        ano=edicao.ano,
    )
    return png, agradecimento.nome_do_arquivo(crianca.codigo, crianca.nome)


@router.get("/apadrinhamentos/{apadrinhamento_id}/agradecimento")
def cartao_de_agradecimento(apadrinhamento_id: int, db: BD, ctx: Ver):
    """PNG de agradecimento desta crianca, para baixar e mandar a mao."""
    apadrinhamento = _apadrinhamento_do_cartao(db, apadrinhamento_id, ctx)
    png, nome = _montar_cartao(apadrinhamento)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.post(
    "/apadrinhamentos/{apadrinhamento_id}/agradecimento/enviar",
    response_model=EnvioCartaoOut,
)
def enviar_cartao(apadrinhamento_id: int, db: BD, ctx: Editar):
    """Manda o cartao ao WhatsApp do padrinho pela Cloud API da Meta.

    Exige editar_padrinhos, e nao so ver: isto gasta dinheiro (a Meta cobra
    por conversa) e chega no telefone de um doador. Nao e uma leitura.

    A tentativa fica gravada mesmo quando falha — sem isso ninguem descobre
    que o numero de um padrinho esta errado.
    """
    apadrinhamento = _apadrinhamento_do_cartao(db, apadrinhamento_id, ctx)
    padrinho = apadrinhamento.padrinho
    telefone = whatsapp.telefone_e164(padrinho.whatsapp)

    if not telefone:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Este padrinho nao tem um WhatsApp valido cadastrado.",
        )

    if not whatsapp.configurado():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "O envio pelo WhatsApp nao esta configurado neste servidor. "
            "Use o botao de baixar o cartao.",
        )

    png, nome_arquivo = _montar_cartao(apadrinhamento)

    envio = EnvioCartao(
        apadrinhamento_id=apadrinhamento.id,
        telefone=telefone,
        status="falhou",
        enviado_por=ctx.usuario.id,
    )

    try:
        enviado = whatsapp.enviar_cartao(
            telefone=telefone,
            png=png,
            nome_arquivo=nome_arquivo,
            padrinho_nome=padrinho.nome.split(" ")[0],
            crianca_nome=apadrinhamento.crianca.primeiro_nome,
        )
    except whatsapp.ErroWhatsapp as erro:
        envio.erro = f"{erro.mensagem} {erro.detalhe}".strip()
        db.add(envio)
        registrar(
            db, "cartao_envio_falhou", usuario_id=ctx.usuario.id,
            tabela="apadrinhamentos", registro_id=apadrinhamento.id,
            detalhes={"erro": erro.mensagem, "codigo": erro.codigo},
        )
        db.commit()
        # 502: quem falhou foi a Meta, nao o pedido de quem clicou.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, envio.erro)

    envio.status = "enviado"
    envio.mensagem_id = enviado.mensagem_id
    db.add(envio)
    registrar(
        db, "cartao_enviado", usuario_id=ctx.usuario.id,
        tabela="apadrinhamentos", registro_id=apadrinhamento.id,
        detalhes={"telefone": telefone, "mensagem_id": enviado.mensagem_id},
    )
    db.commit()
    db.refresh(envio)

    return EnvioCartaoOut(
        apadrinhamento_id=apadrinhamento.id,
        status=envio.status,
        telefone=telefone,
        mensagem_id=envio.mensagem_id,
        enviado_em=envio.criado_em,
    )


@router.patch("/apadrinhamentos/{apadrinhamento_id}", response_model=PadrinhoOut)
def editar_apadrinhamento(
    apadrinhamento_id: int, dados: ApadrinhamentoEditar, db: BD, ctx: Editar
):
    apadrinhamento = db.get(Apadrinhamento, apadrinhamento_id)
    if apadrinhamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Apadrinhamento nao encontrado.")

    padrinho = _carregar(db, apadrinhamento.padrinho_id, ctx, "editar_padrinhos")

    if not _e_meu(ctx, db, apadrinhamento):
        raise HTTPException(status.HTTP_403_FORBIDDEN, DO_COLEGA)

    mudancas = dados.model_dump(exclude_unset=True)
    for campo, valor in mudancas.items():
        setattr(apadrinhamento, campo, valor)

    registrar(
        db, "apadrinhamento_editado", usuario_id=ctx.usuario.id,
        tabela="apadrinhamentos", registro_id=apadrinhamento.id,
        detalhes={"campos": sorted(mudancas)},
    )
    db.commit()
    return _saida(_carregar(db, padrinho.id, ctx, "editar_padrinhos"))


@router.delete("/apadrinhamentos/{apadrinhamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_apadrinhamento(apadrinhamento_id: int, db: BD, ctx: Editar):
    apadrinhamento = db.get(Apadrinhamento, apadrinhamento_id)
    if apadrinhamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Apadrinhamento nao encontrado.")

    _carregar(db, apadrinhamento.padrinho_id, ctx, "editar_padrinhos")

    if not _e_meu(ctx, db, apadrinhamento):
        raise HTTPException(status.HTTP_403_FORBIDDEN, DO_COLEGA)

    # Apadrinhamento pago so a coordenacao desfaz. Quem capta corrige o que
    # acabou de digitar; desfazer o que ja virou dinheiro e outra coisa.
    if apadrinhamento.pagamento_id is not None and not ctx.pode("excluir_padrinhos"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este apadrinhamento ja tem pagamento registrado. Peca a coordenacao "
            "para desfazer.",
        )

    # O PAGAMENTO fica. O dinheiro entrou de verdade — o que foi engano e a
    # crianca a que ele foi ligado. Apagar o pagamento junto sumiria com uma
    # entrada real do caixa; aqui ele so deixa de quitar este apadrinhamento, e
    # a diferenca aparece sozinha na ficha, entre o combinado e o pago.
    pagamento_solto = apadrinhamento.pagamento_id

    registrar(
        db, "apadrinhamento_apagado", usuario_id=ctx.usuario.id,
        tabela="apadrinhamentos", registro_id=apadrinhamento.id,
        detalhes={
            "crianca_id": apadrinhamento.crianca_id,
            "tipo": apadrinhamento.tipo,
            # Fica no log porque e o rastro de que sobrou dinheiro sem destino:
            # quem for conferir o caixa depois precisa achar este momento.
            "pagamento_que_ficou_sem_destino": pagamento_solto,
        },
    )
    db.delete(apadrinhamento)
    db.commit()


@router.get("/padrinhos/{padrinho_id}/dependencias", response_model=DependenciasOut)
def dependencias_do_padrinho(padrinho_id: int, db: BD, ctx: Excluir):
    """O que cai junto com este padrinho. E a conta que a janela mostra antes."""
    padrinho = _carregar(db, padrinho_id, ctx, "excluir_padrinhos")
    itens = exclusao.contar(db, exclusao.alcance_do_padrinho(padrinho_id))
    return DependenciasOut(
        id=padrinho.id,
        nome=padrinho.nome,
        total=sum(i.quantidade for i in itens),
        itens=itens,
    )


@router.delete("/padrinhos/{padrinho_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_padrinho(padrinho_id: int, db: BD, ctx: Excluir):
    """Apaga o cadastro do padrinho, com os apadrinhamentos e os pagamentos dele.

    As criancas NAO caem: elas continuam cadastradas e voltam a poder ser
    apadrinhadas — e esse o ponto de apagar um padrinho criado por engano.
    """
    padrinho = _carregar(db, padrinho_id, ctx, "excluir_padrinhos")

    registrar(
        db, "padrinho_apagado", usuario_id=ctx.usuario.id,
        tabela="padrinhos", registro_id=padrinho.id,
        detalhes={"nome": padrinho.nome, "edicao_id": padrinho.edicao_id},
    )
    orfaos = exclusao.apagar_padrinho(db, padrinho_id)
    db.commit()
    # Depois do commit: arquivo apagado nao volta, entao so sai do disco o que
    # ja saiu da base de verdade.
    exclusao.remover_arquivos(orfaos)


# ---------------------------------------------------------------- pagamentos

def _saida_pagamento(pagamento: Pagamento) -> PagamentoOut:
    return PagamentoOut(
        id=pagamento.id,
        padrinho_id=pagamento.padrinho_id,
        padrinho=pagamento.padrinho.nome,
        valor=pagamento.valor,
        data=pagamento.data,
        forma=pagamento.forma,
        observacoes=pagamento.observacoes,
        conferido=pagamento.conferido,
        comprovante_arquivo=pagamento.comprovante_arquivo,
        comprovante_drive_link=pagamento.comprovante_drive_link,
        apadrinhamentos=[a.id for a in pagamento.apadrinhamentos],
    )


def _ligar_apadrinhamentos(
    db: Session, pagamento: Pagamento, ids: list[int], padrinho: Padrinho,
    ctx: ContextoAcesso,
) -> None:
    """Deixa o pagamento quitando exatamente os apadrinhamentos pedidos."""
    desejados = set(ids)
    do_padrinho = {a.id for a in padrinho.apadrinhamentos}

    fora = desejados - do_padrinho
    if fora:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Ha apadrinhamentos que nao sao deste padrinho.",
        )

    # Quitar o apadrinhamento do colega E mexer nele: era promessa e vira
    # apadrinhamento confirmado, e o numero muda no nome de quem registrou.
    # O comissario de base so quita os proprios. Quando o padrinho paga tudo
    # de uma vez, quem fecha a conta e quem coordena a captacao.
    do_colega = [
        a for a in padrinho.apadrinhamentos
        if a.id in desejados and not _e_meu(ctx, db, a)
    ]
    if do_colega:
        raise HTTPException(status.HTTP_403_FORBIDDEN, DO_COLEGA)

    ja_quitados = db.scalars(
        select(Apadrinhamento).where(
            Apadrinhamento.id.in_(desejados),
            Apadrinhamento.pagamento_id.is_not(None),
            Apadrinhamento.pagamento_id != pagamento.id,
        )
    ).all()
    if ja_quitados:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ha apadrinhamentos ja quitados por outro pagamento.",
        )

    for a in padrinho.apadrinhamentos:
        if a.id in desejados:
            a.pagamento_id = pagamento.id
        elif a.pagamento_id == pagamento.id:
            a.pagamento_id = None


@router.get("/pagamentos", response_model=PaginaPagamentos)
def listar_pagamentos(
    db: BD,
    ctx: Pagar,
    padrinho_id: int | None = None,
    conferido: bool | None = None,
    comprovante: bool | None = None,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
):
    condicao = Pagamento.padrinho_id.in_(
        select(Padrinho.id).where(_filtro_padrinhos(ctx, "registrar_pagamentos_padrinho"))
    )
    if padrinho_id is not None:
        condicao = condicao & (Pagamento.padrinho_id == padrinho_id)
    if conferido is not None:
        condicao = condicao & (Pagamento.conferido.is_(conferido))
    # Quem cobra comprovante precisa achar os que ainda nao tem. O filtro olha
    # o arquivo no disco, e nao a copia no Drive: o disco e o original, e o
    # Drive pode estar desligado sem que falte comprovante nenhum.
    if comprovante is not None:
        condicao = condicao & (
            Pagamento.comprovante_arquivo.is_not(None)
            if comprovante
            else Pagamento.comprovante_arquivo.is_(None)
        )

    total = db.scalar(select(func.count()).select_from(Pagamento).where(condicao)) or 0

    itens = db.scalars(
        select(Pagamento)
        .where(condicao)
        .options(joinedload(Pagamento.padrinho), selectinload(Pagamento.apadrinhamentos))
        .order_by(Pagamento.data.desc(), Pagamento.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).unique().all()

    return PaginaPagamentos(
        total=total, pagina=pagina, por_pagina=por_pagina,
        itens=[_saida_pagamento(p) for p in itens],
    )


@router.post("/pagamentos", response_model=PagamentoOut, status_code=status.HTTP_201_CREATED)
def criar_pagamento(dados: PagamentoIn, db: BD, ctx: Pagar):
    padrinho = _carregar(db, dados.padrinho_id, ctx, "registrar_pagamentos_padrinho")

    pagamento = Pagamento(
        padrinho_id=padrinho.id,
        valor=dados.valor,
        data=dados.data,
        forma=dados.forma,
        observacoes=dados.observacoes,
        registrado_por=ctx.usuario.id,
    )
    db.add(pagamento)
    db.flush()

    _ligar_apadrinhamentos(db, pagamento, dados.apadrinhamentos, padrinho, ctx)

    registrar(
        db, "pagamento_registrado", usuario_id=ctx.usuario.id,
        tabela="pagamentos", registro_id=pagamento.id,
        detalhes={
            "padrinho_id": padrinho.id, "valor": str(dados.valor),
            "apadrinhamentos": dados.apadrinhamentos,
        },
    )
    db.commit()
    db.refresh(pagamento)
    return _saida_pagamento(pagamento)


@router.patch("/pagamentos/{pagamento_id}", response_model=PagamentoOut)
def editar_pagamento(pagamento_id: int, dados: PagamentoEditar, db: BD, ctx: Pagar):
    pagamento = db.get(Pagamento, pagamento_id)
    if pagamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pagamento nao encontrado.")

    padrinho = _carregar(db, pagamento.padrinho_id, ctx, "registrar_pagamentos_padrinho")

    mudancas = dados.model_dump(exclude_unset=True)
    apadrinhamentos = mudancas.pop("apadrinhamentos", None)

    # Conferir e o ato de auditoria: diz que alguem olhou o comprovante e bateu
    # com o dinheiro. Quem registrou o pagamento nao pode se auto-conferir, ou a
    # conferencia nao verifica nada.
    if "conferido" in mudancas and not ctx.pode("registrar_pagamentos"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Conferir um pagamento e da coordenacao. Voce pode registrar o "
            "pagamento e subir o comprovante; a conferencia e feita por quem "
            "cuida do financeiro da edicao.",
        )

    for campo, valor in mudancas.items():
        setattr(pagamento, campo, valor)

    if apadrinhamentos is not None:
        _ligar_apadrinhamentos(db, pagamento, apadrinhamentos, padrinho, ctx)

    registrar(
        db, "pagamento_editado", usuario_id=ctx.usuario.id,
        tabela="pagamentos", registro_id=pagamento.id,
        detalhes={"campos": sorted(dados.model_dump(exclude_unset=True))},
    )
    db.commit()
    db.refresh(pagamento)
    return _saida_pagamento(pagamento)


@router.delete("/pagamentos/{pagamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_pagamento(pagamento_id: int, db: BD, ctx: Auditar):
    pagamento = db.get(Pagamento, pagamento_id)
    if pagamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pagamento nao encontrado.")

    _carregar(db, pagamento.padrinho_id, ctx, "registrar_pagamentos")

    # Solta os apadrinhamentos que ele quitava, senao ficariam apontando para
    # um pagamento que nao existe mais.
    for a in pagamento.apadrinhamentos:
        a.pagamento_id = None

    # O comprovante sai do disco junto: sem a linha, ninguem mais alcanca o
    # arquivo, e ele ficaria ocupando lugar para sempre.
    comprovantes.apagar_arquivo(pagamento)

    registrar(
        db, "pagamento_apagado", usuario_id=ctx.usuario.id,
        tabela="pagamentos", registro_id=pagamento.id,
        detalhes={"valor": str(pagamento.valor)},
    )
    db.delete(pagamento)
    db.commit()


# ------------------------------------------------------------- comprovantes
#
# O trabalho de guardar, trocar, espelhar no Drive e entregar o arquivo vive em
# servicos/comprovantes.py, compartilhado com os recebimentos do financeiro: as
# duas origens guardam os mesmos tres campos e merecem o mesmo cuidado. Aqui
# fica so o que e do pagamento — quem pode, e qual edicao nomeia o arquivo.


@router.post("/pagamentos/{pagamento_id}/comprovante", response_model=PagamentoOut)
async def subir_comprovante(
    pagamento_id: int,
    db: BD,
    ctx: Pagar,
    arquivo: UploadFile = File(...),
):
    """Guarda o comprovante deste pagamento.

    Fica separado do POST /pagamentos de proposito: o pagamento e o vinculo
    com os apadrinhamentos sao a parte que nao pode falhar, e misturar o
    upload nela faria um arquivo grande demais derrubar a quitacao junto.
    Sem comprovante o pagamento existe; o comprovante entra depois, e pode ser
    trocado quantas vezes for preciso.
    """
    pagamento = db.get(Pagamento, pagamento_id)
    if pagamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pagamento nao encontrado.")

    padrinho = _carregar(db, pagamento.padrinho_id, ctx, "registrar_pagamentos_padrinho")

    await comprovantes.guardar(
        db, pagamento, arquivo,
        cidade=padrinho.edicao.cidade.nome,
        ano=padrinho.edicao.ano,
        titular=padrinho.nome,
        data=pagamento.data,
        tabela="pagamentos",
        usuario_id=ctx.usuario.id,
    )

    db.commit()
    db.refresh(pagamento)
    return _saida_pagamento(pagamento)


@router.get("/pagamentos/{pagamento_id}/comprovante")
def baixar_comprovante(pagamento_id: int, db: BD, ctx: Pagar):
    """Devolve o comprovante. Unica porta para o arquivo, sempre autenticada."""
    pagamento = db.get(Pagamento, pagamento_id)
    if pagamento is None:
        raise comprovantes.NAO_ENCONTRADO

    _carregar(db, pagamento.padrinho_id, ctx, "registrar_pagamentos_padrinho")
    return comprovantes.entregar(pagamento)
