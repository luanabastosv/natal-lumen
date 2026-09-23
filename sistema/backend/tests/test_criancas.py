"""Testa criancas e importacao de listas (fase 5).

O que mais importa aqui e o isolamento: crianca e dado sensivel, e comissario
ou monitor so pode alcancar as das instituicoes atribuidas a ele.

Rodar com:  python -m tests.test_criancas
"""

import io

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    Cidade,
    Crianca,
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

MARCA = "ZZ_CRI"
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

    cidades = db.scalars(select(Cidade).where(Cidade.nome.like(f"{MARCA}%"))).all()
    cids = [c.id for c in cidades]
    if cids:
        eds = list(db.scalars(select(Edicao.id).where(Edicao.cidade_id.in_(cids))).all())
        if eds:
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


def planilha(linhas: list[dict]) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(linhas).to_excel(buf, index=False)
    return buf.getvalue()


def main() -> None:
    db = SessionLocal()
    log_inicial = db.scalar(select(func.max(LogAtividade.id))) or 0
    limpar(db)

    perfis = {p.nome: p for p in db.scalars(select(Perfil)).all()}

    cidade = Cidade(nome=f"{MARCA} Cidade", uf="CE")
    db.add(cidade)
    db.flush()
    edicao = Edicao(
        cidade_id=cidade.id, ano=2026, nome=f"{MARCA} Edicao 2026",
        valor_cesta=120, valor_festa=60,
    )
    db.add(edicao)
    db.flush()
    inst_a = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola A")
    inst_b = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola B")
    db.add_all([inst_a, inst_b])
    db.flush()

    def criar_usuario(sufixo, perfil, instituicoes=()):
        u = Usuario(
            nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
            senha_hash=gerar_hash(SENHA),
        )
        db.add(u)
        db.flush()
        v = UsuarioEdicao(usuario_id=u.id, edicao_id=edicao.id, perfil_id=perfis[perfil].id)
        db.add(v)
        db.flush()
        for i in instituicoes:
            db.add(UsuarioInstituicao(usuario_edicao_id=v.id, instituicao_id=i))
        return u

    coord = criar_usuario("Coord", "Coordenacao")
    comissario = criar_usuario("Comissario", "Comissario", [inst_a.id])
    db.commit()

    try:
        cc = TestClient(app)
        entrar(cc, coord.email)
        ck = TestClient(app)
        entrar(ck, comissario.email)

        print("\nCadastro manual")
        r = cc.post("/criancas", json={
            "edicao_id": edicao.id, "instituicao_id": inst_a.id,
            "codigo": "001", "nome": "  Ana   Clara  Avila ", "idade": 8, "sexo": "F",
        })
        verifica("coordenacao cadastra crianca", r.status_code == 201, r.text[:120])
        ana = r.json() if r.status_code == 201 else {}
        verifica("espacos extras do nome sao limpos", ana.get("nome") == "Ana Clara Avila", str(ana.get("nome")))

        r = cc.post("/criancas", json={
            "edicao_id": edicao.id, "instituicao_id": inst_a.id,
            "codigo": "001", "nome": "Outra Crianca", "idade": 9, "sexo": "F",
        })
        verifica("recusa codigo repetido na mesma instituicao", r.status_code == 409)

        r = cc.post("/criancas", json={
            "edicao_id": edicao.id, "instituicao_id": inst_b.id,
            "codigo": "001", "nome": "Bruno Lima", "idade": 10, "sexo": "M",
        })
        verifica("o mesmo codigo vale noutra instituicao", r.status_code == 201, r.text[:120])
        bruno = r.json() if r.status_code == 201 else {}

        r = cc.post("/criancas", json={
            "edicao_id": edicao.id, "instituicao_id": inst_a.id,
            "codigo": "003", "nome": "X", "idade": 8, "sexo": "F",
        })
        verifica("recusa nome curto demais", r.status_code == 422)

        r = cc.post("/criancas", json={
            "edicao_id": edicao.id, "instituicao_id": inst_a.id,
            "codigo": "004", "nome": "Idade Errada", "idade": 99, "sexo": "F",
        })
        verifica("recusa idade fora da faixa", r.status_code == 422)

        print("\nIsolamento por instituicao")
        r = ck.get("/criancas")
        nomes = [c["nome"] for c in r.json()["itens"]]
        verifica("comissario so ve as criancas da instituicao dele", nomes == ["Ana Clara Avila"], str(nomes))

        r = cc.get("/criancas")
        verifica("coordenacao ve as duas", r.json()["total"] == 2, str(r.json()["total"]))

        r = ck.get(f"/criancas/{bruno['id']}")
        verifica("comissario recebe 404 na crianca de outra instituicao", r.status_code == 404)

        r = ck.get("/criancas", params={"busca": "Bruno"})
        verifica("busca por nome nao escapa do filtro", r.json()["total"] == 0, str(r.json()["total"]))

        print("\nEscape por codigo exato")
        r = ck.get("/criancas", params={"codigo": bruno["codigo"]})
        achados = [c["nome"] for c in r.json()["itens"]]
        verifica(
            "busca por codigo exato alcanca outra instituicao da edicao",
            "Bruno Lima" in achados,
            str(achados),
        )

        registros = db.scalars(
            select(LogAtividade).where(
                LogAtividade.acao == "busca_por_codigo",
                LogAtividade.usuario_id == comissario.id,
            )
        ).all()
        verifica("o uso do escape fica registrado em log", len(registros) >= 1)

        print("\nEdicao e remocao")
        r = ck.patch(f"/criancas/{bruno['id']}", json={"nome": "Tentando Mudar"})
        verifica("comissario nao edita crianca fora do alcance", r.status_code in (403, 404), str(r.status_code))

        r = cc.patch(f"/criancas/{ana['id']}", json={"idade": 9, "observacoes": "alergia a amendoim"})
        verifica("coordenacao edita crianca", r.status_code == 200 and r.json()["idade"] == 9, r.text[:110])

        print("\nImportacao de lista")
        arquivo = planilha([
            {"Matrícula": "010", "Nome Completo": "Carla Souza", "Idade": "7", "Sexo": "Feminino", "Escola": f"{MARCA} Escola A"},
            {"Matrícula": "011", "Nome Completo": "Diego Alves", "Idade": "9", "Sexo": "M", "Escola": f"{MARCA} escola a"},
            {"Matrícula": "011", "Nome Completo": "Repetido", "Idade": "9", "Sexo": "M", "Escola": f"{MARCA} Escola A"},
            {"Matrícula": "001", "Nome Completo": "Ja Existe", "Idade": "8", "Sexo": "F", "Escola": f"{MARCA} Escola A"},
            {"Matrícula": "012", "Nome Completo": "Ana Clara Ávila", "Idade": "8", "Sexo": "F", "Escola": f"{MARCA} Escola A"},
        ])

        r = cc.post(
            "/criancas/importar",
            files={"arquivo": ("lista.xlsx", arquivo, "application/vnd.ms-excel")},
            data={"edicao_id": str(edicao.id)},
        )
        verifica("analisa a planilha", r.status_code == 200, r.text[:160])
        previa = r.json() if r.status_code == 200 else {}

        if previa:
            verifica("reconhece as colunas com acento e nome diferente",
                     previa["colunas_reconhecidas"].get("codigo") == "Matrícula")
            verifica("conta 5 linhas", previa["total"] == 5, str(previa["total"]))
            verifica("aponta 3 validas", previa["validas"] == 3, str(previa["validas"]))
            verifica("aponta 2 com erro", previa["com_erro"] == 2, str(previa["com_erro"]))

            por_codigo = {l["codigo"]: l for l in previa["linhas"]}
            verifica("aponta o codigo repetido no arquivo",
                     any("repetido" in e for e in por_codigo["011"]["erros"] if por_codigo["011"]["erros"]) or
                     any("repetido" in e for e in previa["linhas"][2]["erros"]))
            verifica("aponta quem ja esta na base",
                     any("ja cadastrada" in e for e in por_codigo["001"]["erros"]))
            verifica("avisa nome parecido com quem ja existe",
                     any("parecido" in a for a in por_codigo["012"]["avisos"]),
                     str(por_codigo["012"]["avisos"]))
            verifica("casa a instituicao mesmo escrita diferente",
                     por_codigo["011"]["instituicao_id"] == inst_a.id)

            r = cc.post(f"/criancas/importar/{previa['id']}/confirmar")
            verifica("confirma a importacao", r.status_code == 200, r.text[:130])
            if r.status_code == 200:
                verifica("importa so as 3 validas", r.json()["importadas"] == 3, str(r.json()))

            r = cc.get("/criancas")
            verifica("as criancas importadas aparecem na lista", r.json()["total"] == 5, str(r.json()["total"]))

            r = cc.post(f"/criancas/importar/{previa['id']}/confirmar")
            verifica("a mesma previa nao pode ser confirmada duas vezes", r.status_code == 404)

        print("\nFormatos de planilha que aparecem na vida real")
        # Cada um destes ja quebrou de verdade. O BOM e o pior: sao tres bytes
        # invisiveis que o Excel grava ao salvar como "CSV UTF-8", e a mensagem
        # de erro ficava sem sentido porque na tela as colunas pareciam certas.
        base_csv = (
            "Codigo;Nome;Sexo;Idade\n"
            "CSV1;Teste Um Sobrenome;F;5\n"
            "CSV2;Teste Dois Sobrenome;M;6\n"
        )

        formatos = {
            "csv utf-8 com BOM (Excel)": base_csv.encode("utf-8-sig"),
            "csv utf-8 sem BOM": base_csv.encode("utf-8"),
            "csv windows-1252 (Excel antigo)":
                base_csv.replace("Sobrenome", "Assuncao").encode("cp1252"),
            "csv separado por virgula": base_csv.replace(";", ",").encode("utf-8"),
        }

        for rotulo, dados in formatos.items():
            r = cc.post(
                "/criancas/importar",
                files={"arquivo": ("lista.csv", dados, "text/csv")},
                data={"edicao_id": str(edicao.id), "instituicao_id": str(inst_a.id)},
            )
            verifica(
                f"le {rotulo}",
                r.status_code == 200 and r.json()["total"] == 2,
                f"{r.status_code} {r.text[:90]}",
            )

        # Cabecalho com espaco inquebravel, outro invisivel comum.
        com_nbsp = "Codigo;Nome\u00a0;Sexo;Idade\nNB1;Teste Nbsp Sobrenome;F;5\n"
        r = cc.post(
            "/criancas/importar",
            files={"arquivo": ("lista.csv", com_nbsp.encode("utf-8"), "text/csv")},
            data={"edicao_id": str(edicao.id), "instituicao_id": str(inst_a.id)},
        )
        verifica("le cabecalho com espaco inquebravel",
                 r.status_code == 200 and "nome" in r.json()["colunas_reconhecidas"],
                 f"{r.status_code} {r.text[:90]}")

        print("\nPlanilha sem as colunas minimas")
        ruim = planilha([{"Alguma Coisa": "x", "Outra": "y"}])
        r = cc.post(
            "/criancas/importar",
            files={"arquivo": ("ruim.xlsx", ruim, "application/vnd.ms-excel")},
            data={"edicao_id": str(edicao.id)},
        )
        verifica("recusa planilha sem codigo e nome", r.status_code == 422, str(r.status_code))
        verifica("a mensagem diz o que falta e o que ela aceita",
                 "codigo" in r.text and "nome" in r.text and "matricula" in r.text,
                 r.text[:160])

        print("\nPermissoes")
        r = ck.post(
            "/criancas/importar",
            files={"arquivo": ("lista.xlsx", arquivo, "application/vnd.ms-excel")},
            data={"edicao_id": str(edicao.id)},
        )
        verifica("comissario nao importa listas", r.status_code == 403, str(r.status_code))

        r = ck.post("/criancas", json={
            "edicao_id": edicao.id, "instituicao_id": inst_a.id,
            "codigo": "999", "nome": "Nao Deveria", "idade": 8, "sexo": "F",
        })
        verifica("comissario nao cadastra crianca", r.status_code == 403, str(r.status_code))

        print("\nPaginacao")
        r = cc.get("/criancas", params={"por_pagina": 2, "pagina": 1})
        verifica("respeita o tamanho da pagina", len(r.json()["itens"]) == 2)
        verifica("devolve o total geral", r.json()["total"] == 5)

        print("\nRemocao")
        r = cc.delete(f"/criancas/{bruno['id']}")
        verifica("coordenacao apaga crianca", r.status_code == 204, str(r.status_code))
        r = cc.get(f"/criancas/{bruno['id']}")
        verifica("depois de apagada nao e mais encontrada", r.status_code == 404)

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
