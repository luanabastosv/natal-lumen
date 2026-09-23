"""Testa padrinhos, apadrinhamentos e pagamentos (fase 6).

Rodar com:  python -m tests.test_padrinhos
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    Apadrinhamento,
    Cidade,
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

MARCA = "ZZ_PAD"
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


def limpar(db, log_inicial: int = 0) -> None:
    db.rollback()
    db.execute(delete(LogAtividade).where(LogAtividade.id > log_inicial))

    usuarios = db.scalars(select(Usuario).where(Usuario.nome.like(f"{MARCA}%"))).all()
    ids = [u.id for u in usuarios]
    if ids:
        db.execute(delete(LogAtividade).where(LogAtividade.usuario_id.in_(ids)))
        db.execute(delete(TokenAcesso).where(TokenAcesso.usuario_id.in_(ids)))

    cids = [c.id for c in db.scalars(select(Cidade).where(Cidade.nome.like(f"{MARCA}%"))).all()]
    if cids:
        eds = list(db.scalars(select(Edicao.id).where(Edicao.cidade_id.in_(cids))).all())
        if eds:
            pads = list(db.scalars(select(Padrinho.id).where(Padrinho.edicao_id.in_(eds))).all())
            cris = list(db.scalars(select(Crianca.id).where(Crianca.edicao_id.in_(eds))).all())
            if pads or cris:
                db.execute(delete(Apadrinhamento).where(
                    Apadrinhamento.padrinho_id.in_(pads or [0])
                    | Apadrinhamento.crianca_id.in_(cris or [0])
                ))
            if pads:
                db.execute(delete(Pagamento).where(Pagamento.padrinho_id.in_(pads)))
                db.execute(delete(Padrinho).where(Padrinho.id.in_(pads)))
            db.execute(delete(Crianca).where(Crianca.edicao_id.in_(eds)))
            vs = list(db.scalars(select(UsuarioEdicao.id).where(UsuarioEdicao.edicao_id.in_(eds))).all())
            if vs:
                db.execute(delete(UsuarioInstituicao).where(UsuarioInstituicao.usuario_edicao_id.in_(vs)))
                db.execute(delete(UsuarioEdicao).where(UsuarioEdicao.id.in_(vs)))
            db.execute(delete(Edicao).where(Edicao.id.in_(eds)))
        db.execute(delete(Instituicao).where(Instituicao.cidade_id.in_(cids)))
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


def main() -> None:
    db = SessionLocal()
    log_inicial = db.scalar(select(func.max(LogAtividade.id))) or 0
    limpar(db)

    perfis = {p.nome: p for p in db.scalars(select(Perfil)).all()}

    # Duas cidades, para testar o apadrinhamento entre cidades.
    c1 = Cidade(nome=f"{MARCA} Fortaleza", uf="CE")
    c2 = Cidade(nome=f"{MARCA} Caucaia", uf="CE")
    db.add_all([c1, c2]); db.flush()
    e1 = Edicao(cidade_id=c1.id, ano=2026, nome=f"{MARCA} Fortaleza 2026", valor_cesta=120, valor_festa=60)
    e2 = Edicao(cidade_id=c2.id, ano=2026, nome=f"{MARCA} Caucaia 2026", valor_cesta=150, valor_festa=70)
    db.add_all([e1, e2]); db.flush()
    i1 = Instituicao(cidade_id=c1.id, nome=f"{MARCA} Escola A")
    i2 = Instituicao(cidade_id=c2.id, nome=f"{MARCA} Creche B")
    db.add_all([i1, i2]); db.flush()

    ana = Crianca(edicao_id=e1.id, instituicao_id=i1.id, codigo="001", nome="Ana Clara Avila", idade=8, sexo="F")
    bruno = Crianca(edicao_id=e1.id, instituicao_id=i1.id, codigo="002", nome="Bruno Lima", idade=10, sexo="M")
    carla = Crianca(edicao_id=e2.id, instituicao_id=i2.id, codigo="001", nome="Carla Souza", idade=7, sexo="F")
    db.add_all([ana, bruno, carla]); db.flush()

    def usuario(sufixo, perfil, edicoes):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        for ed in edicoes:
            db.add(UsuarioEdicao(usuario_id=u.id, edicao_id=ed, perfil_id=perfis[perfil].id))
        return u

    coord = usuario("Coord", "Coordenacao", [e1.id, e2.id])
    comissario = usuario("Comissario", "Comissario", [e1.id])
    monitor = usuario("Monitor", "Monitor", [e1.id])
    db.commit()

    try:
        cc = TestClient(app); entrar(cc, coord.email)
        ck = TestClient(app); entrar(ck, comissario.email)
        cm = TestClient(app); entrar(cm, monitor.email)

        print("\nPadrinhos")
        r = ck.post("/padrinhos", json={"edicao_id": e1.id, "nome": "  Jose   Doador  ", "whatsapp": "85999990000"})
        verifica("comissario capta padrinho", r.status_code == 201, r.text[:130])
        jose = r.json() if r.status_code == 201 else {}
        verifica("espacos extras do nome sao limpos", jose.get("nome") == "Jose Doador", str(jose.get("nome")))

        r = cm.post("/padrinhos", json={"edicao_id": e1.id, "nome": "Nao Deveria"})
        verifica("monitor NAO capta padrinho", r.status_code == 403, str(r.status_code))

        r = ck.post("/padrinhos", json={"edicao_id": e2.id, "nome": "Fora do alcance"})
        verifica("comissario nao capta padrinho na edicao de outra cidade", r.status_code == 403)

        print("\nApadrinhamentos")
        r = ck.post("/apadrinhamentos", json={"crianca_id": ana.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("liga padrinho a crianca", r.status_code == 201, r.text[:130])
        dados = r.json() if r.status_code == 201 else {}
        verifica("valor vem da edicao da crianca", dados["apadrinhamentos"][0]["valor"] == "120.00",
                 str(dados["apadrinhamentos"][0]["valor"]) if dados else "")
        verifica("padrinho recebe so o primeiro nome da crianca",
                 dados["apadrinhamentos"][0]["crianca_primeiro_nome"] == "Ana",
                 str(dados["apadrinhamentos"][0]["crianca_primeiro_nome"]) if dados else "")

        r = ck.post("/apadrinhamentos", json={"crianca_id": ana.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("recusa dois padrinhos de cesta para a mesma crianca", r.status_code == 409)

        r = ck.post("/apadrinhamentos", json={"crianca_id": ana.id, "padrinho_id": jose["id"], "tipo": "festa"})
        verifica("a mesma crianca aceita padrinho de festa", r.status_code == 201, r.text[:110])

        r = ck.post("/apadrinhamentos", json={"crianca_id": bruno.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("o mesmo padrinho apadrinha uma segunda crianca", r.status_code == 201, r.text[:110])

        r = ck.post("/apadrinhamentos", json={"crianca_id": carla.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("comissario de Fortaleza nao alcanca crianca de Caucaia", r.status_code == 403, str(r.status_code))

        r = cc.post("/apadrinhamentos", json={"crianca_id": carla.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("coordenacao das duas cidades faz o apadrinhamento cruzado", r.status_code == 201, r.text[:130])
        cruzado = r.json() if r.status_code == 201 else {}
        if cruzado:
            de_carla = [a for a in cruzado["apadrinhamentos"] if a["crianca_id"] == carla.id][0]
            verifica("no cruzado, o valor vem da edicao da crianca (150, nao 120)",
                     de_carla["valor"] == "150.00", str(de_carla["valor"]))
            verifica("padrinho acumula 4 apadrinhamentos", len(cruzado["apadrinhamentos"]) == 4,
                     str(len(cruzado["apadrinhamentos"])))
            verifica("total combinado soma certo (120+60+120+150)",
                     cruzado["total_combinado"] == "450.00", str(cruzado["total_combinado"]))

        print("\nPagamentos")
        ids_cesta = [a["id"] for a in cruzado["apadrinhamentos"] if a["tipo"] == "cesta"][:2]
        r = ck.post("/pagamentos", json={
            "padrinho_id": jose["id"], "valor": "240.00", "data": str(date(2026, 11, 10)),
            "forma": "pix", "apadrinhamentos": ids_cesta,
        })
        verifica("um pagamento quita varios apadrinhamentos", r.status_code == 201, r.text[:140])
        pagamento = r.json() if r.status_code == 201 else {}
        verifica("o pagamento guarda os apadrinhamentos que quitou",
                 len(pagamento.get("apadrinhamentos", [])) == 2, str(pagamento.get("apadrinhamentos")))

        r = ck.get(f"/padrinhos/{jose['id']}")
        verifica("total pago reflete os quitados", r.json()["total_pago"] == "240.00", r.json()["total_pago"])
        pagos = [a for a in r.json()["apadrinhamentos"] if a["pago"]]
        verifica("dois apadrinhamentos aparecem como pagos", len(pagos) == 2, str(len(pagos)))

        r = ck.post("/pagamentos", json={
            "padrinho_id": jose["id"], "valor": "60.00", "data": str(date(2026, 11, 11)),
            "apadrinhamentos": ids_cesta[:1],
        })
        verifica("recusa quitar duas vezes o mesmo apadrinhamento", r.status_code == 409, str(r.status_code))

        outro = ck.post("/padrinhos", json={"edicao_id": e1.id, "nome": "Outro Doador"}).json()
        r = ck.post("/pagamentos", json={
            "padrinho_id": outro["id"], "valor": "10.00", "data": str(date(2026, 11, 12)),
            "apadrinhamentos": ids_cesta[:1],
        })
        verifica("recusa pagamento com apadrinhamento de outro padrinho", r.status_code == 422, str(r.status_code))

        r = ck.patch(f"/pagamentos/{pagamento['id']}", json={"conferido": True})
        verifica("marca o pagamento como conferido", r.status_code == 200 and r.json()["conferido"], r.text[:110])

        r = ck.get("/pagamentos", params={"conferido": "true"})
        verifica("filtra pagamentos conferidos", r.json()["total"] == 1, str(r.json()["total"]))

        print("\nRemocao")
        r = ck.delete(f"/apadrinhamentos/{ids_cesta[0]}")
        verifica("recusa apagar apadrinhamento ja pago", r.status_code == 409, str(r.status_code))

        r = ck.delete(f"/pagamentos/{pagamento['id']}")
        verifica("apaga o pagamento", r.status_code == 204, str(r.status_code))

        r = ck.get(f"/padrinhos/{jose['id']}")
        verifica("apagar o pagamento solta os apadrinhamentos", r.json()["total_pago"] == "0.00", r.json()["total_pago"])

        r = ck.delete(f"/apadrinhamentos/{ids_cesta[0]}")
        verifica("agora o apadrinhamento pode ser apagado", r.status_code == 204, str(r.status_code))

        print("\nVisibilidade do caso entre cidades")
        # Um comissario so de Caucaia deve enxergar o padrinho de Fortaleza que
        # apadrinhou uma crianca de Caucaia.
        so_caucaia = usuario("SoCaucaia", "Comissario", [e2.id])
        db.commit()
        cs = TestClient(app); entrar(cs, so_caucaia.email)

        r = cs.get("/padrinhos")
        nomes = [p["nome"] for p in r.json()["itens"]]
        verifica("comissario de Caucaia ve o padrinho de Fortaleza que apadrinhou crianca dele",
                 "Jose Doador" in nomes, str(nomes))
        verifica("mas nao ve o padrinho sem ligacao com a cidade dele",
                 "Outro Doador" not in nomes, str(nomes))

        print("\nPermissoes")
        r = cm.get("/padrinhos")
        verifica("monitor NAO ve padrinhos", r.status_code == 403, str(r.status_code))
        r = cm.get("/pagamentos")
        verifica("monitor NAO ve pagamentos", r.status_code == 403, str(r.status_code))

    finally:
        limpar(db, log_inicial)
        db.close()

    print(f"\n{ok} verificacoes ok, {len(falhas)} falha(s)")
    if falhas:
        for f in falhas:
            print("  -", f)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
