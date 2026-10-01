"""Testa os cadastros base (fase 4).

O foco sao as regras de quem pode o que:
  - so a administracao geral cria cidades, edicoes e coordenadores;
  - a coordenacao so mexe em usuarios e instituicoes da propria cidade;
  - a instituicao atribuida tem de ser da cidade da edicao.

Rodar com:  python -m tests.test_cadastros
"""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    Apadrinhamento,
    Cidade,
    Crianca,
    DiaEvento,
    Edicao,
    Grupo,
    Instituicao,
    LogAtividade,
    Padrinho,
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

    usuarios = db.scalars(select(Usuario).where(Usuario.nome.ilike(f"{MARCA}%"))).all()
    ids = [u.id for u in usuarios]
    if ids:
        db.execute(delete(LogAtividade).where(LogAtividade.usuario_id.in_(ids)))
        db.execute(delete(TokenAcesso).where(TokenAcesso.usuario_id.in_(ids)))

    cidades = db.scalars(select(Cidade).where(Cidade.nome.ilike(f"{MARCA}%"))).all()
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
        # Depois dos vinculos: e quem aponta para o grupo.
        db.execute(delete(Grupo).where(Grupo.cidade_id.in_(cidade_ids)))
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
                "vinculo": {"edicao_id": ed_for["id"], "perfil_id": perfis["Monitoria - monitores"].id, "instituicoes": [inst_a["id"]]},
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
            "vinculo": {"edicao_id": ed_for["id"], "perfil_id": perfis["Comissarios - comissario"].id, "instituicoes": [inst_b["id"]]},
        })
        verifica("coordenacao cria comissario na sua edicao", r.status_code == 201, r.text[:140])
        comissario = r.json()["usuario"] if r.status_code == 201 else None

        r = cc.post("/usuarios", json={
            "dados": {"nome": f"{MARCA} Intruso", "email": f"{MARCA.lower()}.int@exemplo.org"},
            "vinculo": {"edicao_id": ed_cau["id"], "perfil_id": perfis["Monitoria - monitores"].id, "instituicoes": []},
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

        print("\nGrupo do comissario")
        if comissario:
            vinculo_id = comissario["vinculos"][0]["id"]
            r = cc.patch(
                f"/usuarios/{comissario['id']}/vinculos/{vinculo_id}",
                json={"grupo": "Elyon"},
            )
            grupo_id = None
            if r.status_code == 200:
                v = r.json()["vinculos"][0]
                grupo_id = v["grupo_id"]
                verifica("nomeia o grupo do comissario", v["grupo"] == "Elyon", str(v))
                verifica("comissario usa grupo", v["usa_grupo"] is True)

            # O ponto do grupo: escrito de outro jeito, cai no MESMO cadastro,
            # com a grafia de quem chegou primeiro.
            r = cc.post("/usuarios", json={
                "dados": {"nome": f"{MARCA} Comissario 2", "email": f"{MARCA.lower()}.c2@exemplo.org"},
                "vinculo": {
                    "edicao_id": ed_for["id"],
                    "perfil_id": perfis["Comissarios - comissario"].id,
                    "instituicoes": [],
                    "grupo": "  élyon ",
                },
            })
            segundo = r.json()["usuario"] if r.status_code == 201 else None
            if segundo:
                v = segundo["vinculos"][0]
                verifica(
                    "grafia diferente cai no grupo que ja existia",
                    v["grupo_id"] == grupo_id and v["grupo"] == "Elyon",
                    str(v),
                )

            r = cc.get(f"/grupos?edicao_id={ed_for['id']}")
            nomes = [g["nome"] for g in r.json()]
            verifica("o grupo aparece uma vez so na sugestao", nomes == ["Elyon"], str(nomes))

            if segundo:
                # Quem nao e comissario nao guarda grupo: o nome sai junto com
                # a funcao, sem a tela precisar pedir.
                r = cc.patch(
                    f"/usuarios/{segundo['id']}/vinculos/{segundo['vinculos'][0]['id']}",
                    json={"perfil_id": perfis["Monitoria - monitores"].id},
                )
                v = r.json()["vinculos"][0] if r.status_code == 200 else {}
                verifica(
                    "virar monitor solta o grupo",
                    v.get("grupo") is None and v.get("usa_grupo") is False,
                    str(v),
                )

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

        print("\nApagar usuario")
        r = ca.delete(f"/usuarios/{admin.id}")
        verifica("ninguem apaga a propria conta", r.status_code == 422, str(r.status_code))

        if comissario:
            r = cc.get(f"/usuarios/{comissario['id']}/dependencias")
            conta = {i["chave"]: i["quantidade"] for i in r.json().get("itens", [])}
            verifica("conta o acesso que vai junto", conta.get("acessos") == 1, str(conta))

            # Ele passa a trabalhar tambem em Caucaia, que esta coordenacao nao
            # gerencia: apagar a conta levaria junto um acesso que ela nao deu.
            r = ca.post(f"/usuarios/{comissario['id']}/vinculos", json={
                "edicao_id": ed_cau["id"], "perfil_id": perfis["Monitoria - monitores"].id, "instituicoes": [],
            })
            verifica("admin da um segundo vinculo", r.status_code == 201, r.text[:110])
            vinculo_caucaia = r.json()["vinculos"]
            fora = next((v for v in vinculo_caucaia if v["edicao_id"] == ed_cau["id"]), None)

            r = cc.delete(f"/usuarios/{comissario['id']}")
            verifica(
                "coordenacao NAO apaga quem tem vinculo fora do alcance dela",
                r.status_code == 403,
                str(r.status_code),
            )

            if fora:
                # Nao ha rota de apagar vinculo (a tela desativa), e o assunto
                # daqui e outro: tira pelo banco e segue.
                db.execute(delete(UsuarioInstituicao).where(
                    UsuarioInstituicao.usuario_edicao_id == fora["id"]
                ))
                db.execute(delete(UsuarioEdicao).where(UsuarioEdicao.id == fora["id"]))
                db.commit()

            r = cc.delete(f"/usuarios/{comissario['id']}")
            verifica("coordenacao apaga usuario da sua edicao", r.status_code == 204, r.text[:110])

            db.expire_all()
            verifica("a conta saiu", db.get(Usuario, comissario["id"]) is None)
            sobrou = db.scalar(
                select(func.count())
                .select_from(UsuarioEdicao)
                .where(UsuarioEdicao.usuario_id == comissario["id"])
            )
            verifica("o acesso dele saiu junto", sobrou == 0, str(sobrou))

        print("\nA coordenacao e da cidade, e nao do ano")
        # Fortaleza abre 2027. A coordenacao de 2026 tem de entrar sozinha: a
        # cidade e a mesma, e sem isto o ano abriria sem ninguem podendo
        # cadastrar coisa alguma ate a administracao geral se lembrar dela.
        r = ca.post("/edicoes", json={
            "cidade_id": fortaleza["id"], "ano": 2027,
            "nome": f"{MARCA} Fortaleza 2027", "valor_cesta": "130.00", "valor_festa": "70.00",
        })
        verifica("admin abre o ano seguinte da cidade", r.status_code == 201, r.text[:110])
        ed_for27 = r.json() if r.status_code == 201 else None

        if ed_for27:
            r = cc.get("/edicoes")
            anos = sorted(e["ano"] for e in r.json())
            verifica("a edicao nova ja nasce com a coordenacao da cidade dentro",
                     anos == [2026, 2027], str(anos))

            # E o caminho de ida: nomear numa edicao nomeia na cidade inteira.
            r = ca.post("/usuarios", json={
                "dados": {"nome": f"{MARCA} Coord 2", "email": f"{MARCA.lower()}.coord2@exemplo.org"},
                "vinculo": {
                    "edicao_id": ed_for27["id"],
                    "perfil_id": perfis["Coordenacao"].id,
                    "instituicoes": [],
                },
            })
            verifica("admin nomeia uma segunda coordenacao", r.status_code == 201, r.text[:160])
            coord2 = r.json()["usuario"] if r.status_code == 201 else None

            if coord2:
                anos = sorted(v["ano"] for v in coord2["vinculos"])
                verifica("nomear numa edicao vale em todas as edicoes ativas da cidade",
                         anos == [2026, 2027], str(anos))
                verifica("e nao encosta em cidade nenhuma alem da dela",
                         {v["cidade"] for v in coord2["vinculos"]} == {f"{MARCA} Fortaleza"},
                         str([v["cidade"] for v in coord2["vinculos"]]))

                # O acesso e um so: suspender numa edicao suspende na cidade.
                v26 = next(v for v in coord2["vinculos"] if v["ano"] == 2026)
                r = ca.patch(
                    f"/usuarios/{coord2['id']}/vinculos/{v26['id']}", json={"ativo": False}
                )
                ativos = [v["ativo"] for v in r.json()["vinculos"]] if r.status_code == 200 else []
                verifica("suspender a coordenacao numa edicao suspende na cidade",
                         ativos == [False, False], str(ativos))

                # E justamente por alcancar a cidade inteira, isso nao e de
                # quem coordena: e de quem nomeia a coordenacao.
                r = cc.patch(
                    f"/usuarios/{coord2['id']}/vinculos/{v26['id']}", json={"ativo": True}
                )
                verifica("coordenacao NAO mexe no acesso de outra coordenacao",
                         r.status_code == 403, str(r.status_code))

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

        print("\nApagar instituicao: a conta antes, as criancas junto")
        # Cenario: a Escola B com duas criancas, uma delas ja apadrinhada.
        padrinho = Padrinho(edicao_id=ed_for["id"], nome=f"{MARCA} Padrinho")
        db.add(padrinho)
        db.flush()
        b1 = Crianca(
            edicao_id=ed_for["id"], instituicao_id=inst_b["id"],
            codigo="B01", nome=f"{MARCA} Crianca B1", idade=7, sexo="M",
        )
        b2 = Crianca(
            edicao_id=ed_for["id"], instituicao_id=inst_b["id"],
            codigo="B02", nome=f"{MARCA} Crianca B2", idade=9, sexo="F",
        )
        db.add_all([b1, b2])
        db.flush()
        apadrinhamento = Apadrinhamento(
            crianca_id=b1.id, padrinho_id=padrinho.id,
            tipo="cesta", valor=Decimal("120.00"),
        )
        db.add(apadrinhamento)
        db.commit()
        padrinho_id, apadrinhamento_id = padrinho.id, apadrinhamento.id

        r = ca.get(f"/instituicoes/{inst_b['id']}/dependencias")
        conta = {i["chave"]: i["quantidade"] for i in r.json().get("itens", [])}
        verifica("conta as criancas da instituicao", conta.get("criancas") == 2, str(conta))
        verifica(
            "conta o apadrinhamento que cai junto com a crianca",
            conta.get("apadrinhamentos") == 1,
            str(conta),
        )
        verifica(
            "nao conta o padrinho, que e da edicao e nao da instituicao",
            "padrinhos" not in conta,
            str(conta),
        )

        r = cc.delete(f"/instituicoes/{inst_c['id']}?confirmar=true")
        verifica(
            "coordenacao NAO apaga instituicao de outra cidade",
            r.status_code == 403,
            str(r.status_code),
        )

        r = ca.delete(f"/instituicoes/{inst_b['id']}")
        verifica(
            "recusa apagar instituicao com dados sem confirmar",
            r.status_code == 409,
            f"{r.status_code} {r.text[:90]}",
        )

        r = ca.delete(f"/instituicoes/{inst_b['id']}?confirmar=true")
        verifica("apaga instituicao confirmada", r.status_code == 204, r.text[:110])

        db.expire_all()
        verifica(
            "as criancas da instituicao sairam",
            db.scalar(
                select(func.count()).select_from(Crianca)
                .where(Crianca.instituicao_id == inst_b["id"])
            ) == 0,
        )
        verifica(
            "o apadrinhamento saiu junto com a crianca",
            db.get(Apadrinhamento, apadrinhamento_id) is None,
        )
        verifica(
            "o padrinho continua: ele e da edicao, nao da instituicao",
            db.get(Padrinho, padrinho_id) is not None,
        )

        print("\nApagar edicao: leva o ano, deixa as instituicoes")
        a1 = Crianca(
            edicao_id=ed_for["id"], instituicao_id=inst_a["id"],
            codigo="A01", nome=f"{MARCA} Crianca A1", idade=10, sexo="F",
        )
        db.add(a1)
        db.commit()

        r = ca.get(f"/edicoes/{ed_for['id']}/dependencias")
        conta = {i["chave"]: i["quantidade"] for i in r.json().get("itens", [])}
        verifica("conta a crianca da edicao", conta.get("criancas") == 1, str(conta))
        verifica("conta o padrinho da edicao", conta.get("padrinhos") == 1, str(conta))
        verifica("conta o acesso da equipe a edicao", conta.get("acessos", 0) >= 1, str(conta))
        verifica(
            "nao conta instituicoes: o cadastro delas atravessa os anos",
            "instituicoes" not in conta,
            str(conta),
        )

        r = cc.delete(f"/edicoes/{ed_for['id']}?confirmar=true")
        verifica("coordenacao NAO apaga edicao", r.status_code == 403, str(r.status_code))

        r = ca.delete(f"/edicoes/{ed_for['id']}")
        verifica("recusa apagar edicao com dados sem confirmar", r.status_code == 409)

        r = ca.delete(f"/edicoes/{ed_for['id']}?confirmar=true")
        verifica("apaga edicao confirmada", r.status_code == 204, r.text[:110])

        db.expire_all()
        verifica("a edicao saiu", db.get(Edicao, ed_for["id"]) is None)
        verifica("o padrinho da edicao saiu junto", db.get(Padrinho, padrinho_id) is None)
        verifica(
            "a instituicao da cidade continua de pe",
            db.get(Instituicao, inst_a["id"]) is not None,
        )

        print("\nApagar cidade: leva as edicoes e as instituicoes dela")
        r = ca.post("/cidades", json={"nome": f"{MARCA} Sobral", "uf": "CE"})
        sobral = r.json()
        r = ca.delete(f"/cidades/{sobral['id']}")
        verifica(
            "cidade sem nada ligado a ela nao precisa de confirmacao",
            r.status_code == 204,
            f"{r.status_code} {r.text[:90]}",
        )

        r = ca.get(f"/cidades/{caucaia['id']}/dependencias")
        conta = {i["chave"]: i["quantidade"] for i in r.json().get("itens", [])}
        verifica("conta a edicao da cidade", conta.get("edicoes") == 1, str(conta))
        verifica("conta a instituicao da cidade", conta.get("instituicoes") == 1, str(conta))

        r = ca.delete(f"/cidades/{caucaia['id']}")
        verifica("recusa apagar cidade com dados sem confirmar", r.status_code == 409)

        r = ca.delete(f"/cidades/{caucaia['id']}?confirmar=true")
        verifica("apaga cidade confirmada", r.status_code == 204, r.text[:110])

        db.expire_all()
        verifica("a cidade saiu", db.get(Cidade, caucaia["id"]) is None)
        verifica("a edicao dela saiu junto", db.get(Edicao, ed_cau["id"]) is None)
        verifica("a instituicao dela saiu junto", db.get(Instituicao, inst_c["id"]) is None)

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
