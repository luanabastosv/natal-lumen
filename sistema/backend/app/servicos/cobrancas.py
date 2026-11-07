"""O ciclo de um link de pagamento: reservar, receber, vencer.

Regra de 08/10/2026: apadrinhar exige o pagamento junto, porque a promessa
segurava a crianca para um padrinho que podia nunca pagar. O link do cartao e
uma excecao com PRAZO: a crianca fica reservada so enquanto o link vale
(config.mercadopago_link_minutos). Vencido sem pagamento, ela volta para a lista
de disponiveis sozinha.

Ninguem confirma o pagamento a mao. Quem diz que o dinheiro entrou e a API do
Mercado Pago, perguntada com o nosso token: pelo aviso (webhook) que ela manda,
pelo botao "Conferir pagamento", ou na hora de vencer, que pergunta uma ultima
vez antes de liberar as criancas.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Apadrinhamento, CobrancaCartao, Pagamento
from app.servicos import mercadopago
from app.servicos.log import registrar

FUSO = ZoneInfo("America/Sao_Paulo")

# O pagamento ainda pode virar aprovado: nao se liberam as criancas.
EM_ANDAMENTO = ("pending", "in_process", "authorized", "in_mediation")

FORMAS = {
    "credit_card": "Cartão",
    "debit_card": "Cartão",
    "prepaid_card": "Cartão",
    "bank_transfer": "Pix",
    "account_money": "Saldo Mercado Pago",
}


def agora() -> datetime:
    return datetime.now(timezone.utc)


def _data_do_pagamento(pagamento_mp: dict) -> date:
    texto = pagamento_mp.get("date_approved") or pagamento_mp.get("date_created")
    try:
        return datetime.fromisoformat(texto).astimezone(FUSO).date()
    except (TypeError, ValueError):
        return agora().astimezone(FUSO).date()


def _observacao(pagamento_mp: dict, cobranca: CobrancaCartao, valor: Decimal) -> str:
    partes = [f"Link do Mercado Pago, pagamento nº {pagamento_mp.get('id')}."]
    parcelas = pagamento_mp.get("installments")
    if parcelas and parcelas > 1:
        partes.append(f"Em {parcelas}x no cartão.")
    if valor != Decimal(str(cobranca.valor)):
        partes.append(f"O link cobrava R$ {cobranca.valor}; entrou R$ {valor}.")
    if cobranca.status in ("expirado", "cancelado"):
        partes.append(
            "Pago depois que o link tinha sido encerrado: as crianças já tinham "
            "sido liberadas. A coordenação decide o destino deste dinheiro."
        )
    return " ".join(partes)


def aplicar(db: Session, cobranca: CobrancaCartao, pagamento_mp: dict) -> bool:
    """Registra o que o Mercado Pago informou sobre esta cobranca.

    Devolve True quando um pagamento novo entrou no caixa. Nao faz commit.
    Quem chama ja travou a linha da cobranca (SELECT ... FOR UPDATE): o aviso
    do Mercado Pago e o botao de conferir podem chegar juntos.
    """
    if str(pagamento_mp.get("external_reference")) != cobranca.referencia:
        return False
    estado = pagamento_mp.get("status")
    cobranca.status_mercadopago = estado
    if estado != "approved" or cobranca.pagamento_id is not None:
        return False

    mp_id = str(pagamento_mp["id"])
    if db.scalar(select(Pagamento.id).where(Pagamento.mercadopago_id == mp_id)):
        return False

    valor = Decimal(str(pagamento_mp.get("transaction_amount") or cobranca.valor)).quantize(
        Decimal("0.01")
    )
    pagamento = Pagamento(
        padrinho_id=cobranca.padrinho_id,
        valor=valor,
        data=_data_do_pagamento(pagamento_mp),
        forma=FORMAS.get(pagamento_mp.get("payment_type_id"), "Mercado Pago"),
        observacoes=_observacao(pagamento_mp, cobranca, valor),
        registrado_por=cobranca.criado_por,
        mercadopago_id=mp_id,
    )
    db.add(pagamento)
    db.flush()

    # So as reservas que ainda existem: alguem pode ter desfeito uma crianca
    # do link no meio do caminho.
    reservas = db.scalars(
        select(Apadrinhamento).where(
            Apadrinhamento.cobranca_id == cobranca.id,
            Apadrinhamento.pagamento_id.is_(None),
        )
    ).all()
    for a in reservas:
        a.pagamento_id = pagamento.id

    cobranca.pagamento_id = pagamento.id
    cobranca.status = "pago" if cobranca.status == "aguardando" else "pago_apos_vencer"
    cobranca.encerrada_em = cobranca.encerrada_em or agora()

    registrar(
        db, "pagamento_registrado", usuario_id=cobranca.criado_por,
        tabela="pagamentos", registro_id=pagamento.id,
        detalhes={
            "padrinho_id": cobranca.padrinho_id, "valor": str(valor),
            "apadrinhamentos": [a.id for a in reservas],
            "origem": "mercadopago", "mercadopago_id": mp_id,
            "cobranca_id": cobranca.id,
        },
    )
    return True


def liberar(db: Session, cobranca: CobrancaCartao, novo_status: str, usuario_id: int | None):
    """Encerra o link sem pagamento: as criancas voltam a ficar livres."""
    reservas = db.scalars(
        select(Apadrinhamento).where(
            Apadrinhamento.cobranca_id == cobranca.id,
            Apadrinhamento.pagamento_id.is_(None),
        )
    ).all()
    for a in reservas:
        db.delete(a)
    cobranca.status = novo_status
    cobranca.encerrada_em = agora()
    registrar(
        db, f"link_de_pagamento_{novo_status}", usuario_id=usuario_id,
        tabela="cobrancas_cartao", registro_id=cobranca.id,
        detalhes={
            "padrinho_id": cobranca.padrinho_id,
            "criancas_liberadas": [
                {"crianca_id": a.crianca_id, "tipo": a.tipo} for a in reservas
            ],
        },
    )


def _travar(db: Session, cobranca_id: int) -> CobrancaCartao | None:
    return db.scalar(
        select(CobrancaCartao)
        .where(CobrancaCartao.id == cobranca_id)
        .with_for_update()
        # Rele do banco: a copia na sessao pode ser de antes de outro pedido
        # mexer nesta linha.
        .execution_options(populate_existing=True)
    )


def conferir(db: Session, cobranca_id: int) -> CobrancaCartao:
    """Pergunta ao Mercado Pago se este link ja foi pago, e grava. Faz commit.

    Levanta ErroMercadoPago se a API nao responde.
    """
    cobranca = db.get(CobrancaCartao, cobranca_id)
    resultados = mercadopago.pagamentos_da_referencia(cobranca.referencia)
    return _gravar_resultados(db, cobranca_id, resultados)


def _gravar_resultados(db: Session, cobranca_id: int, resultados: list[dict]) -> CobrancaCartao:
    cobranca = _travar(db, cobranca_id)
    aprovado = next((p for p in resultados if p.get("status") == "approved"), None)
    try:
        if aprovado:
            aplicar(db, cobranca, aprovado)
        elif resultados:
            cobranca.status_mercadopago = resultados[0].get("status")
        db.commit()
    except IntegrityError:
        # O mesmo pagamento entrou por outro caminho no mesmo instante.
        db.rollback()
    db.refresh(cobranca)
    return cobranca


def receber_aviso(db: Session, pagamento_mp_id: str) -> bool:
    """O aviso do Mercado Pago: le o pagamento NA API e aplica. Faz commit.

    O corpo do aviso nao e usado para nada alem do numero do pagamento.
    """
    pagamento_mp = mercadopago.buscar_pagamento(pagamento_mp_id)
    referencia = pagamento_mp.get("external_reference")
    if not referencia:
        return False
    cobranca_id = db.scalar(
        select(CobrancaCartao.id).where(CobrancaCartao.referencia == str(referencia))
    )
    if cobranca_id is None:
        # Pagamento da lojinha, ou de outra integracao da mesma conta.
        return False
    cobranca = _travar(db, cobranca_id)
    try:
        entrou = aplicar(db, cobranca, pagamento_mp)
        db.commit()
    except IntegrityError:
        db.rollback()
        entrou = False
    return entrou


def expirar_vencidas(db: Session) -> int:
    """Libera as criancas dos links vencidos. Faz commit se mexeu em algo.

    Antes de liberar, pergunta ao Mercado Pago uma ultima vez: um aviso perdido
    nao pode custar a crianca de quem pagou. Se o Mercado Pago nao responde, ou
    o pagamento ainda esta em analise, a reserva fica para a proxima rodada.
    Chamada pelas telas que mostram quem esta livre (lista de criancas,
    apadrinhar), entao custa uma consulta quando nao ha nada vencido.
    """
    vencidas = db.scalars(
        select(CobrancaCartao.id).where(
            CobrancaCartao.status == "aguardando",
            CobrancaCartao.expira_em < agora(),
        )
    ).all()
    liberadas = 0
    for cobranca_id in vencidas:
        resultados = None
        if mercadopago.configurado():
            cobranca = db.get(CobrancaCartao, cobranca_id)
            try:
                resultados = mercadopago.pagamentos_da_referencia(cobranca.referencia)
            except mercadopago.ErroMercadoPago:
                continue
        cobranca = _travar(db, cobranca_id)
        if cobranca is None or cobranca.status != "aguardando":
            db.rollback()
            continue
        aprovado = next((p for p in resultados or [] if p.get("status") == "approved"), None)
        try:
            if aprovado:
                aplicar(db, cobranca, aprovado)
            elif any(p.get("status") in EM_ANDAMENTO for p in resultados or []):
                db.rollback()
                continue
            else:
                liberar(db, cobranca, "expirado", None)
                liberadas += 1
            db.commit()
        except IntegrityError:
            db.rollback()
    return liberadas
