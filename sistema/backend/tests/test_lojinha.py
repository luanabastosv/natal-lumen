"""Testa a copia das vendas da lojinha (Shopify) para os recebimentos.

Nao fala com o Shopify de verdade: a lista de pedidos vem de uma loja de
mentira. Usa o banco local, com nomes de teste, e apaga tudo no fim.

O que precisa ficar provado: so pedido pago e de verdade entra, pelo valor que
o cliente pagou; o mesmo pedido nunca entra duas vezes; o estorno e o
cancelamento na loja chegam aqui; a venda da campanha do ano passado nao cai
na edicao deste ano; e a linha da lojinha nao se edita nem se remove na mao.

Rodar com:  python -m tests.test_lojinha
"""

from copy import deepcopy
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    Cidade,
    Edicao,
    LogAtividade,
    Perfil,
    Recebimento,
    TokenAcesso,
    Usuario,
    UsuarioEdicao,
)
from app.seguranca.senhas import gerar_hash
from app.servicos import lojinha, shopify

MARCA = "ZZ_LOJINHA"
SENHA = "senha-de-teste-123"
HOJE = date(2026, 11, 23)

ok = 0
falhas: list[str] = []


def verifica(d: str, c: bool, extra: str = "") -> None:
    global ok
    if c:
        ok += 1
        print(f"  ok    {d}")
    else:
        falhas.append(d)
        print(f"  FALHA {d} {extra}")


def pedido(n, criado, valor, status="PAID", test=False, cancelado=None, itens=None,
           nome="Maria Compradora"):
    return {
        "id": f"gid://shopify/Order/{MARCA}{n}",
        "name": f"#{n}",
        "createdAt": criado,
        "test": test,
        "cancelledAt": cancelado,
        "displayFinancialStatus": status,
        "paymentGatewayNames": ["Mercado Pago Checkout Pro"],
        "currentTotalPriceSet": {"shopMoney": {"amount": valor, "currencyCode": "BRL"}},
        "billingAddress": {"name": nome},
        "lineItems": {"nodes": itens or [{"title": "Blusa NL26", "quantity": 1}]},
    }


class LojaDeMentira:
    """Faz o papel de shopify.consultar, em paginas de dois pedidos."""

    def __init__(self, pedidos):
        self.pedidos = pedidos
        self.buscas: list[str] = []
        self.erro = ""

    def consultar(self, documento, variaveis=None):
        if self.erro:
            raise shopify.ErroShopify(self.erro)
        self.buscas.append(variaveis["busca"])
        inicio = int(variaveis.get("depois") or 0)
        pagina = self.pedidos[inicio:inicio + 2]
        fim = inicio + 2
        return {"data": {"orders": {
            "pageInfo": {"hasNextPage": fim < len(self.pedidos), "endCursor": str(fim)},
            "nodes": deepcopy(pagina),
        }}}


def limpar(db, log_inicial: int = 0) -> None:
    db.rollback()
    db.execute(delete(LogAtividade).where(LogAtividade.id > log_inicial))
    db.execute(delete(Recebimento).where(Recebimento.shopify_pedido_id.like(f"%{MARCA}%")))
    ids = [u.id for u in db.scalars(select(Usuario).where(Usuario.nome.ilike(f"{MARCA}%"))).all()]
    if ids:
        db.execute(delete(TokenAcesso).where(TokenAcesso.usuario_id.in_(ids)))
    cids = [c.id for c in db.scalars(select(Cidade).where(Cidade.nome.ilike(f"{MARCA}%"))).all()]
    if cids:
        eds = list(db.scalars(select(Edicao.id).where(Edicao.cidade_id.in_(cids))).all())
        if eds:
            db.execute(delete(Recebimento).where(Recebimento.edicao_id.in_(eds)))
            db.execute(delete(UsuarioEdicao).where(UsuarioEdicao.edicao_id.in_(eds)))
            db.execute(delete(Edicao).where(Edicao.id.in_(eds)))
        db.execute(delete(Cidade).where(Cidade.id.in_(cids)))
    if ids:
        db.execute(delete(Usuario).where(Usuario.id.in_(ids)))
    db.commit()


def entrar(cliente: TestClient, email: str):
    r = cliente.post("/auth/login", json={"email": email, "senha": SENHA})
    if r.status_code == 200:
        for nome in (config.cookie_nome, config.cookie_csrf):
            valor = next((ck.value for ck in cliente.cookies.jar if ck.name == nome), None)
            if valor:
                cliente.cookies.set(nome, valor, path="/")
        cliente.headers["X-CSRF-Token"] = next(
            ck.value for ck in cliente.cookies.jar if ck.name == config.cookie_csrf
        )
    return r


