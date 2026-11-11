"""Testa a intercessao: o perfil da equipe que reza, as marcacoes e o painel.

  1. o perfil Intercessao ve a edicao inteira e recebe as marcacoes na lista;
     quem nao intercede (a coordenacao) recebe o campo nulo e nao marca;
  2. cada vivencia de uma crianca e de uma pessoa so: quem marcou primeiro.
     Os outros levam 409 ao marcar e nao conseguem desmarcar;
  3. o painel soma como a planilha: vivencias / 5, misterios / 15.

Rodar com:  python -m tests.test_intercessao
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    AveMaria,
    Cidade,
    Crianca,
    DiaEvento,
    Edicao,
    Instituicao,
    LogAtividade,
    Perfil,
    TokenAcesso,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.seguranca.senhas import gerar_hash

MARCA = "ZZ_INT"
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
            db.execute(delete(Crianca).where(Crianca.edicao_id.in_(eds)))
            vs = list(db.scalars(select(UsuarioEdicao.id).where(UsuarioEdicao.edicao_id.in_(eds))).all())
            if vs:
                db.execute(delete(UsuarioInstituicao).where(UsuarioInstituicao.usuario_edicao_id.in_(vs)))
                db.execute(delete(UsuarioEdicao).where(UsuarioEdicao.id.in_(vs)))
            db.execute(delete(DiaEvento).where(DiaEvento.edicao_id.in_(eds)))
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

    cidade = Cidade(nome=f"{MARCA} Cidade", uf="CE"); db.add(cidade); db.flush()
    edicao = Edicao(cidade_id=cidade.id, ano=2026, nome=f"{MARCA} Edicao",
                    valor_cesta=120, valor_festa=60); db.add(edicao); db.flush()
    dia = DiaEvento(edicao_id=edicao.id, data=date(2026, 12, 20)); db.add(dia); db.flush()
    inst = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola A")
    inst_b = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola B")
    db.add_all([inst, inst_b]); db.flush()

    criancas = [
        Crianca(edicao_id=edicao.id, instituicao_id=(inst if i < 4 else inst_b).id,
                dia_evento_id=dia.id, codigo=f"I{i}", nome=f"Crianca I{i}", idade=8, sexo="F")
        for i in range(1, 6)
    ]
    db.add_all(criancas); db.flush()

    def usuario(sufixo, perfil, instituicoes=()):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        v = UsuarioEdicao(usuario_id=u.id, edicao_id=edicao.id, perfil_id=perfis[perfil].id)
        db.add(v); db.flush()
        for i in instituicoes:
            db.add(UsuarioInstituicao(usuario_edicao_id=v.id, instituicao_id=i))
        return u

    coord = usuario("Coord", "Coordenacao")
    ana = usuario("Ana", "Intercessao")
    bia = usuario("Bia", "Intercessao")
    monitor = usuario("Monitor", "Monitoria - monitores", [inst.id])
    db.commit()

    try:
        ca = TestClient(app); entrar(ca, ana.email)
        cb = TestClient(app); entrar(cb, bia.email)
        cc = TestClient(app); entrar(cc, coord.email)
        cm = TestClient(app); entrar(cm, monitor.email)

        print("\nO perfil da intercessao")
        r = ca.get("/criancas", params={"edicao_id": edicao.id, "por_pagina": 50})
        itens = r.json().get("itens", []) if r.status_code == 200 else []
        verifica("ve todas as criancas da edicao, das duas escolas",
                 len(itens) == 5, f"{r.status_code} {len(itens)}")
        verifica("e recebe as marcacoes na lista (vazias)",
                 all(c.get("intercessoes") == [] for c in itens), str(itens[:1])[:200])
        verifica("nao recebe padrinho nem kit",
                 all(c.get("tem_padrinho_cesta") is None and c.get("kit_status") is None
                     for c in itens))

        r = cc.get("/criancas", params={"edicao_id": edicao.id})
        verifica("a coordenacao nao recebe as marcacoes (nulo)",
                 all(c.get("intercessoes") is None for c in r.json().get("itens", [])))

        alvo = criancas[0]
        print("\nMarcar e desmarcar")
        r = ca.post(f"/intercessao/{alvo.id}/missa")
        verifica("a Ana marca missa", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        marcas = r.json() if r.status_code == 200 else []
        verifica("e a marcacao vem com o nome dela",
                 len(marcas) == 1 and marcas[0]["nome"] == ana.nome and marcas[0]["tipo"] == "missa",
                 str(marcas))
        r = ca.post(f"/intercessao/{alvo.id}/missa")
        verifica("marcar de novo nao duplica", r.status_code == 200 and len(r.json()) == 1, r.text[:120])
        r = cb.post(f"/intercessao/{alvo.id}/missa")
        verifica("a Bia nao marca a missa que ja e da Ana: 409 com o nome dela",
                 r.status_code == 409 and ana.nome in r.json().get("detail", ""), r.text[:200])
        r = cb.delete(f"/intercessao/{alvo.id}/missa")
        verifica("e nem desmarca a da Ana",
                 r.status_code == 200 and [m["nome"] for m in r.json()] == [ana.nome], r.text[:200])
        r = cb.post(f"/intercessao/{alvo.id}/terco")
        verifica("outra vivencia da mesma crianca a Bia marca",
                 r.status_code == 200 and len(r.json()) == 2, r.text[:200])
        cb.delete(f"/intercessao/{alvo.id}/terco")
        r = ca.delete(f"/intercessao/{alvo.id}/missa")
        verifica("a Ana desmarca a dela", r.status_code == 200 and r.json() == [], r.text[:200])
        r = cb.post(f"/intercessao/{alvo.id}/missa")
        verifica("e ai a Bia pode marcar", r.status_code == 200 and
                 [m["nome"] for m in r.json()] == [bia.nome], r.text[:200])
        r = ca.post(f"/intercessao/{alvo.id}/novena")
        verifica("vivencia que nao existe e recusada", r.status_code == 422, str(r.status_code))

        r = ca.get("/criancas", params={"edicao_id": edicao.id, "codigo": alvo.codigo})
        na_lista = r.json()["itens"][0]["intercessoes"] if r.status_code == 200 else None
        verifica("a lista mostra a marcacao da Bia",
                 na_lista and na_lista[0]["usuario_id"] == bia.id, str(na_lista))

        print("\nQuem nao intercede nao marca")
        r = cc.post(f"/intercessao/{alvo.id}/jejum")
        verifica("a coordenacao leva 403", r.status_code == 403, str(r.status_code))
        r = cm.post(f"/intercessao/{alvo.id}/jejum")
        verifica("o monitor leva 403", r.status_code == 403, str(r.status_code))

        outra = Edicao(cidade_id=cidade.id, ano=2027, nome=f"{MARCA} Outra",
                       valor_cesta=1, valor_festa=1)
        db.add(outra); db.flush()
        de_fora = Crianca(edicao_id=outra.id, instituicao_id=inst.id, codigo="X1",
                          nome="Crianca de fora", idade=7, sexo="M")
        db.add(de_fora); db.commit()
        r = ca.post(f"/intercessao/{de_fora.id}/missa")
        verifica("crianca de outra edicao: 404", r.status_code == 404, str(r.status_code))

        print("\nO painel soma como a planilha")
        # 5 missas e 5 misterios: 1 missa e 0,3 terco. 2 jejuns: 0,4 jejum.
        ca.delete(f"/intercessao/{alvo.id}/missa")
        cb.delete(f"/intercessao/{alvo.id}/missa")
        for c in criancas:
            ca.post(f"/intercessao/{c.id}/missa")
            ca.post(f"/intercessao/{c.id}/terco")
            cb.post(f"/intercessao/{c.id}/terco")  # 409: ja e da Ana
        for c in criancas[:3]:
            db.add(AveMaria(crianca_id=c.id, dia=date(2026, 11, 1)))
        db.commit()
        for c in criancas:
            cb.post(f"/intercessao/{c.id}/adoracao")
        cb.post(f"/intercessao/{criancas[0].id}/jejum")
        cb.post(f"/intercessao/{criancas[1].id}/jejum")
        criancas[4].desistiu_em = func.now()
        db.commit()

        r = ca.get(f"/intercessao/painel/{edicao.id}")
        p = r.json() if r.status_code == 200 else {}
        verifica("a equipe abre o painel", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        verifica("criancas sem a desistente", p.get("criancas") == 4, str(p))
        verifica("todas as 4 receberam intercessao", p.get("receberam") == 4 and p.get("faltam") == 0, str(p))
        verifica("5 missas marcadas = 1 missa", p.get("missas") == 1.0, str(p.get("missas")))
        verifica("5 adoracoes marcadas = 1 adoracao", p.get("adoracoes") == 1.0, str(p.get("adoracoes")))
        verifica("5 misterios = 0,3 terco (a Bia nao somou por cima)",
                 p.get("tercos") == 0.3, str(p.get("tercos")))
        verifica("2 jejuns marcados = 0,4 jejum", p.get("jejuns") == 0.4, str(p.get("jejuns")))
        verifica("e as ave-marias da edicao", p.get("ave_marias") == 3, str(p.get("ave_marias")))

        r = cc.get(f"/intercessao/painel/{edicao.id}")
        verifica("a coordenacao tambem abre o painel", r.status_code == 200, str(r.status_code))
        r = cm.get(f"/intercessao/painel/{edicao.id}")
        verifica("o monitor nao", r.status_code == 403, str(r.status_code))
        r = ca.get(f"/intercessao/painel/{outra.id}")
        verifica("edicao fora do alcance: 404", r.status_code == 404, str(r.status_code))

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
