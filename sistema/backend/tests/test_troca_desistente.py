"""Testa a troca da crianca desistente e a lista de padrinhos com pendencias.

Quando uma crianca apadrinhada (e paga) desiste, a coordenacao passa o mesmo
apadrinhamento para outra crianca, e depois avisa o padrinho. Tres coisas a
provar: so a coordenacao troca e avisa (por enquanto); a troca nao mexe no dinheiro; e a
desistente fica livre, sem padrinho, se voltar.

Rodar com:  python -m tests.test_troca_desistente
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

MARCA = "ZZ_TROCA"
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
    ids = [u.id for u in db.scalars(select(Usuario).where(Usuario.nome.ilike(f"{MARCA}%"))).all()]
    if ids:
        db.execute(delete(LogAtividade).where(LogAtividade.usuario_id.in_(ids)))
        db.execute(delete(TokenAcesso).where(TokenAcesso.usuario_id.in_(ids)))
    cids = [c.id for c in db.scalars(select(Cidade).where(Cidade.nome.ilike(f"{MARCA}%"))).all()]
    if cids:
        eds = list(db.scalars(select(Edicao.id).where(Edicao.cidade_id.in_(cids))).all())
        if eds:
            pads = list(db.scalars(select(Padrinho.id).where(Padrinho.edicao_id.in_(eds))).all())
            if pads:
                db.execute(delete(Apadrinhamento).where(Apadrinhamento.padrinho_id.in_(pads)))
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

    cidade = Cidade(nome=f"{MARCA} Fortaleza", uf="CE"); db.add(cidade); db.flush()
    ed = Edicao(cidade_id=cidade.id, ano=2026, nome=f"{MARCA} 2026", valor_cesta=130, valor_festa=60)
    db.add(ed); db.flush()
    inst = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola"); db.add(inst); db.flush()

    def crianca(codigo, nome):
        c = Crianca(edicao_id=ed.id, instituicao_id=inst.id, codigo=codigo, nome=nome, idade=8, sexo="F")
        db.add(c); db.flush()
        return c

    ana = crianca("T01", "Ana Desiste")
    bia = crianca("T02", "Bia Recebe")
    cris = crianca("T03", "Cris Tambem Desistiu")

    def usuario(sufixo, perfil, instituicoes=()):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        v = UsuarioEdicao(usuario_id=u.id, edicao_id=ed.id, perfil_id=perfis[perfil].id)
        db.add(v); db.flush()
        for i in instituicoes:
            db.add(UsuarioInstituicao(usuario_edicao_id=v.id, instituicao_id=i))
        return u

    coord = usuario("Coord", "Coordenacao")
    capcoord = usuario("CapCoord", "Comissarios - coordenacao")
    comissario = usuario("Comissario", "Comissarios - comissario", [inst.id])
    ana.comissario_id = comissario.id
    bia.comissario_id = comissario.id
    db.commit()

    try:
        cc = TestClient(app); entrar(cc, coord.email)
        cap = TestClient(app); entrar(cap, capcoord.email)
        ck = TestClient(app); entrar(ck, comissario.email)

        r = ck.post("/padrinhos", json={"edicao_id": ed.id, "nome": "Paulo Padrinho",
                                        "whatsapp": "85988887777"})
        padrinho = r.json()
        r = ck.post(f"/padrinhos/{padrinho['id']}/apadrinhar", json={
            "criancas": [{"crianca_id": ana.id, "tipo": "cesta"}],
            "data": str(date(2026, 11, 20)), "forma": "pix",
        })
        verifica("o comissario apadrinha a Ana, pago", r.status_code == 201, r.text[:160])
        apad = r.json()["apadrinhamentos"][0] if r.status_code == 201 else {}
        pagamento_id = r.json().get("ultimo_pagamento_id") if r.status_code == 201 else None

        print("\nSem desistencia, sem pendencia")
        r = cc.get("/padrinhos/pendencias", params={"edicao_id": ed.id})
        verifica("a lista de pendencias vem vazia", r.status_code == 200 and r.json() == [], r.text[:160])
        r = cc.post(f"/apadrinhamentos/{apad['id']}/trocar-crianca", json={"crianca_id": bia.id})
        verifica("nao troca a crianca de quem nao desistiu", r.status_code == 409, r.text[:160])

        print("\nA Ana desiste")
        r = cc.patch(f"/criancas/{ana.id}/desistencia", json={"desistiu": True})
        verifica("a coordenacao marca a desistencia", r.status_code == 200, r.text[:160])
        cc.patch(f"/criancas/{cris.id}/desistencia", json={"desistiu": True})

        r = cc.get("/padrinhos/pendencias", params={"edicao_id": ed.id})
        lista = r.json() if r.status_code == 200 else []
        verifica("o padrinho aparece nas pendencias da coordenacao",
                 [p["id"] for p in lista] == [padrinho["id"]], r.text[:200])
        verifica("com a pendencia 'trocar' na crianca e a conta no padrinho",
                 lista and lista[0]["apadrinhamentos"][0]["pendencia"] == "trocar"
                 and lista[0]["pendencias"] == 1, r.text[:300])
        r = cap.get("/padrinhos/pendencias", params={"edicao_id": ed.id})
        # Por enquanto (23/11/2026) so a coordenacao: a dos comissarios entra
        # depois que a troca for testada.
        verifica("a coordenacao dos comissarios ainda nao ve",
                 r.status_code == 200 and r.json() == [], r.text[:160])
        r = ck.get("/padrinhos/pendencias", params={"edicao_id": ed.id})
        verifica("o comissario de base recebe a lista vazia",
                 r.status_code == 200 and r.json() == [], r.text[:160])

        print("\nDesfazer nao vale para a desistente paga")
        r = cc.delete(f"/apadrinhamentos/{apad['id']}")
        verifica("nem a coordenacao desfaz: o pagamento ficaria sem destino",
                 r.status_code == 409 and "vincule" in r.text, r.text[:160])

        print("\nQuem pode trocar")
        r = ck.post(f"/apadrinhamentos/{apad['id']}/trocar-crianca", json={"crianca_id": bia.id})
        verifica("o comissario de base NAO troca", r.status_code == 403, r.text[:160])
        r = cap.post(f"/apadrinhamentos/{apad['id']}/trocar-crianca", json={"crianca_id": bia.id})
        verifica("a coordenacao dos comissarios ainda NAO troca", r.status_code == 403, r.text[:160])
        r = cap.post(f"/apadrinhamentos/{apad['id']}/troca-avisada")
        verifica("nem marca o aviso", r.status_code == 403, r.text[:160])
        r = cc.post(f"/apadrinhamentos/{apad['id']}/trocar-crianca", json={"crianca_id": ana.id})
        verifica("nao troca para a propria crianca", r.status_code == 422, r.text[:160])
        r = cc.post(f"/apadrinhamentos/{apad['id']}/trocar-crianca", json={"crianca_id": cris.id})
        verifica("nao troca para outra desistente", r.status_code == 409, r.text[:160])

        r = cc.post(f"/apadrinhamentos/{apad['id']}/trocar-crianca", json={"crianca_id": bia.id})
        verifica("a coordenacao passa para a Bia", r.status_code == 200, r.text[:160])
        depois = r.json()["apadrinhamentos"][0] if r.status_code == 200 else {}
        verifica("o apadrinhamento e o mesmo, agora na Bia",
                 depois.get("id") == apad["id"] and depois.get("crianca_id") == bia.id, str(depois)[:200])
        verifica("guarda de quem veio", depois.get("trocado_de_codigo") == "T01",
                 str(depois.get("trocado_de_codigo")))
        verifica("e fica pendente de avisar o padrinho", depois.get("pendencia") == "avisar",
                 str(depois.get("pendencia")))

        db.expire_all()
        a = db.get(Apadrinhamento, apad["id"])
        verifica("o pagamento e o valor nao mudam",
                 a.pagamento_id == pagamento_id and float(a.valor) == 130.0,
                 f"{a.pagamento_id} {a.valor}")
        verifica("o comissario que captou continua o mesmo", a.comissario_id == comissario.id,
                 str(a.comissario_id))
        verifica("a Ana fica sem padrinho",
                 db.scalar(select(func.count()).select_from(Apadrinhamento)
                           .where(Apadrinhamento.crianca_id == ana.id)) == 0)
        verifica("a troca fica no log",
                 db.scalar(select(func.count()).select_from(LogAtividade).where(
                     LogAtividade.acao == "apadrinhamento_trocado",
                     LogAtividade.registro_id == apad["id"])) == 1)

        r = cc.post(f"/apadrinhamentos/{apad['id']}/trocar-crianca", json={"crianca_id": ana.id})
        verifica("depois da troca, nao troca de novo (a Bia nao desistiu)", r.status_code == 409,
                 r.text[:160])

        r = cc.get("/padrinhos/pendencias", params={"edicao_id": ed.id})
        verifica("o padrinho continua nas pendencias, agora para avisar",
                 r.json() and r.json()[0]["apadrinhamentos"][0]["pendencia"] == "avisar",
                 r.text[:200])

        print("\nO aviso ao padrinho")
        r = ck.post(f"/apadrinhamentos/{apad['id']}/troca-avisada")
        verifica("o comissario de base NAO marca o aviso", r.status_code == 403, r.text[:160])
        r = cc.post(f"/apadrinhamentos/{apad['id']}/troca-avisada")
        verifica("a coordenacao marca o aviso", r.status_code == 200, r.text[:160])
        resumo = r.json()["apadrinhamentos"][0] if r.status_code == 200 else {}
        verifica("e a pendencia some",
                 resumo.get("pendencia") is None and resumo.get("troca_avisada_em"), str(resumo)[:200])
        r = cc.get("/padrinhos/pendencias", params={"edicao_id": ed.id})
        verifica("a lista de pendencias esvazia", r.json() == [], r.text[:160])

        print("\nA Ana volta")
        r = cc.patch(f"/criancas/{ana.id}/desistencia", json={"desistiu": False})
        verifica("a coordenacao desmarca a desistencia", r.status_code == 200, r.text[:160])
        r = ck.post(f"/padrinhos/{padrinho['id']}/apadrinhar", json={
            "criancas": [{"crianca_id": ana.id, "tipo": "cesta"}],
            "data": str(date(2026, 11, 21)), "forma": "pix",
        })
        verifica("e ela volta livre: pode ser apadrinhada de novo", r.status_code == 201, r.text[:160])
    finally:
        limpar(db, log_inicial)
        db.close()

    print(f"\n{ok} verificacoes ok, {len(falhas)} falha(s)")
    if falhas:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
