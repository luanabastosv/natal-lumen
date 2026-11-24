"""As vendas da lojinha no Shopify, copiadas para os recebimentos.

Cada pedido PAGO da loja vira uma linha de `recebimentos` com a categoria
'lojinha', e a partir dai e um recebimento como os outros: soma no caixa,
aparece no "De onde veio", filtra e se confere.

Copiado, e nao lido ao vivo a cada abertura da tela, porque o Shopify so deixa
o app ler os pedidos dos ULTIMOS 60 DIAS (falta o escopo read_all_orders). Lida
ao vivo, a venda de outubro sumiria do caixa em dezembro.

As regras:

  valor     o que o cliente pagou: o total atual do pedido, com frete e ja
            sem o que foi estornado. A taxa do Shopify e do gateway nao sai
            daqui.
  entra     pedido pago (ou pago e estornado em parte), que nao e de teste e
            nao foi cancelado. O Pix que expirou sem pagar nunca entra.
  sai       o pedido que ja estava copiado e depois foi cancelado, estornado
            inteiro ou marcado como teste: deixou de ser dinheiro que entrou.
  edicao    a do ANO DA CAMPANHA do pedido. A campanha de um ano vende de
            julho a junho do ano seguinte (a de 2025 vendeu de novembro de
            2025 ate janeiro de 2026), entao o pedido de janeiro conta para o
            ano anterior. So entra se houver exatamente UMA edicao naquele
            ano: com duas, nao ha como saber de qual cidade foi a venda, e o
            pedido fica de fora em vez de cair na errada.

A copia roda quando a tela do financeiro abre (no maximo uma vez a cada
INTERVALO, para nao bater no Shopify a cada clique) e pelo botao de atualizar.
"""

import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Edicao, Recebimento
from app.models.tipos import CATEGORIA_LOJINHA
from app.servicos import shopify
from app.servicos.log import registrar

FUSO = ZoneInfo("America/Fortaleza")

# Quanto o Shopify deixa ler para tras. Um dia de folga a menos, para o filtro
# nunca pedir alem do que a loja entrega.
JANELA_DIAS = 59

# Entre duas copias automaticas. O botao de atualizar ignora.
INTERVALO_S = 300

POR_PAGINA = 30

PAGOS = {"PAID", "PARTIALLY_REFUNDED"}

CONSULTA = """
query Pedidos($depois: String, $busca: String!) {
  orders(first: %d, after: $depois, query: $busca, sortKey: CREATED_AT) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      name
      createdAt
      test
      cancelledAt
      displayFinancialStatus
      paymentGatewayNames
      currentTotalPriceSet { shopMoney { amount currencyCode } }
      billingAddress { name }
      lineItems(first: 20) { nodes { title quantity } }
    }
  }
}
""" % POR_PAGINA

_trava = threading.Lock()
_ultima_copia = {"em": 0.0}


@dataclass
class Resultado:
    ligada: bool = True
    copiou: bool = False
    novos: int = 0
    atualizados: int = 0
    removidos: int = 0
    # Pedidos pagos que ficaram de fora por nao haver uma edicao so no ano da
    # campanha deles.
    sem_edicao: int = 0
    erro: str | None = None
    mudou: bool = False


def ano_da_campanha(dia: date) -> int:
    return dia.year if dia.month >= 7 else dia.year - 1


def _dia_local(momento: str) -> date:
    return datetime.fromisoformat(momento.replace("Z", "+00:00")).astimezone(FUSO).date()


def _forma(gateways: list[str]) -> str | None:
    if not gateways:
        return None
    nome = gateways[0]
    if nome.lower().startswith("mercado pago"):
        return "Mercado Pago"
    if nome.lower() == "manual":
        return "Manual"
    return nome[:40]


def _descricao(pedido: dict) -> str:
    """"Blusa NL26 - Tirinha (2) + Faixa (1)", juntando o mesmo produto."""
    conta: Counter[str] = Counter()
    for item in (pedido.get("lineItems") or {}).get("nodes") or []:
        conta[item.get("title") or "Produto"] += int(item.get("quantity") or 0)
    if not conta:
        return "Venda da lojinha"
    texto = " + ".join(f"{titulo} ({qtd})" for titulo, qtd in conta.items())
    return texto if len(texto) <= 255 else texto[:252] + "..."