def da_lojinha(db, edicao_id):
    db.expire_all()
    return {
        r.shopify_pedido_numero: r
        for r in db.scalars(
            select(Recebimento).where(
                Recebimento.edicao_id == edicao_id, Recebimento.categoria == "lojinha"
            )
        ).all()
    }


def main() -> None:
    db = SessionLocal()
    log_inicial = db.scalar(select(func.max(LogAtividade.id))) or 0
    limpar(db)
    perfis = {p.nome: p for p in db.scalars(select(Perfil)).all()}

    cidade = Cidade(nome=f"{MARCA} Fortaleza", uf="CE"); db.add(cidade); db.flush()
    ed = Edicao(cidade_id=cidade.id, ano=2026, nome=f"{MARCA} 2026", valor_cesta=130, valor_festa=60)
    db.add(ed); db.flush()

    def usuario(sufixo, perfil):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        db.add(UsuarioEdicao(usuario_id=u.id, edicao_id=ed.id, perfil_id=perfis[perfil].id))
        return u

    coord = usuario("Coord", "Coordenacao")
    comissario = usuario("Comissario", "Comissarios - comissario")
    db.commit()

    pedidos = [
        pedido(1, "2026-11-09T13:31:10Z", "90.0",
               itens=[{"title": "Blusa NL26", "quantity": 1}, {"title": "Blusa NL26", "quantity": 1},
                      {"title": "Faixa", "quantity": 3}]),
        pedido(2, "2026-11-09T13:40:00Z", "45.0", test=True),
        pedido(3, "2026-11-10T10:00:00Z", "50.0", status="EXPIRED"),
        pedido(4, "2026-11-11T10:00:00Z", "45.0", cancelado="2026-11-11T12:00:00Z"),
        # Madrugada em UTC, ainda dia 14 em Fortaleza.
        pedido(5, "2026-11-15T02:30:00Z", "30.0", status="PARTIALLY_REFUNDED"),
        # Venda da campanha de 2025, que ainda vendia em janeiro.
        pedido(6, "2026-01-10T15:00:00Z", "60.0"),
    ]
    loja = LojaDeMentira(pedidos)
    configurado_antes, consultar_antes = shopify.configurado, shopify.consultar
    shopify.configurado = lambda: True
    shopify.consultar = loja.consultar

    try:
        print("\nregras")
        verifica("janeiro conta para a campanha do ano anterior",
                 lojinha.ano_da_campanha(date(2026, 1, 10)) == 2025)
        verifica("novembro conta para o proprio ano", lojinha.ano_da_campanha(date(2026, 11, 9)) == 2026)
        verifica("julho ja e a campanha nova", lojinha.ano_da_campanha(date(2026, 7, 1)) == 2026)

        print("\nprimeira copia")
        r = lojinha.copiar(db, forcar=True, hoje=HOJE, edicoes=[ed])
        verifica("copiou", r.copiou and r.erro is None, str(r))
        verifica("so o pedido pago e o estornado em parte entram", r.novos == 2, str(r))
        verifica("a venda da campanha passada fica de fora", r.sem_edicao == 1, str(r))
        verifica("pede so os ultimos 59 dias", loja.buscas[0] == "created_at:>=2026-09-25", loja.buscas[0])
        verifica("leu as tres paginas", len(loja.buscas) == 3, str(loja.buscas))
        linhas = da_lojinha(db, ed.id)
        verifica("entraram o #1 e o #5", set(linhas) == {"#1", "#5"}, str(set(linhas)))
        um = linhas["#1"]
        verifica("valor e o que o cliente pagou", str(um.valor) == "90.00", str(um.valor))
        verifica("descricao junta o mesmo produto", um.descricao == "Blusa NL26 (2) + Faixa (3)", um.descricao)
        verifica("comprador e a forma", um.doador == "Maria Compradora" and um.forma == "Mercado Pago")
        verifica("data em Fortaleza", linhas["#5"].data == date(2026, 11, 14), str(linhas["#5"].data))
        verifica("nasce sem conferir", um.conferido is False)

        print("\nde novo, sem mudar nada")
        r = lojinha.copiar(db, forcar=True, hoje=HOJE, edicoes=[ed])
        verifica("nada novo, nada duplicado",
                 (r.novos, r.atualizados, r.removidos, r.mudou) == (0, 0, 0, False), str(r))
        verifica("continuam duas linhas", len(da_lojinha(db, ed.id)) == 2)

        print("\nsem forcar, logo depois")
        r = lojinha.copiar(db, hoje=HOJE, edicoes=[ed])
        verifica("nem fala com o Shopify", r.copiou is False and r.erro is None, str(r))

        print("\npela tela")
        cc = TestClient(app); entrar(cc, coord.email)
        ck = TestClient(app); entrar(ck, comissario.email)

        verifica("comissario nao copia", ck.post("/recebimentos/lojinha").status_code == 403)

        lista = cc.get(f"/recebimentos?edicao_id={ed.id}").json()
        da_loja = [l for l in lista["itens"] if l["categoria"] == "lojinha"]
        verifica("as duas vendas na lista", len(da_loja) == 2, str(lista)[:300])
        verifica("o numero do pedido vem na linha",
                 {l["shopify_pedido_numero"] for l in da_loja} == {"#1", "#5"})
        verifica("quem lancou e a Lojinha", all(l["responsavel"] == "Lojinha" for l in da_loja))
        verifica("conta no total por categoria", lista["por_categoria"].get("lojinha") == "120.00",
                 str(lista["por_categoria"]))
        verifica("nao falta comprovante nelas", lista["sem_comprovante"] == 0, str(lista["sem_comprovante"]))
        filtrada = cc.get(f"/recebimentos?edicao_id={ed.id}&categoria=lojinha").json()
        verifica("o filtro lojinha acha as duas", filtrada["total"] == 2)

        rid = um.id
        r = cc.patch(f"/recebimentos/{rid}", json={"valor": "10.00"})
        verifica("nao edita o valor", r.status_code == 400, r.text)
        r = cc.patch(f"/recebimentos/{rid}", json={"conferido": True, "observacoes": "ok no extrato"})
        verifica("confere e anota", r.status_code == 200 and r.json()["conferido"] is True, r.text)
        verifica("nao remove", cc.delete(f"/recebimentos/{rid}").status_code == 400)
        r = cc.post(f"/recebimentos/{rid}/comprovante",
                    files={"arquivo": ("c.pdf", b"%PDF-1.4 teste", "application/pdf")})
        verifica("nao sobe comprovante", r.status_code == 400, r.text)

        print("\nestorno e cancelamento na loja")
        loja.pedidos[0]["currentTotalPriceSet"]["shopMoney"]["amount"] = "45.0"
        loja.pedidos[0]["displayFinancialStatus"] = "PARTIALLY_REFUNDED"
        loja.pedidos[4]["cancelledAt"] = "2026-11-20T10:00:00Z"
        r = lojinha.copiar(db, forcar=True, hoje=HOJE, edicoes=[ed])
        verifica("um atualizado, um removido", (r.atualizados, r.removidos) == (1, 1), str(r))
        linhas = da_lojinha(db, ed.id)
        verifica("o cancelado saiu", set(linhas) == {"#1"}, str(set(linhas)))
        verifica("o valor novo", str(linhas["#1"].valor) == "45.00", str(linhas["#1"].valor))
        verifica("valor mudou, volta a conferir", linhas["#1"].conferido is False)
        verifica("a observacao fica", linhas["#1"].observacoes == "ok no extrato")
        acoes = set(db.scalars(select(LogAtividade.acao).where(LogAtividade.id > log_inicial)).all())
        verifica("as duas mudancas no log",
                 {"lojinha_venda_atualizada", "lojinha_venda_removida"} <= acoes, str(acoes))

        print("\nShopify fora do ar")
        loja.erro = "Nao consegui falar com o Shopify agora"
        r = lojinha.copiar(db, forcar=True, hoje=HOJE, edicoes=[ed])
        verifica("volta o erro, sem levantar", r.erro and not r.copiou, str(r))
        verifica("nada sai do caixa", set(da_lojinha(db, ed.id)) == {"#1"})
        loja.erro = ""

        print("\nsem credenciais")
        shopify.configurado = lambda: False
        r = cc.post("/recebimentos/lojinha?forcar=true")
        verifica("diz que a loja nao esta ligada", r.status_code == 200 and r.json()["ligada"] is False, r.text)
    finally:
        shopify.configurado, shopify.consultar = configurado_antes, consultar_antes
        lojinha.esquecer_ultima_copia()
        limpar(db, log_inicial)
        db.close()

    print(f"\n{ok} ok, {len(falhas)} falha(s)")
    if falhas:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
