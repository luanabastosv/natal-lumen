"""Testa os cadastros base (fase 4).

O foco sao as regras de quem pode o que:
  - so a administracao geral cria cidades, edicoes e coordenadores;
  - a coordenacao so mexe em usuarios e instituicoes da propria cidade;
  - a instituicao atribuida tem de ser da cidade da edicao.

Rodar com:  python -m tests.test_cadastros
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
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

MARCA = "ZZ_CAD"
SENHA = "senha-de-teste-123"

ok = 0
falhas: list[str] = []


def verifica(descricao: str, condicao: bool, extra: str = "") -> None:
    global ok
    if condicao:
        ok += 1
        print(f"  ok    {descricao}")
    else:
        falhas.append(descricao)
        print(f"  FALHA {descricao} {extra}")


def limpar(db, log_inicial: int = 0) -> None:
    db.rollback()
    db.execute(delete(LogAtividade).where(LogAtividade.id > log_inicial))

    usuarios = db.scalars(select(Usuario).where(Usuario.nome.like(f"{MARCA}%"))).all()
    ids = [u.id for u in usuarios]
    if ids:
        db.execute(delete(LogAtividade).where(LogAtividade.usuario_id.in_(ids)))
        db.execute(delete(TokenAcesso).where(TokenAcesso.usuario_id.in_(ids)))

    cidades = db.scalars(select(Cidade).where(Cidade.nome.like(f"{MARCA}%"))).all()
    cidade_ids = [c.id for c in cidades]
    if cidade_ids:
        edicoes = db.scalars(select(Edicao).where(Edicao.cidade_id.in_(cidade_ids))).all()
        edicao_ids = [e.id for e in edicoes]
        if edicao_ids:
            db.execute(delete(Crianca).where(Crianca.edicao_id.in_(edicao_ids)))
            vinculos = db.scalars(
                select(UsuarioEdicao).where(UsuarioEdicao.edicao_id.in_(edicao_ids))
            ).all()
            if vinculos:
                db.execute(
                    delete(UsuarioInstituicao).where(
                        UsuarioInstituicao.usuario_edicao_id.in_([v.id for v in vinculos])
                    )
                )
                db.execute(delete(UsuarioEdicao).where(UsuarioEdicao.edicao_id.in_(edicao_ids)))
            db.execute(delete(DiaEvento).where(DiaEvento.edicao_id.in_(edicao_ids)))
            db.execute(delete(Edicao).where(Edicao.id.in_(edicao_ids)))
        db.execute(delete(Instituicao).where(Instituicao.cidade_id.in_(cidade_ids)))
        db.execute(delete(Cidade).where(Cidade.id.in_(cidade_ids)))

    if ids:
        db.execute(delete(Usuario).where(Usuario.id.in_(ids)))
    db.commit()


def entrar(cliente: TestClient, email: str):
    resposta = cliente.post("/auth/login", json={"email": email, "senha": SENHA})
    if resposta.status_code == 200:
        # A app vive sob /acesso em producao; no teste ela esta na raiz.
        for nome in (config.cookie_nome, config.cookie_csrf):
            valor = next((ck.value for ck in cliente.cookies.jar if ck.name == nome), None)
            if valor:
                cliente.cookies.set(nome, valor, path="/")
        csrf = next(ck.value for ck in cliente.cookies.jar if ck.name == config.cookie_csrf)
        cliente.headers["X-CSRF-Token"] = csrf
    return resposta


def main() -> None:
    db = SessionLocal()
    log_inicial = db.scalar(select(func.max(LogAtividade.id))) or 0
    limpar(db)

    # --- cenario minimo: um admin e um coordenador, criados direto na base ---
    perfis = {p.nome: p for p in db.scalars(select(Perfil)).all()}

    admin = Usuario(
        nome=f"{MARCA} Admin", email=f"{MARCA.lower()}.admin@exemplo.org",
        senha_hash=gerar_hash(SENHA), admin_geral=True,
    )
    coord = Usuario(
        nome=f"{MARCA} Coord", email=f"{MARCA.lower()}.coord@exemplo.org",
        senha_hash=gerar_hash(SENHA),
    )
    db.add_all([admin, coord])
    db.commit()

    try:
        ca = TestClient(app)
        entrar(ca, admin.email)

        print("\nCidades e edicoes (so a administracao geral)")
        r = ca.post("/cidades", json={"nome": f"{MARCA} Fortaleza", "uf": "ce"})
        verifica("admin cria cidade", r.status_code == 201, r.text[:110])
        fortaleza = r.json()
        verifica("uf e gravada em maiusculas", fortaleza["uf"] == "CE")

        r = ca.post("/cidades", json={"nome": f"{MARCA} Fortaleza", "uf": "CE"})
        verifica("recusa cidade repetida na mesma uf", r.status_code == 409)

        r = ca.post("/cidades", json={"nome": f"{MARCA} Caucaia", "uf": "CE"})
        caucaia = r.json()

        r = ca.post("/edicoes", json={
            "cidade_id": fortaleza["id"], "ano": 2026,
            "nome": f"{MARCA} Fortaleza 2026", "valor_cesta": "120.00", "valor_festa": "60.00",
        })
        verifica("admin cria edicao", r.status_code == 201, r.text[:110])
        ed_for = r.json()

        r = ca.post("/edicoes", json={
            "cidade_id": fortaleza["id"], "ano": 2026, "nome": "Outra",
            "valor_cesta": "120.00", "valor_festa": "60.00",
        })
        verifica("recusa duas edicoes da mesma cidade no mesmo ano", r.status_code == 409)

        r = ca.post("/edicoes", json={
            "cidade_id": caucaia["id"], "ano": 2026, "nome": f"{MARCA} Caucaia 2026",
            "valor_cesta": "120.00", "valor_festa": "60.00",
        })
        ed_cau = r.json()

        print("\nInstituicoes")
        r = ca.post("/instituicoes", json={"cidade_id": fortaleza["id"], "nome": f"{MARCA} Escola A"})
        verifica("cria instituicao", r.status_code == 201, r.text[:110])
        inst_a = r.json()
        inst_b = ca.post("/instituicoes", json={"cidade_id": fortaleza["id"], "nome": f"{MARCA} Escola B"}).json()
        inst_c = ca.post("/instituicoes", json={"cidade_id": caucaia["id"], "nome": f"{MARCA} Creche C"}).json()

        r = ca.post("/instituicoes", json={"cidade_id": fortaleza["id"], "nome": f"{MARCA} Escola A"})
        verifica("recusa instituicao repetida na cidade", r.status_code == 409)

        print("\nDias do evento")
        r = ca.post(f"/edicoes/{ed_for['id']}/dias", json={"data": "2026-12-20", "descricao": "Sabado"})
        verifica("cria dia do evento", r.status_code == 201, r.text[:110])
        dia = r.json()
        r = ca.post(f"/edicoes/{ed_for['id']}/dias", json={"data": "2026-12-20"})
        verifica("recusa o mesmo dia duas vezes", r.status_code == 409)

        r = ca.get(f"/edicoes/{ed_for['id']}/dias")
        verifica("lista dias com contagem de criancas", r.json()[0]["total_criancas"] == 0)

        print("\nCriacao de usuarios")
        # O coordenador precisa de vinculo para gerenciar; so o admin pode dar.
        r = ca.post(f"/usuarios/{coord.id}/vinculos", json={
            "edicao_id": ed_for["id"], "perfil_id": perfis["Coordenacao"].id, "instituicoes": [],
        })
        verifica("admin torna alguem coordenador", r.status_code == 201, r.text[:140])

        r = ca.post(
            "/usuarios",
            json={
                "dados": {"nome": f"{MARCA} Monitor", "email": f"{MARCA.lower()}.monitor@exemplo.org"},
                "vinculo": {"edicao_id": ed_for["id"], "perfil_id": perfis["Monitor"].id, "instituicoes": [inst_a["id"]]},
            },
        )
        verifica("cria usuario com vinculo e instituicao", r.status_code == 201, r.text[:160])
        criado = r.json() if r.status_code == 201 else {}
        if criado:
            verifica("devolve link de primeiro acesso", "definir-senha?token=" in criado["link"])
            verifica("conta nasce sem senha", criado["usuario"]["tem_senha"] is False)
            verifica(
                "instituicao ficou atribuida",
                criado["usuario"]["vinculos"][0]["instituicoes"] == [inst_a["id"]],
            )

        print("\nRegras da coordenacao")
        cc = TestClient(app)
        entrar(cc, coord.email)

        r = cc.post("/cidades", json={"nome": f"{MARCA} Sobral", "uf": "CE"})
        verifica("coordenacao NAO cria cidade", r.status_code == 403, str(r.status_code))

        r = cc.post("/edicoes", json={
            "cidade_id": fortaleza["id"], "ano": 2027, "nome": "x",
            "valor_cesta": "1.00", "valor_festa": "1.00",
        })
        verifica("coordenacao NAO cria edicao", r.status_code == 403)

        r = cc.post("/usuarios", json={
            "dados": {"nome": f"{MARCA} Outro Coord", "email": f"{MARCA.lower()}.oc@exemplo.org"},
            "vinculo": {"edicao_id": ed_for["id"], "perfil_id": perfis["Coordenacao"].id, "instituicoes": []},
        })
        verifica("coordenacao NAO cria outro coordenador", r.status_code == 403, str(r.status_code))

        r = cc.post("/usuarios", json={
            "dados": {"nome": f"{MARCA} Comissario", "email": f"{MARCA.lower()}.com@exemplo.org"},
            "vinculo": {"edicao_id": ed_for["id"], "perfil_id": perfis["Comissario"].id, "instituicoes": [inst_b["id"]]},
        })
        verifica("coordenacao cria comissario na sua edicao", r.status_code == 201, r.text[:140])
        comissario = r.json()["usuario"] if r.status_code == 201 else None

        r = cc.post("/usuarios", json={
            "dados": {"nome": f"{MARCA} Intruso", "email": f"{MARCA.lower()}.int@exemplo.org"},
            "vinculo": {"edicao_id": ed_cau["id"], "perfil_id": perfis["Monitor"].id, "instituicoes": []},
        })
        verifica("coordenacao NAO cria usuario na edicao de outra cidade", r.status_code == 403)

        print("\nInstituicao tem de ser da cidade da edicao")
        if comissario:
            vinculo_id = comissario["vinculos"][0]["id"]
            r = cc.patch(
                f"/usuarios/{comissario['id']}/vinculos/{vinculo_id}",
                json={"instituicoes": [inst_c["id"]]},
            )
            verifica(
                "recusa instituicao de outra cidade",
                r.status_code == 422,
                f"{r.status_code} {r.text[:90]}",
            )

            r = cc.patch(
                f"/usuarios/{comissario['id']}/vinculos/{vinculo_id}",
                json={"instituicoes": [inst_a["id"], inst_b["id"]]},
            )
            verifica("aceita instituicoes da mesma cidade", r.status_code == 200, r.text[:110])
            if r.status_code == 200:
                verifica(
                    "as duas instituicoes ficaram atribuidas",
                    sorted(r.json()["vinculos"][0]["instituicoes"]) == sorted([inst_a["id"], inst_b["id"]]),
                )

            r = cc.patch(
                f"/usuarios/{comissario['id']}/vinculos/{vinculo_id}", json={"instituicoes": []}
            )
            verifica("consegue tirar todas as instituicoes", r.json()["vinculos"][0]["instituicoes"] == [])

        print("\nAlcance e listagens")
        r = cc.get("/cidades")
        nomes = [c["nome"] for c in r.json()]
        verifica("coordenacao so ve a cidade dela", nomes == [f"{MARCA} Fortaleza"], str(nomes))

        r = cc.get("/instituicoes")
        nomes = sorted(i["nome"] for i in r.json())
        verifica(
            "coordenacao so ve instituicoes da cidade dela",
            nomes == sorted([f"{MARCA} Escola A", f"{MARCA} Escola B"]),
            str(nomes),
        )

        r = cc.get("/edicoes")
        verifica("coordenacao so ve a edicao dela", len(r.json()) == 1)

        r = ca.get("/edicoes")
        verifica("admin ve as duas edicoes", len(r.json()) >= 2)

        r = cc.patch(f"/usuarios/{admin.id}", json={"nome": "tentando"})
        verifica("coordenacao NAO mexe em conta de admin", r.status_code == 403, str(r.status_code))

        print("\nLink de acesso e bloqueio")
        if comissario:
            r = cc.post(f"/usuarios/{comissario['id']}/link-de-acesso")
            verifica("gera link novo para quem perdeu o anterior", r.status_code == 200, r.text[:110])

        print("\nCSRF continua valendo nestas rotas")
        sem_csrf = TestClient(app)
        entrar(sem_csrf, admin.email)
        del sem_csrf.headers["X-CSRF-Token"]
        r = sem_csrf.post("/cidades", json={"nome": f"{MARCA} Sem CSRF", "uf": "CE"})
        verifica("POST sem CSRF e recusado", r.status_code == 403, str(r.status_code))

        print("\nApagar dia com criancas marcadas")
        edicao_obj = db.get(Edicao, ed_for["id"])
        crianca = Crianca(
            edicao_id=edicao_obj.id, instituicao_id=inst_a["id"], dia_evento_id=dia["id"],
            codigo="001", nome=f"{MARCA} Crianca", idade=8, sexo="F",
        )
        db.add(crianca)
        db.commit()

        r = ca.delete(f"/edicoes/{ed_for['id']}/dias/{dia['id']}")
        verifica("recusa apagar dia com crianca marcada", r.status_code == 409, str(r.status_code))

        db.delete(crianca)
        db.commit()
        r = ca.delete(f"/edicoes/{ed_for['id']}/dias/{dia['id']}")
        verifica("apaga dia vazio", r.status_code == 204, str(r.status_code))

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