def _valor(pedido: dict) -> Decimal | None:
    dinheiro = ((pedido.get("currentTotalPriceSet") or {}).get("shopMoney")) or {}
    if dinheiro.get("currencyCode") not in (None, "BRL"):
        return None
    try:
        return Decimal(str(dinheiro.get("amount"))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return None


def _conta_como_recebido(pedido: dict) -> bool:
    valor = _valor(pedido)
    return (
        not pedido.get("test")
        and not pedido.get("cancelledAt")
        and pedido.get("displayFinancialStatus") in PAGOS
        and valor is not None
        and valor > 0
    )


def _pedidos(desde: date) -> list[dict]:
    pedidos: list[dict] = []
    depois = None
    while True:
        resposta = shopify.consultar(
            CONSULTA, {"depois": depois, "busca": f"created_at:>={desde.isoformat()}"}
        )
        if resposta.get("errors"):
            mensagem = "; ".join(e.get("message", "") for e in resposta["errors"])
            raise shopify.ErroShopify(f"O Shopify recusou a lista de pedidos: {mensagem}")
        pagina = resposta["data"]["orders"]
        pedidos += pagina["nodes"]
        if not pagina["pageInfo"]["hasNextPage"]:
            return pedidos
        depois = pagina["pageInfo"]["endCursor"]


def _edicao_por_ano(db: Session, edicoes: list[Edicao] | None):
    """ano -> id da edicao, so para os anos com UMA edicao."""
    todas = edicoes if edicoes is not None else db.scalars(select(Edicao)).all()
    por_ano: dict[int, list[int]] = {}
    for e in todas:
        por_ano.setdefault(e.ano, []).append(e.id)
    return {ano: ids[0] for ano, ids in por_ano.items() if len(ids) == 1}


def copiar(
    db: Session,
    *,
    forcar: bool = False,
    hoje: date | None = None,
    edicoes: list[Edicao] | None = None,
) -> Resultado:
    """Traz as vendas da lojinha para os recebimentos. Nunca levanta erro do
    Shopify: ele volta em `erro`, e a tela segue com o que ja estava copiado.

    `edicoes` restringe as edicoes candidatas (os testes usam, para nao
    disputar o ano com a edicao de verdade do banco local)."""
    if not shopify.configurado():
        return Resultado(ligada=False)

    with _trava:
        if not forcar and time.monotonic() - _ultima_copia["em"] < INTERVALO_S:
            return Resultado()
        hoje = hoje or datetime.now(FUSO).date()
        try:
            pedidos = _pedidos(hoje - timedelta(days=JANELA_DIAS))
        except shopify.ErroShopify as erro:
            return Resultado(erro=str(erro))

        resultado = Resultado(copiou=True)
        edicao_do_ano = _edicao_por_ano(db, edicoes)
        ids = [p["id"] for p in pedidos]
        copiados = {
            r.shopify_pedido_id: r
            for r in db.scalars(
                select(Recebimento)
                .where(Recebimento.shopify_pedido_id.in_(ids))
                # Le do banco mesmo o que a sessao ja tinha: a conferencia
                # pode ter mudado por outra rota.
                .execution_options(populate_existing=True)
            ).all()
        } if ids else {}

        for pedido in pedidos:
            ja = copiados.get(pedido["id"])

            if not _conta_como_recebido(pedido):
                if ja is not None:
                    registrar(
                        db, "lojinha_venda_removida", tabela="recebimentos",
                        registro_id=ja.id,
                        detalhes={
                            "pedido": ja.shopify_pedido_numero,
                            "valor": str(ja.valor),
                            "status": pedido.get("displayFinancialStatus"),
                            "cancelado": bool(pedido.get("cancelledAt")),
                        },
                    )
                    db.delete(ja)
                    resultado.removidos += 1
                continue

            dia = _dia_local(pedido["createdAt"])
            comprador = ((pedido.get("billingAddress") or {}).get("name") or "").strip()
            dados = {
                "descricao": _descricao(pedido),
                "valor": _valor(pedido),
                "data": dia,
                "doador": comprador[:180] or None,
                "forma": _forma(pedido.get("paymentGatewayNames") or []),
                "shopify_pedido_numero": pedido.get("name"),
            }
            if ja is None:
                edicao_id = edicao_do_ano.get(ano_da_campanha(dia))
                if edicao_id is None:
                    resultado.sem_edicao += 1
                    continue
                novo = Recebimento(
                    edicao_id=edicao_id,
                    categoria=CATEGORIA_LOJINHA,
                    shopify_pedido_id=pedido["id"],
                    **dados,
                )
                db.add(novo)
                resultado.novos += 1
                continue

            mudancas = {
                campo: valor for campo, valor in dados.items()
                if getattr(ja, campo) != valor
            }
            if not mudancas:
                continue
            antes = {campo: str(getattr(ja, campo)) for campo in mudancas}
            for campo, valor in mudancas.items():
                setattr(ja, campo, valor)
            # Valor mudou (estorno parcial): a conferencia de antes era de
            # outro numero.
            if "valor" in mudancas:
                ja.conferido = False
            registrar(
                db, "lojinha_venda_atualizada", tabela="recebimentos", registro_id=ja.id,
                detalhes={
                    "pedido": ja.shopify_pedido_numero,
                    "antes": antes,
                    "depois": {campo: str(v) for campo, v in mudancas.items()},
                },
            )
            resultado.atualizados += 1

        db.commit()
        _ultima_copia["em"] = time.monotonic()
        resultado.mudou = bool(resultado.novos or resultado.atualizados or resultado.removidos)
        return resultado


def esquecer_ultima_copia() -> None:
    """Para os testes: a proxima copia roda mesmo sem `forcar`."""
    _ultima_copia["em"] = 0.0
