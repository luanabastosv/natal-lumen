"""Testa o link de pagamento do Mercado Pago, com a API do Mercado Pago simulada.

Rodar com:  python -m tests.test_mercadopago
"""

import hashlib
import hmac
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    Apadrinhamento,
    Cidade,
    CobrancaCartao,
    Crianca,
    Edicao,
    Instituicao,
    LogAtividade,
    Padrinho,
    Pagamento,
    Perfil,
    TokenAcesso,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.seguranca.senhas import gerar_hash
from app.servicos import cobrancas, mercadopago

MARCA = "ZZ_MP"
SENHA = "senha-de-teste-123"

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


# ------------------------------------------------- Mercado Pago de mentira

class Falso:
    """Guarda o que o sistema pediu e responde o que o teste mandar."""

    def __init__(self):
        self.preferencias: list[dict] = []
        self.pagamentos: dict[str, list[dict]] = {}  # referencia -> resultados
        self.por_id: dict[str, dict] = {}
        self.falhar = False
        self.encerradas: list[str] = []

    def criar_preferencia(self, **kw):
        if self.falhar:
            raise mercadopago.ErroMercadoPago("O Mercado Pago recusou o pedido: teste.")
        self.preferencias.append(kw)
        n = len(self.preferencias)
        return {"id": f"pref-{n}", "link": f"https://mp.teste/checkout/{n}"}

    def pagamentos_da_referencia(self, referencia):
        return list(self.pagamentos.get(referencia, []))

    def buscar_pagamento(self, pid):
        return self.por_id[pid]

    def encerrar_preferencia(self, pid, agora):
        self.encerradas.append(pid)

    def pagar(self, referencia, valor, status="approved", pid=None, tipo="credit_card"):
        pid = pid or str(900000 + len(self.por_id))
        pg = {
            "id": int(pid), "status": status, "external_reference": referencia,
            "transaction_amount": float(valor), "payment_type_id": tipo,
            "installments": 3, "date_approved": "2026-11-07T10:00:00.000-04:00",
        }
        self.por_id[pid] = pg
        self.pagamentos.setdefault(referencia, []).insert(0, pg)
        return pid


def limpar(db, log_inicial: int = 0) -> None:
    db.rollback()
    db.execute(delete(LogAtividade).where(LogAtividade.id > log_inicial))
    usuarios = db.scalars(select(Usuario).where(Usuario.nome.ilike(f"{MARCA}%"))).all()
    ids = [u.id for u in usuarios]
    if ids:
        db.execute(delete(TokenAcesso).where(TokenAcesso.usuario_id.in_(ids)))
    cids = [c.id for c in db.scalars(select(Cidade).where(Cidade.nome.ilike(f"{MARCA}%"))).all()]
    if cids:
        eds = list(db.scalars(select(Edicao.id).where(Edicao.cidade_id.in_(cids))).all())
        pads = list(db.scalars(select(Padrinho.id).where(Padrinho.edicao_id.in_(eds or [0]))).all())
        if pads:
            db.execute(delete(Apadrinhamento).where(Apadrinhamento.padrinho_id.in_(pads)))
            db.execute(delete(CobrancaCartao).where(CobrancaCartao.padrinho_id.in_(pads)))
            db.execute(delete(Pagamento).where(Pagamento.padrinho_id.in_(pads)))
            db.execute(delete(Padrinho).where(Padrinho.id.in_(pads)))
        db.execute(delete(Crianca).where(Crianca.edicao_id.in_(eds or [0])))
        vs = list(db.scalars(select(UsuarioEdicao.id).where(UsuarioEdicao.edicao_id.in_(eds or [0]))).all())
        if vs:
            db.execute(delete(UsuarioInstituicao).where(UsuarioInstituicao.usuario_edicao_id.in_(vs)))
            db.execute(delete(UsuarioEdicao).where(UsuarioEdicao.id.in_(vs)))
        db.execute(delete(Edicao).where(Edicao.id.in_(eds or [0])))
        db.execute(delete(Instituicao).where(Instituicao.cidade_id.in_(cids)))
        db.execute(delete(Cidade).where(Cidade.id.in_(cids)))
    if ids:
        db.execute(delete(LogAtividade).where(LogAtividade.usuario_id.in_(ids)))
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


def main() -> None:
    db = SessionLocal()
    log_inicial = db.scalar(select(func.max(LogAtividade.id))) or 0
    limpar(db)

    falso = Falso()
    originais = {
        nome: getattr(mercadopago, nome)
        for nome in ("criar_preferencia", "pagamentos_da_referencia", "buscar_pagamento",
                     "encerrar_preferencia")
    }
    for nome in originais:
        setattr(mercadopago, nome, getattr(falso, nome))
    token_original = config.mercadopago_access_token
    segredo_original = config.mercadopago_segredo_webhook
    config.mercadopago_access_token = "TEST-token-de-mentira"
    config.mercadopago_segredo_webhook = ""

    perfis = {p.nome: p for p in db.scalars(select(Perfil)).all()}
    c1 = Cidade(nome=f"{MARCA} Fortaleza", uf="CE")
    db.add(c1); db.flush()
    e1 = Edicao(cidade_id=c1.id, ano=2026, nome=f"{MARCA} Fortaleza 2026", valor_cesta=120, valor_festa=60)
    db.add(e1); db.flush()
    i1 = Instituicao(cidade_id=c1.id, nome=f"{MARCA} Escola A")
    db.add(i1); db.flush()

    def usuario(sufixo, perfil, instituicoes=()):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        v = UsuarioEdicao(usuario_id=u.id, edicao_id=e1.id, perfil_id=perfis[perfil].id)
        db.add(v); db.flush()
        for inst in instituicoes:
            db.add(UsuarioInstituicao(usuario_edicao_id=v.id, instituicao_id=inst))
        return u

    comissario = usuario("Comissario", "Comissarios - comissario", [i1.id])
    colega = usuario("Colega", "Comissarios - comissario", [i1.id])
    coord = usuario("Coord", "Coordenacao")

    criancas = []
    for n, nome in enumerate(["Ana Avila", "Bruno Lima", "Carla Souza", "Davi Reis", "Eva Melo"], 1):
        c = Crianca(edicao_id=e1.id, instituicao_id=i1.id, codigo=f"00{n}", nome=nome,
                    idade=8, sexo="F", comissario_id=comissario.id)
        criancas.append(c)
    db.add_all(criancas); db.commit()
    ana, bruno, carla, davi, eva = criancas

    def link(cliente, padrinho_id, *pares):
        return cliente.post(f"/padrinhos/{padrinho_id}/link-de-pagamento", json={
            "criancas": [{"crianca_id": c.id, "tipo": t} for c, t in pares],
        })

    def cobranca(cid):
        db.expire_all()
        return db.get(CobrancaCartao, cid)

    def reservas(crianca):
        db.expire_all()
        return db.scalars(select(Apadrinhamento).where(Apadrinhamento.crianca_id == crianca.id)).all()

    try:
        ck = TestClient(app); entrar(ck, comissario.email)
        ccol = TestClient(app); entrar(ccol, colega.email)
        cc = TestClient(app); entrar(cc, coord.email)
        anonimo = TestClient(app)

        r = ck.post("/padrinhos", json={"edicao_id": e1.id, "nome": "Jose Cartao",
                                        "email": "jose@exemplo.org"})
        jose = r.json()["id"]
        r = cc.post("/padrinhos", json={"edicao_id": e1.id, "nome": "Maria Outra"})
        maria = r.json()["id"]

        print("\nGerar o link")
        r = ck.get("/mercadopago/situacao")
        verifica("a tela sabe que o link esta ligado", r.json().get("ligado") is True, r.text)

        r = link(ck, jose, (ana, "cesta"), (bruno, "cesta"))
        verifica("comissario gera o link", r.status_code == 201, r.text[:200])
        corpo = r.json()
        l1 = corpo.get("ultimo_link") or {}
        verifica("devolve o link do Mercado Pago", l1.get("link", "").startswith("https://mp.teste/"), str(l1))
        verifica("o valor e a soma das cestas", l1.get("valor") == "240.00", str(l1.get("valor")))
        verifica("o link aparece aberto na ficha", len(corpo.get("links_abertos", [])) == 1)
        verifica("as criancas aparecem aguardando o link",
                 all(a["aguardando_link"] and not a["pago"] for a in corpo["apadrinhamentos"]))
        pedido = falso.preferencias[-1]
        verifica("nome de crianca nao vai para o Mercado Pago",
                 "Ana" not in pedido["titulo"] and pedido["titulo"] == "Natal Lumen: 2 cestas",
                 pedido["titulo"])
        verifica("o email do padrinho vai para preencher o formulario",
                 pedido["padrinho_email"] == "jose@exemplo.org")
        verifica("sem url publica, nao manda endereco de aviso", pedido["url_aviso"] is None)

        r = ck.get("/criancas", params={"edicao_id": e1.id, "por_pagina": 200})
        a_lista = {c["id"]: c for c in r.json()["itens"]}
        verifica("na lista, a crianca fica reservada (nao livre, nao apadrinhada)",
                 a_lista[ana.id]["promessa_cesta"] and not a_lista[ana.id]["tem_padrinho_cesta"],
                 str(a_lista[ana.id]))

        r = cc.post(f"/padrinhos/{maria}/apadrinhar", json={
            "criancas": [{"crianca_id": ana.id, "tipo": "cesta"}], "data": "2026-11-07", "forma": "Pix"})
        verifica("outro padrinho nao leva a crianca reservada", r.status_code == 409, r.text[:150])

        falso.falhar = True
        r = link(ck, jose, (carla, "cesta"))
        falso.falhar = False
        verifica("se o Mercado Pago falha, responde 502", r.status_code == 502, r.text[:150])
        verifica("e nada fica gravado", reservas(carla) == [])

        print("\nConferir e receber")
        r = ck.post(f"/cobrancas/{l1['id']}/conferir")
        verifica("conferir sem pagamento deixa aguardando",
                 r.status_code == 200 and r.json()["ultimo_link"]["status"] == "aguardando", r.text[:150])

        r = ccol.post(f"/cobrancas/{l1['id']}/conferir")
        verifica("o colega nao mexe no link do outro", r.status_code == 403, str(r.status_code))

        ref1 = cobranca(l1["id"]).referencia
        pid = falso.pagar(ref1, 240)
        r = anonimo.post(f"/mercadopago/notificacoes?data.id={pid}&type=payment",
                         json={"type": "payment", "action": "payment.updated", "data": {"id": pid}})
        verifica("o aviso do Mercado Pago e aceito", r.status_code == 200, r.text[:150])
        c = cobranca(l1["id"])
        verifica("o link fica pago", c.status == "pago", c.status)
        pg = db.get(Pagamento, c.pagamento_id) if c.pagamento_id else None
        verifica("o pagamento entra com o numero do Mercado Pago",
                 pg is not None and pg.mercadopago_id == pid and str(pg.valor) == "240.00")
        verifica("forma Cartao, data no fuso de Sao Paulo",
                 pg is not None and pg.forma == "Cartão" and str(pg.data) == "2026-11-07",
                 f"{pg and pg.forma} {pg and pg.data}")
        verifica("registrado em nome de quem gerou o link", pg is not None and pg.registrado_por == comissario.id)
        verifica("as duas criancas ficam pagas",
                 all(a.pagamento_id == c.pagamento_id for a in reservas(ana) + reservas(bruno)))

        anonimo.post(f"/mercadopago/notificacoes?data.id={pid}&type=payment",
                     json={"type": "payment", "data": {"id": pid}})
        n = db.scalar(select(func.count()).select_from(Pagamento).where(Pagamento.mercadopago_id == pid))
        verifica("aviso repetido nao entra em dobro", n == 1, str(n))

        r = anonimo.post("/mercadopago/notificacoes?topic=merchant_order&id=1", json={})
        verifica("aviso de outro tipo e ignorado com 200", r.status_code == 200, r.text)

        r = ck.get("/pagamentos", params={"padrinho_id": jose, "comprovante": "false"})
        verifica("pago pelo link nao aparece como 'falta comprovante'",
                 r.status_code == 200 and r.json()["total"] == 0, r.text[:200])

        print("\nAviso de link pago")
        r = ck.get("/cobrancas/minhas")
        pagos = r.json().get("pagos", []) if r.status_code == 200 else []
        verifica("quem gerou o link recebe o aviso de pago",
                 [p["cobranca_id"] for p in pagos] == [l1["id"]], r.text[:200])
        verifica("o aviso traz as criancas para o agradecimento",
                 pagos and {a["id"] for a in pagos[0]["apadrinhamentos"]}
                 == {a.id for a in reservas(ana) + reservas(bruno)}, str(pagos)[:200])
        r = ccol.get("/cobrancas/minhas")
        verifica("o colega nao recebe o aviso do link do outro",
                 r.status_code == 200 and r.json()["pagos"] == [], r.text[:150])
        r = ccol.post(f"/cobrancas/{l1['id']}/avisado")
        verifica("nem marca como visto", r.status_code == 404, str(r.status_code))
        r = ck.post(f"/cobrancas/{l1['id']}/avisado")
        verifica("marcar como visto", r.status_code == 204, str(r.status_code))
        r = ck.get("/cobrancas/minhas")
        verifica("e o aviso some", r.json()["pagos"] == [], r.text[:150])

        lx = link(ck, jose, (eva, "cesta")).json()["ultimo_link"]
        falso.pagar(cobranca(lx["id"]).referencia, 120)
        r = ck.get("/cobrancas/minhas")
        verifica("sem aviso do Mercado Pago, a pergunta da tela confere e avisa",
                 [p["cobranca_id"] for p in r.json()["pagos"]] == [lx["id"]]
                 and cobranca(lx["id"]).status == "pago", r.text[:200])
        ck.post(f"/cobrancas/{lx['id']}/avisado")
        for a in reservas(eva):
            db.delete(a)
        db.commit()

        print("\nVencer")
        r = link(ck, jose, (carla, "cesta"))
        l2 = r.json()["ultimo_link"]
        cobranca(l2["id"]).expira_em = cobrancas.agora() - timedelta(minutes=1)
        db.commit()
        ck.get("/criancas", params={"edicao_id": e1.id})
        verifica("link vencido sem pagamento solta a crianca", reservas(carla) == [])
        verifica("e fica como expirado", cobranca(l2["id"]).status == "expirado")

        r = link(ck, jose, (davi, "cesta"))
        l3 = r.json()["ultimo_link"]
        ref3 = cobranca(l3["id"]).referencia
        falso.pagar(ref3, 120, status="in_process")
        cobranca(l3["id"]).expira_em = cobrancas.agora() - timedelta(minutes=1)
        db.commit()
        ck.get("/criancas", params={"edicao_id": e1.id})
        verifica("pagamento em analise segura a crianca mesmo vencido",
                 len(reservas(davi)) == 1 and cobranca(l3["id"]).status == "aguardando")

        falso.pagar(ref3, 120, status="approved")
        ck.get("/criancas", params={"edicao_id": e1.id})
        verifica("aprovado na ultima conferencia antes de vencer: entra pago",
                 cobranca(l3["id"]).status == "pago" and reservas(davi)[0].pagamento_id is not None)

        ref2 = cobranca(l2["id"]).referencia
        pid_tarde = falso.pagar(ref2, 120)
        anonimo.post(f"/mercadopago/notificacoes?data.id={pid_tarde}&type=payment",
                     json={"type": "payment", "data": {"id": pid_tarde}})
        c = cobranca(l2["id"])
        pg = db.get(Pagamento, c.pagamento_id) if c.pagamento_id else None
        verifica("pago depois de vencer: o dinheiro entra, sem crianca",
                 c.status == "pago_apos_vencer" and pg is not None and reservas(carla) == [], c.status)
        verifica("e a observacao avisa a coordenacao",
                 pg is not None and "coordenação" in (pg.observacoes or ""), pg and pg.observacoes)

        print("\nCancelar")
        r = link(ck, jose, (eva, "cesta"))
        l4 = r.json()["ultimo_link"]
        r = ck.post(f"/cobrancas/{l4['id']}/cancelar")
        verifica("cancelar solta a crianca",
                 r.status_code == 200 and reservas(eva) == [] and cobranca(l4["id"]).status == "cancelado",
                 r.text[:150])
        verifica("e encerra o link no Mercado Pago", falso.encerradas[-1:] == [l4 and cobranca(l4["id"]).preferencia_id])
        r = ck.post(f"/cobrancas/{l4['id']}/cancelar")
        verifica("cancelar de novo e recusado", r.status_code == 409, str(r.status_code))

        r = link(ck, jose, (eva, "cesta"))
        l5 = r.json()["ultimo_link"]
        falso.pagar(cobranca(l5["id"]).referencia, 120)
        r = ck.post(f"/cobrancas/{l5['id']}/cancelar")
        verifica("nao cancela o que ja foi pago, e o pagamento entra",
                 r.status_code == 409 and cobranca(l5["id"]).status == "pago", r.text[:150])

        print("\nAssinatura do aviso")
        config.mercadopago_segredo_webhook = "segredo-de-teste"
        r = anonimo.post(f"/mercadopago/notificacoes?data.id={pid}&type=payment",
                         json={"type": "payment", "data": {"id": pid}},
                         headers={"x-signature": "ts=1,v1=errado", "x-request-id": "abc"})
        verifica("assinatura errada e recusada", r.status_code == 401, str(r.status_code))
        v1 = hmac.new(b"segredo-de-teste", f"id:{pid};request-id:abc;ts:1;".encode(),
                      hashlib.sha256).hexdigest()
        r = anonimo.post(f"/mercadopago/notificacoes?data.id={pid}&type=payment",
                         json={"type": "payment", "data": {"id": pid}},
                         headers={"x-signature": f"ts=1,v1={v1}", "x-request-id": "abc"})
        verifica("assinatura certa e aceita", r.status_code == 200, r.text[:150])
        config.mercadopago_segredo_webhook = ""

        print("\nDesligado")
        config.mercadopago_access_token = ""
        r = link(ck, jose, (eva, "festa"))
        verifica("sem token, gerar o link e recusado", r.status_code == 409, str(r.status_code))
        r = ck.get("/mercadopago/situacao")
        verifica("e a tela sabe que esta desligado", r.json().get("ligado") is False)
    finally:
        for nome, funcao in originais.items():
            setattr(mercadopago, nome, funcao)
        config.mercadopago_access_token = token_original
        config.mercadopago_segredo_webhook = segredo_original
        limpar(db, log_inicial)
        db.close()

    print(f"\n{ok} ok, {len(falhas)} falha(s)")
    if falhas:
        for f in falhas:
            print(f"  - {f}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
