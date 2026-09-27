"""Testa criancas e importacao de listas (fase 5).

O que mais importa aqui e o isolamento: crianca e dado sensivel, e comissario
ou monitor so pode alcancar as das instituicoes atribuidas a ele.

Rodar com:  python -m tests.test_criancas
"""

import io
from datetime import date

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
    Grupo,
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
        # Depois dos vinculos, que sao quem aponta para o grupo.
        db.execute(delete(Grupo).where(Grupo.cidade_id.in_(cids)))
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


def planilha_crua(linhas: list[list]) -> bytes:
    """Planilha linha a linha, para montar cabecalho fora da primeira linha."""
    buf = io.BytesIO()
    pd.DataFrame(linhas).to_excel(buf, index=False, header=False)
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

        print("\nPlanilha SEM codigo: a aplicacao numera")
        # E o formato real: a instituicao manda nome, idade, sexo e instituicao.
        sem_codigo = planilha([
            {"Nome": "Lucas Oliveira", "Idade": "6", "Sexo": "M"},
            {"Nome": "Ana Clara Souza", "Idade": "4", "Sexo": "F"},
            {"Nome": "Beatriz Costa", "Idade": "5", "Sexo": "F"},
            {"Nome": "Sofia Almeida", "Idade": "2", "Sexo": "F"},
            {"Nome": "Alice Rocha", "Idade": "5", "Sexo": "F"},
            {"Nome": "Davi Martins", "Idade": "2", "Sexo": "M"},
        ])
        r = cc.post(
            "/criancas/importar",
            files={"arquivo": ("sem_codigo.xlsx", sem_codigo, "application/vnd.ms-excel")},
            data={"edicao_id": str(edicao.id), "instituicao_id": str(inst_b.id)},
        )
        verifica("aceita planilha sem coluna de codigo", r.status_code == 200, r.text[:140])
        previa_sem = r.json() if r.status_code == 200 else {}

        if previa_sem:
            verifica("todas as linhas ficam validas", previa_sem["validas"] == 6,
                     str(previa_sem["validas"]))
            gerados = [(l["codigo"], l["nome"], l["sexo"], l["idade"]) for l in previa_sem["linhas"]]
            por_codigo = sorted(gerados)
            esperado = [
                ("ZZ00", "Sofia Almeida", "F", 2),
                ("ZZ01", "Ana Clara Souza", "F", 4),
                ("ZZ02", "Alice Rocha", "F", 5),
                ("ZZ03", "Beatriz Costa", "F", 5),
                ("ZZ04", "Davi Martins", "M", 2),
                ("ZZ05", "Lucas Oliveira", "M", 6),
            ]
            # A sigla depende do nome da instituicao de teste; comparamos so a
            # ordem de nome, sexo e idade.
            verifica(
                "numera meninas primeiro, depois idade, depois alfabetica",
                [g[1:] for g in por_codigo] == [e[1:] for e in esperado],
                str([g[:2] for g in por_codigo]),
            )
            verifica("a sigla vem da instituicao",
                     all(c[0][:2].isalpha() for c in por_codigo), str(por_codigo[0][0]))

            r = cc.post(f"/criancas/importar/{previa_sem['id']}/confirmar")
            verifica("confirma a importacao sem codigo", r.status_code == 200, r.text[:120])

        print("\nRenumerar uma instituicao")
        r = cc.post("/criancas/renumerar", json={
            "edicao_id": edicao.id, "instituicao_id": inst_b.id, "sigla": "XY",
        })
        verifica("renumera com sigla nova", r.status_code == 200, r.text[:140])
        if r.status_code == 200:
            renumeradas = r.json()
            verifica("todos os codigos ganham a sigla nova",
                     all(c["codigo"].startswith("XY") for c in renumeradas),
                     str([c["codigo"] for c in renumeradas][:3]))
            # Bruno Lima (M, 10) foi cadastrado nesta instituicao antes, e a
            # renumeracao pega a instituicao inteira — por isso ele entra no fim.
            verifica("a ordem se mantem: meninas, idade, alfabetica",
                     [c["nome"] for c in renumeradas] ==
                     ["Sofia Almeida", "Ana Clara Souza", "Alice Rocha", "Beatriz Costa",
                      "Davi Martins", "Lucas Oliveira", "Bruno Lima"],
                     str([(c["nome"], c["sexo"], c["idade"]) for c in renumeradas]))
            verifica("comeca do zero", renumeradas[0]["codigo"] == "XY00",
                     renumeradas[0]["codigo"])

        print("\nListagem vem ordenada por codigo")
        r = cc.get("/criancas", params={"instituicao_id": inst_b.id, "por_pagina": 10})
        lista = [c["codigo"] for c in r.json()["itens"]]
        verifica("a planilha sai na ordem do codigo", lista == sorted(lista), str(lista))

        print("\nTrocar a sigla da instituicao leva os codigos junto")
        # Mudar a sigla no cadastro e deixar ES04 na planilha foi o que
        # aconteceu de verdade: o codigo apontava para uma sigla que nao existia
        # mais. O numero de cada crianca continua o mesmo, so o prefixo muda.
        antes = {
            c["id"]: c["codigo"]
            for c in cc.get("/criancas", params={"instituicao_id": inst_b.id,
                                                 "por_pagina": 50}).json()["itens"]
        }
        r = cc.patch(f"/instituicoes/{inst_b.id}", json={"sigla": "WZ"})
        verifica("coordenacao troca a sigla da instituicao", r.status_code == 200,
                 r.text[:140])
        if r.status_code == 200:
            verifica("a resposta diz quantos codigos mudaram",
                     r.json()["codigos_atualizados"] == len(antes),
                     f"{r.json().get('codigos_atualizados')} de {len(antes)}")

            depois = {
                c["id"]: c["codigo"]
                for c in cc.get("/criancas", params={"instituicao_id": inst_b.id,
                                                     "por_pagina": 50}).json()["itens"]
            }
            verifica("todos os codigos passam para a sigla nova",
                     all(c.startswith("WZ") for c in depois.values()),
                     str(sorted(depois.values())[:3]))
            verifica("o numero de cada crianca continua o mesmo",
                     all(depois[i] == "WZ" + antes[i][2:] for i in antes),
                     str([(antes[i], depois[i]) for i in list(antes)[:3]]))

        # Codigo que veio escrito na planilha ("999") nao tem sigla para trocar,
        # e fica como esta.
        r = cc.post("/criancas", json={
            "edicao_id": edicao.id, "instituicao_id": inst_b.id,
            "codigo": "999", "nome": "Codigo Da Planilha", "idade": 7, "sexo": "F",
        })
        verifica("cadastra crianca com codigo sem sigla", r.status_code == 201, r.text[:110])

        mistura_antes = {
            c["id"]: c["codigo"]
            for c in cc.get("/criancas", params={"instituicao_id": inst_b.id,
                                                 "por_pagina": 50}).json()["itens"]
        }
        com_sigla = {i: c for i, c in mistura_antes.items() if c.startswith("WZ")}
        sem_sigla = {i: c for i, c in mistura_antes.items() if not c.startswith("WZ")}

        r = cc.patch(f"/instituicoes/{inst_b.id}", json={"sigla": "VV"})
        verifica("troca a sigla de novo, com codigos misturados",
                 r.status_code == 200, r.text[:140])
        if r.status_code == 200:
            verifica("conta so os codigos que tinham a sigla antiga",
                     r.json()["codigos_atualizados"] == len(com_sigla),
                     f"{r.json().get('codigos_atualizados')} de {len(com_sigla)}")

            depois_b = {
                c["id"]: c["codigo"]
                for c in cc.get("/criancas", params={"instituicao_id": inst_b.id,
                                                     "por_pagina": 50}).json()["itens"]
            }
            verifica("os codigos com sigla ganham a nova, com o mesmo numero",
                     all(depois_b[i] == "VV" + com_sigla[i][2:] for i in com_sigla),
                     str([(com_sigla[i], depois_b[i]) for i in list(com_sigla)[:3]]))
            verifica("codigo que veio da planilha nao e mexido",
                     all(depois_b[i] == c for i, c in sem_sigla.items()),
                     str([(c, depois_b[i]) for i, c in list(sem_sigla.items())[:3]]))

        # Instituicao que ainda nao tinha sigla: nao ha prefixo antigo para
        # trocar, e os codigos que existem ficam como estao.
        a_antes = {
            c["id"]: c["codigo"]
            for c in cc.get("/criancas", params={"instituicao_id": inst_a.id,
                                                 "por_pagina": 50}).json()["itens"]
        }
        r = cc.patch(f"/instituicoes/{inst_a.id}", json={"sigla": "QQ"})
        a_depois = {
            c["id"]: c["codigo"]
            for c in cc.get("/criancas", params={"instituicao_id": inst_a.id,
                                                 "por_pagina": 50}).json()["itens"]
        }
        verifica("estrear a sigla nao mexe nos codigos que ja existem",
                 r.status_code == 200 and r.json()["codigos_atualizados"] == 0
                 and a_depois == a_antes,
                 f"{r.status_code} {r.json().get('codigos_atualizados')}")

        # Sigla nova que esbarra num codigo que ja existe: recusa e nao deixa
        # nada pela metade — nem a sigla, nem os codigos.
        r = cc.post("/criancas", json={
            "edicao_id": edicao.id, "instituicao_id": inst_b.id,
            "codigo": "TT00", "nome": "Ja Ocupa Tt", "idade": 9, "sexo": "F",
        })
        verifica("cadastra crianca com codigo TT00", r.status_code == 201, r.text[:110])

        r = cc.patch(f"/instituicoes/{inst_b.id}", json={"sigla": "TT"})
        verifica("recusa a sigla que esbarra em codigo existente",
                 r.status_code == 409, f"{r.status_code} {r.text[:110]}")
        sigla_agora = next(
            i["sigla"] for i in cc.get("/instituicoes").json() if i["id"] == inst_b.id
        )
        verifica("e a sigla continua a de antes", sigla_agora == "VV", str(sigla_agora))
        ainda = {
            c["id"]: c["codigo"]
            for c in cc.get("/criancas", params={"instituicao_id": inst_b.id,
                                                 "por_pagina": 50}).json()["itens"]
        }
        verifica("nenhum codigo fica com o valor temporario",
                 not any(c.startswith("~") for c in ainda.values()),
                 str(sorted(ainda.values())[:4]))

        # Editar outro campo nao mexe em codigo nenhum.
        r = cc.patch(f"/instituicoes/{inst_b.id}", json={"responsavel": "Quem Responde"})
        verifica("editar outro campo nao mexe nos codigos",
                 r.status_code == 200 and r.json()["codigos_atualizados"] == 0,
                 f"{r.status_code} {r.text[:110]}")

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

        print("\nIdade escrita do jeito que a instituicao quis")
        # A coluna de idade raramente vem so com o numero: "2 ANOS" era recusado
        # como idade invalida e derrubava a planilha inteira.
        idades = planilha([
            {"Nome": "Idade Escrita Um", "Idade": "2 ANOS", "Sexo": "F"},
            {"Nome": "Idade Escrita Dois", "Idade": "4 anos", "Sexo": "M"},
            {"Nome": "Idade Escrita Tres", "Idade": "10a", "Sexo": "F"},
            {"Nome": "Idade Escrita Quatro", "Idade": "1 ano e 6 meses", "Sexo": "M"},
            {"Nome": "Idade Escrita Cinco", "Idade": "18 meses", "Sexo": "F"},
        ])
        r = cc.post(
            "/criancas/importar",
            files={"arquivo": ("idades.xlsx", idades, "application/vnd.ms-excel")},
            data={"edicao_id": str(edicao.id), "instituicao_id": str(inst_a.id)},
        )
        verifica("le a planilha com a idade escrita em texto", r.status_code == 200,
                 r.text[:140])
        if r.status_code == 200:
            lidas = {l["nome"]: l["idade"] for l in r.json()["linhas"]}
            esperadas = {
                "Idade Escrita Um": 2, "Idade Escrita Dois": 4,
                "Idade Escrita Tres": 10, "Idade Escrita Quatro": 1,
                "Idade Escrita Cinco": 1,
            }
            verifica("entende '2 ANOS', '10a', '1 ano e 6 meses' e '18 meses'",
                     lidas == esperadas, str(lidas))
            verifica("e nenhuma linha fica com erro",
                     r.json()["validas"] == 5, str(r.json()["linhas"][:1]))

        # O que continua sendo erro, e com a mensagem dizendo o que veio escrito.
        sem_idade = planilha([
            {"Nome": "Idade Ruim Um", "Idade": "nao informada", "Sexo": "F"},
            {"Nome": "Idade Ruim Dois", "Idade": "04/03/2015", "Sexo": "M"},
        ])
        r = cc.post(
            "/criancas/importar",
            files={"arquivo": ("ruins.xlsx", sem_idade, "application/vnd.ms-excel")},
            data={"edicao_id": str(edicao.id), "instituicao_id": str(inst_a.id)},
        )
        if r.status_code == 200:
            erros = [e for l in r.json()["linhas"] for e in l["erros"]]
            verifica("aponta a idade que nao deu para entender, com o valor escrito",
                     len(erros) == 2 and all("idade invalida" in e for e in erros)
                     and any("04/03/2015" in e for e in erros),
                     str(erros))

        print("\nCabecalhos que as instituicoes usam de verdade")
        from app.servicos.importador import _mapear_colunas

        variantes = [
            (["nome", "idade", "sexo"], "nome"),
            (["Nome", "Idade", "Sexo"], "Nome"),
            (["NOME", "IDADE", "SEXO"], "NOME"),
            (["Nome completo", "Idade", "Sexo"], "Nome completo"),
            (["Nome Completo", "Idade", "Sexo"], "Nome Completo"),
            (["NOME COMPLETO", "IDADE", "SEXO"], "NOME COMPLETO"),
            (["  Nome  ", "Idade", "Sexo"], "  Nome  "),
            (["Nome da Crianca", "Idade", "Sexo"], "Nome da Crianca"),
            (["Nome do Aluno", "Anos", "Genero"], "Nome do Aluno"),
            (["nome e sobrenome", "idade", "m/f"], "nome e sobrenome"),
            (["Nome Completo da Crianca (sem abreviar)", "Idade", "Sexo"],
             "Nome Completo da Crianca (sem abreviar)"),
            (["NOME DO BENEFICIARIO", "IDADE", "SEXO"], "NOME DO BENEFICIARIO"),
            (["Nome da crianca atendida", "Idade", "Sexo"], "Nome da crianca atendida"),
        ]
        erradas = [
            (cols, esperado, _mapear_colunas(cols)[0].get("nome"))
            for cols, esperado in variantes
            if _mapear_colunas(cols)[0].get("nome") != esperado
        ]
        verifica(
            f"reconhece a coluna de nome em {len(variantes)} escritas diferentes",
            not erradas,
            str(erradas[:2]),
        )

        # O caso perigoso: "nome" aparece duas vezes e uma delas e a instituicao.
        mapa, _ = _mapear_colunas(["Nome da Instituicao", "Nome da Crianca", "Idade", "Sexo"])
        verifica(
            "com duas colunas 'Nome', a da crianca vai para nome",
            mapa.get("nome") == "Nome da Crianca", str(mapa.get("nome")),
        )
        verifica(
            "e a da instituicao vai para instituicao",
            mapa.get("instituicao") == "Nome da Instituicao", str(mapa.get("instituicao")),
        )

        mapa2, _ = _mapear_colunas(["Nome", "Nome da Escola", "Idade", "Sexo"])
        verifica(
            "'Nome' sozinho continua sendo a crianca, mesmo com 'Nome da Escola' ao lado",
            mapa2.get("nome") == "Nome" and mapa2.get("instituicao") == "Nome da Escola",
            f"{mapa2.get('nome')} / {mapa2.get('instituicao')}",
        )

        # Pela API, de ponta a ponta, com o cabecalho todo em maiusculas.
        maiusculas = planilha([
            {"NOME COMPLETO": "Teste Maiusculas Sobrenome", "IDADE": "5", "SEXO": "F"},
        ])
        r = cc.post(
            "/criancas/importar",
            files={"arquivo": ("maiusculas.xlsx", maiusculas, "application/vnd.ms-excel")},
            data={"edicao_id": str(edicao.id), "instituicao_id": str(inst_a.id)},
        )
        verifica("importa planilha com cabecalho em maiusculas",
                 r.status_code == 200 and r.json()["validas"] == 1,
                 f"{r.status_code} {r.text[:120]}")

        print("\nCabecalho fora da primeira linha")
        # Planilha com titulo, subtitulo e linha em branco antes da tabela e
        # comum. Assumir a primeira linha faria o titulo virar nome de coluna.
        com_titulo = planilha_crua([
            ["OBRA LUMEN SER FELIZ", "", ""],
            ["Lista de criancas 2026", "", ""],
            ["", "", ""],
            ["NOME COMPLETO", "IDADE", "SEXO"],
            ["Titulo Deslocado Um", "4", "F"],
            ["Titulo Deslocado Dois", "6", "M"],
        ])
        r = cc.post(
            "/criancas/importar",
            files={"arquivo": ("com_titulo.xlsx", com_titulo, "application/vnd.ms-excel")},
            data={"edicao_id": str(edicao.id), "instituicao_id": str(inst_a.id)},
        )
        verifica("acha o cabecalho na 4a linha", r.status_code == 200, r.text[:140])
        previa_titulo = r.json() if r.status_code == 200 else {}

        if previa_titulo:
            verifica("le so as 2 criancas, nao o titulo",
                     previa_titulo["total"] == 2, str(previa_titulo["total"]))
            verifica("reconhece as colunas do cabecalho deslocado",
                     previa_titulo["colunas_reconhecidas"].get("nome") == "NOME COMPLETO",
                     str(previa_titulo["colunas_reconhecidas"]))
            # A numeracao tem de bater com a que a pessoa ve no Excel.
            linhas_ditas = sorted(l["linha"] for l in previa_titulo["linhas"])
            verifica("numera as linhas como o Excel mostra (5 e 6)",
                     linhas_ditas == [5, 6], str(linhas_ditas))

        # Cabecalho na segunda linha, o caso mais comum.
        segunda = planilha_crua([
            ["LISTA DE CRIANCAS - 2026", "", ""],
            ["Nome", "Idade", "Sexo"],
            ["Segunda Linha Teste", "5", "F"],
        ])
        r = cc.post(
            "/criancas/importar",
            files={"arquivo": ("segunda.xlsx", segunda, "application/vnd.ms-excel")},
            data={"edicao_id": str(edicao.id), "instituicao_id": str(inst_a.id)},
        )
        verifica("acha o cabecalho na 2a linha",
                 r.status_code == 200 and r.json()["total"] == 1,
                 f"{r.status_code} {r.text[:110]}")

        # Em CSV tambem.
        csv_titulo = ("Relatorio da instituicao\n\nNome;Idade;Sexo\n"
                      "Csv Deslocado Teste;7;M\n").encode("utf-8-sig")
        r = cc.post(
            "/criancas/importar",
            files={"arquivo": ("desloc.csv", csv_titulo, "text/csv")},
            data={"edicao_id": str(edicao.id), "instituicao_id": str(inst_a.id)},
        )
        verifica("funciona em CSV tambem",
                 r.status_code == 200 and r.json()["total"] == 1,
                 f"{r.status_code} {r.text[:110]}")

        print("\nPlanilha sem as colunas minimas")
        ruim = planilha([{"Alguma Coisa": "x", "Outra": "y"}])
        r = cc.post(
            "/criancas/importar",
            files={"arquivo": ("ruim.xlsx", ruim, "application/vnd.ms-excel")},
            data={"edicao_id": str(edicao.id)},
        )
        verifica("recusa planilha sem a coluna de nome", r.status_code == 422, str(r.status_code))
        # O codigo nao entra mais: as planilhas vem sem ele, e quem numera e a
        # aplicacao. So o nome e indispensavel.
        verifica("a mensagem diz o que falta e quais nomes aceita",
                 "nome" in r.text.lower() and "crianca" in r.text.lower(),
                 r.text[:200])

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
        total_agora = r.json()["total"]
        verifica("respeita o tamanho da pagina", len(r.json()["itens"]) == 2)
        # Nao fixamos o numero: o teste cria e importa criancas ao longo do
        # caminho, e prender o total aqui quebraria a cada teste novo.
        verifica("devolve o total geral, maior que a pagina",
                 total_agora > 2, str(total_agora))

        print("\nO dia e da INSTITUICAO, nao da crianca")
        from app.models import DiaEvento

        sabado = DiaEvento(edicao_id=edicao.id, data=date(2026, 12, 20), descricao="Sabado")
        domingo = DiaEvento(edicao_id=edicao.id, data=date(2026, 12, 21), descricao="Domingo")
        db.add_all([sabado, domingo]); db.commit()

        r = cc.put(f"/edicoes/{edicao.id}/instituicoes/{inst_a.id}/dia",
                   json={"dia_evento_id": sabado.id})
        verifica("marca o dia da instituicao", r.status_code == 200, r.text[:140])
        if r.status_code == 200:
            verifica("leva as criancas dela junto", r.json()["criancas_atualizadas"] >= 1,
                     str(r.json()["criancas_atualizadas"]))

        r = cc.get("/criancas", params={"instituicao_id": inst_a.id, "por_pagina": 50})
        dias_da_escola = {c["dia_evento"] for c in r.json()["itens"]}
        verifica("TODAS as criancas da instituicao ficam no mesmo dia",
                 len(dias_da_escola) == 1 and "2026-12-20" in dias_da_escola,
                 str(dias_da_escola))

        # A outra instituicao nao foi tocada.
        r = cc.get("/criancas", params={"instituicao_id": inst_b.id, "por_pagina": 50})
        verifica("a outra instituicao continua sem dia",
                 all(c["dia_evento"] is None for c in r.json()["itens"]))

        # Nao existe mais como mudar o dia de UMA crianca.
        uma = db.scalar(select(Crianca).where(Crianca.instituicao_id == inst_a.id))
        r = cc.patch(f"/criancas/{uma.id}", json={"dia_evento_id": domingo.id})
        db.expire_all()
        verifica("mudar o dia de uma crianca so nao tem efeito",
                 db.get(Crianca, uma.id).dia_evento_id == sabado.id,
                 str(db.get(Crianca, uma.id).dia_evento_id))

        r = cc.post("/criancas/lote", json={"criancas": [uma.id], "dia_evento_id": domingo.id,
                                            "definir_dia": True})
        db.expire_all()
        verifica("o lote tambem nao muda o dia de uma crianca",
                 db.get(Crianca, uma.id).dia_evento_id == sabado.id,
                 str(db.get(Crianca, uma.id).dia_evento_id))

        # Trocar a instituicao inteira de dia
        r = cc.put(f"/edicoes/{edicao.id}/instituicoes/{inst_a.id}/dia",
                   json={"dia_evento_id": domingo.id})
        r = cc.get("/criancas", params={"instituicao_id": inst_a.id, "por_pagina": 50})
        verifica("trocar o dia da instituicao move todas de uma vez",
                 {c["dia_evento"] for c in r.json()["itens"]} == {"2026-12-21"},
                 str({c["dia_evento"] for c in r.json()["itens"]}))

        # Uma crianca nova entra ja no dia da instituicao
        r = cc.post("/criancas", json={
            "edicao_id": edicao.id, "instituicao_id": inst_a.id,
            "codigo": "NOVA1", "nome": "Nova Crianca Teste", "idade": 7, "sexo": "F",
        })
        verifica("crianca nova entra ja no dia da instituicao",
                 r.status_code == 201 and r.json()["dia_evento"] == "2026-12-21",
                 f"{r.status_code} {r.json().get('dia_evento')}")

        # Dia de OUTRA edicao, aplicado na edicao que o usuario alcanca.
        outra = Edicao(cidade_id=cidade.id, ano=2027, nome=f"{MARCA} Outra",
                       valor_cesta=1, valor_festa=1)
        db.add(outra); db.flush()
        dia_de_outra = DiaEvento(edicao_id=outra.id, data=date(2027, 12, 19))
        db.add(dia_de_outra); db.commit()

        r = cc.put(f"/edicoes/{edicao.id}/instituicoes/{inst_a.id}/dia",
                   json={"dia_evento_id": dia_de_outra.id})
        verifica("recusa dia que e de outra edicao", r.status_code == 422, str(r.status_code))

        # E a edicao em que o usuario nao tem vinculo responde 404.
        r = cc.put(f"/edicoes/{outra.id}/instituicoes/{inst_a.id}/dia",
                   json={"dia_evento_id": dia_de_outra.id})
        verifica("edicao fora do alcance responde 404", r.status_code == 404, str(r.status_code))

        r = cc.get("/criancas/resumo-instituicoes", params={"edicao_id": edicao.id})
        aba = next(a for a in r.json() if a["instituicao_id"] == inst_a.id)
        verifica("a aba mostra o dia da instituicao", aba["dia_evento"] == "2026-12-21",
                 str(aba.get("dia_evento")))

        # Desmarcar
        r = cc.put(f"/edicoes/{edicao.id}/instituicoes/{inst_a.id}/dia",
                   json={"dia_evento_id": None})
        r = cc.get("/criancas", params={"instituicao_id": inst_a.id, "por_pagina": 50})
        verifica("desmarcar tira o dia de todas",
                 all(c["dia_evento"] is None for c in r.json()["itens"]))

        print("\nFicha da crianca")
        r = cc.get(f"/criancas/{ana['id']}")
        verifica("abre a ficha", r.status_code == 200, r.text[:130])
        ficha = r.json() if r.status_code == 200 else {}

        if ficha:
            verifica("traz os dados da crianca", ficha["nome"] == "Ana Clara Avila")
            verifica("traz a edicao e a instituicao",
                     ficha["instituicao"] and ficha["edicao"])
            verifica("traz kit e cartoes", "kit_status" in ficha and "cartoes" in ficha)
            verifica("sem padrinho, a lista vem vazia", ficha["padrinhos"] == [],
                     str(ficha["padrinhos"]))

        # Agora com padrinho, para conferir nome e contato.
        from app.models import Apadrinhamento, Padrinho

        padrinho = Padrinho(edicao_id=edicao.id, nome=f"{MARCA} Jose Doador",
                            whatsapp="85999990000", email="jose@exemplo.org")
        db.add(padrinho); db.flush()
        db.add(Apadrinhamento(crianca_id=ana["id"], padrinho_id=padrinho.id,
                              tipo="cesta", valor=120))
        db.commit()

        r = cc.get(f"/criancas/{ana['id']}")
        ficha = r.json()
        verifica("com padrinho, a ficha lista o apadrinhamento",
                 len(ficha["padrinhos"]) == 1, str(len(ficha["padrinhos"])))
        if ficha["padrinhos"]:
            p0 = ficha["padrinhos"][0]
            verifica("coordenacao ve o nome do padrinho", p0["nome"] == f"{MARCA} Jose Doador", p0["nome"])
            verifica("coordenacao ve o WhatsApp", p0["whatsapp"] == "85999990000", str(p0["whatsapp"]))
            verifica("mostra o tipo e se esta pago",
                     p0["tipo"] == "cesta" and p0["pago"] is False)

        # O monitor tem ver_criancas mas NAO ver_padrinhos.
        monitor = Usuario(nome=f"{MARCA} Monitor", email=f"{MARCA.lower()}.mon@exemplo.org",
                          senha_hash=gerar_hash(SENHA))
        db.add(monitor); db.flush()
        vm = UsuarioEdicao(usuario_id=monitor.id, edicao_id=edicao.id,
                           perfil_id=perfis["Monitor"].id)
        db.add(vm); db.flush()
        db.add(UsuarioInstituicao(usuario_edicao_id=vm.id, instituicao_id=inst_a.id))
        db.commit()

        cmon = TestClient(app); entrar(cmon, monitor.email)
        r = cmon.get(f"/criancas/{ana['id']}")
        verifica("monitor abre a ficha", r.status_code == 200, str(r.status_code))
        do_monitor = r.json() if r.status_code == 200 else {}

        if do_monitor.get("padrinhos"):
            pm = do_monitor["padrinhos"][0]
            verifica("monitor SABE que ha padrinho", pm["tipo"] == "cesta")
            verifica("monitor NAO ve o nome do padrinho",
                     f"{MARCA} Jose Doador" not in pm["nome"], pm["nome"])
            verifica("monitor NAO ve o WhatsApp", pm["whatsapp"] is None, str(pm["whatsapp"]))
            verifica("monitor NAO ve o email", pm["email"] is None, str(pm["email"]))
            verifica("a ficha avisa que o contato esta oculto",
                     do_monitor["pode_ver_contato"] is False)

        r = cmon.get(f"/criancas/{bruno['id']}")
        verifica("monitor nao abre ficha de crianca fora do alcance",
                 r.status_code == 404, str(r.status_code))

        print("\nDesistencia")
        r = cc.patch(f"/criancas/{ana['id']}/desistencia", json={"desistiu": True})
        verifica("coordenacao marca que a crianca desistiu",
                 r.status_code == 200 and r.json()["desistiu_em"] is not None, r.text[:110])

        r = cc.get("/criancas", params={"edicao_id": edicao.id, "busca": "Ana"})
        itens = r.json()["itens"] if r.status_code == 200 else []
        verifica("quem desistiu CONTINUA na planilha",
                 any(i["id"] == ana["id"] for i in itens), str(len(itens)))
        marcada = next((i for i in itens if i["id"] == ana["id"]), {})
        verifica("e a listagem diz que desistiu", marcada.get("desistiu_em") is not None)

        r = cc.get(f"/criancas/{ana['id']}")
        verifica("a ficha tambem diz", r.json().get("desistiu_em") is not None, r.text[:110])

        antes = db.scalar(
            select(func.count()).select_from(LogAtividade)
            .where(LogAtividade.acao == "crianca_desistiu", LogAtividade.registro_id == ana["id"])
        )
        cc.patch(f"/criancas/{ana['id']}/desistencia", json={"desistiu": True})
        depois = db.scalar(
            select(func.count()).select_from(LogAtividade)
            .where(LogAtividade.acao == "crianca_desistiu", LogAtividade.registro_id == ana["id"])
        )
        verifica("marcar de novo nao registra outra vez", antes == depois, f"{antes} -> {depois}")

        r = cc.patch(f"/criancas/{ana['id']}/desistencia", json={"desistiu": False})
        verifica("e da para voltar atras",
                 r.status_code == 200 and r.json()["desistiu_em"] is None, r.text[:110])

        r = ck.patch(f"/criancas/{bruno['id']}/desistencia", json={"desistiu": True})
        verifica("comissario nao marca crianca fora do alcance",
                 r.status_code in (403, 404), str(r.status_code))

        print("\nTime de comissarios por instituicao")
        # Duas outras comissarias na MESMA Escola A: a instituicao e atendida
        # por um time, nao por uma pessoa.
        bia = criar_usuario("Bia", "Comissario", [inst_a.id])
        caio = criar_usuario("Caio", "Comissario", [inst_a.id, inst_b.id])
        db.commit()
        cb = TestClient(app); entrar(cb, bia.email)

        r = cc.get("/criancas/comissarios", params={"edicao_id": edicao.id})
        time = {c["nome"]: c for c in r.json()} if r.status_code == 200 else {}
        verifica("lista o time de comissarios da edicao", r.status_code == 200, r.text[:140])

        # A lista nao e so de comissarios: coordenacao e administracao geral
        # tambem podem ficar com uma crianca no nome. Por isso a conta e pelo
        # papel, e nao pelo tamanho da lista.
        so_comissarios = [n for n, c in time.items() if c["papel"] == "Comissario"]
        verifica("os tres comissarios estao no time",
                 len(so_comissarios) == 3, str(sorted(so_comissarios)))
        verifica("cada um traz as instituicoes que atende",
                 time.get(f"{MARCA} Caio", {}).get("instituicoes") == sorted([inst_a.id, inst_b.id]),
                 str(time.get(f"{MARCA} Caio")))
        verifica("o monitor nao entra no time",
                 f"{MARCA} Monitor" not in time, str(sorted(time)))
        verifica("a coordenacao entra no time",
                 time.get(f"{MARCA} Coord", {}).get("papel") == "Coordenacao",
                 str(time.get(f"{MARCA} Coord")))
        verifica("e alcanca as escolas todas, sem recorte de instituicao",
                 set(time.get(f"{MARCA} Coord", {}).get("instituicoes", []))
                 >= {inst_a.id, inst_b.id},
                 str(time.get(f"{MARCA} Coord")))
        verifica("os comissarios vem antes na lista",
                 [c["papel"] for c in r.json()][:3] == ["Comissario"] * 3,
                 str([c["papel"] for c in r.json()]))

        # E a coordenacao pode mesmo ficar com a crianca no nome dela.
        r = cc.patch(f"/criancas/{ana['id']}", json={"comissario_id": coord.id})
        verifica("coordenacao assume uma crianca como responsavel",
                 r.status_code == 200 and r.json()["comissario_id"] == coord.id,
                 r.text[:140])
        r = cc.patch(f"/criancas/{ana['id']}", json={"comissario_id": comissario.id})
        verifica("e devolve para a comissaria de sempre",
                 r.status_code == 200, r.text[:140])

        r = cb.get("/criancas", params={"instituicao_id": inst_a.id, "por_pagina": 100})
        quantas_bia = r.json()["total"]
        r = ck.get("/criancas", params={"instituicao_id": inst_a.id, "por_pagina": 100})
        verifica("duas comissarias da mesma escola veem a MESMA lista",
                 quantas_bia == r.json()["total"] and quantas_bia > 0,
                 f"{quantas_bia} x {r.json()['total']}")

        print("\nComissario responsavel pela crianca")
        r = cc.patch(f"/criancas/{ana['id']}", json={"comissario_id": bia.id})
        verifica("coordenacao poe a responsavel", r.status_code == 200, r.text[:140])
        verifica("a linha passa a trazer o nome dela",
                 r.json().get("comissario") == f"{MARCA} Bia", str(r.json().get("comissario")))
        verifica("e o id, para a tela montar o seletor",
                 r.json().get("comissario_id") == bia.id, str(r.json().get("comissario_id")))

        # O grupo da comissaria viaja junto com o nome dela: e a coluna Grupo
        # da planilha, e sai do cadastro dela nesta edicao — nao da crianca.
        bia_vinculo = next(
            u["vinculos"][0]["id"] for u in cc.get("/usuarios").json() if u["id"] == bia.id
        )
        cc.patch(f"/usuarios/{bia.id}/vinculos/{bia_vinculo}", json={"grupo": "Elyon"})
        r = cc.get(f"/criancas/{ana['id']}")
        verifica("a crianca traz o grupo da comissaria",
                 r.json().get("comissario_grupo") == "Elyon",
                 str(r.json().get("comissario_grupo")))

        # O ponto do time: quem NAO e responsavel continua alcancando a crianca.
        r = ck.get(f"/criancas/{ana['id']}")
        verifica("o outro comissario do time ainda abre a ficha",
                 r.status_code == 200, str(r.status_code))
        verifica("e ve de quem ela e",
                 r.json().get("comissario") == f"{MARCA} Bia", str(r.json().get("comissario")))

        r = ck.patch(f"/criancas/{ana['id']}", json={"comissario_id": comissario.id})
        verifica("comissario NAO se atribui a crianca (e da coordenacao)",
                 r.status_code == 403, str(r.status_code))

        r = cc.patch(f"/criancas/{bruno['id']}", json={"comissario_id": bia.id})
        verifica("recusa responsavel que nao esta no time da escola",
                 r.status_code == 422, str(r.status_code))
        verifica("e a mensagem diz o que fazer",
                 "time" in r.text.lower() and "usuarios" in r.text.lower(), r.text[:200])

        r = cc.patch(f"/criancas/{ana['id']}", json={"comissario_id": monitor.id})
        verifica("recusa monitor como responsavel", r.status_code == 422, str(r.status_code))

        r = cc.patch(f"/criancas/{ana['id']}", json={"comissario_id": None})
        verifica("mandar null solta a crianca",
                 r.status_code == 200 and r.json()["comissario_id"] is None, r.text[:140])

        print("\nAtribuir criancas especificas, em lote")
        da_escola_a = cc.get(
            "/criancas", params={"instituicao_id": inst_a.id, "por_pagina": 100}
        ).json()["itens"]
        metade = [c["id"] for c in da_escola_a[:2]]
        r = cc.post("/criancas/lote", json={"criancas": metade, "comissario_id": bia.id})
        verifica("divide parte da escola com uma comissaria", r.status_code == 200, r.text[:160])
        verifica("todas as marcadas saem com ela",
                 all(c["comissario_id"] == bia.id for c in r.json()), r.text[:160])

        resto = [c["id"] for c in da_escola_a[2:4]]
        if resto:
            r = cc.post("/criancas/lote", json={"criancas": resto, "comissario_id": caio.id})
            verifica("e o resto com outro, na mesma escola", r.status_code == 200, r.text[:160])

        r = cc.post("/criancas/lote", json={"criancas": metade, "comissario_id": None})
        verifica("o lote tambem solta", 
                 r.status_code == 200 and all(c["comissario_id"] is None for c in r.json()),
                 r.text[:160])

        # De volta com a Bia, para os filtros terem o que achar.
        cc.post("/criancas/lote", json={"criancas": metade, "comissario_id": bia.id})

        print("\nFiltro por responsavel")
        r = cc.get("/criancas", params={"comissario_id": bia.id, "por_pagina": 100})
        verifica("filtra as criancas de uma comissaria",
                 r.json()["total"] == len(metade), str(r.json()["total"]))
        verifica("e sao exatamente as dela",
                 all(c["comissario_id"] == bia.id for c in r.json()["itens"]), r.text[:160])

        r = cc.get("/criancas", params={
            "instituicao_id": inst_a.id, "sem_comissario": "true", "por_pagina": 100,
        })
        verifica("filtra as que ainda nao tem responsavel",
                 all(c["comissario_id"] is None for c in r.json()["itens"]), r.text[:160])

        r = cc.get("/criancas/resumo-instituicoes", params={"edicao_id": edicao.id})
        aba_a = next((a for a in r.json() if a["instituicao_id"] == inst_a.id), {})
        verifica("a aba da instituicao conta quantas estao sem responsavel",
                 aba_a.get("sem_comissario") == aba_a.get("criancas") - len(metade) - len(resto),
                 f"{aba_a.get('sem_comissario')} de {aba_a.get('criancas')}")

        print("\nO responsavel cai quando deixa de alcancar a crianca")
        # Mudar de escola: a Bia nao esta no time da Escola B.
        r = cc.post("/criancas/lote", json={
            "criancas": metade[:1], "instituicao_id": inst_b.id,
        })
        verifica("mudar de escola solta a responsavel que nao atende a nova",
                 r.status_code == 200 and r.json()[0]["comissario_id"] is None,
                 r.text[:160])

        # Tirar a Escola A da Bia: as criancas dela naquela escola ficam sem
        # responsavel, porque ela nao as alcanca mais.
        ainda_da_bia = cc.get(
            "/criancas", params={"comissario_id": bia.id, "por_pagina": 100}
        ).json()
        verifica("antes de tirar, ela ainda tem criancas",
                 ainda_da_bia["total"] > 0, str(ainda_da_bia["total"]))

        vinculo_bia = db.scalar(
            select(UsuarioEdicao).where(UsuarioEdicao.usuario_id == bia.id)
        )
        r = cc.patch(f"/usuarios/{bia.id}/vinculos/{vinculo_bia.id}",
                     json={"instituicoes": []})
        verifica("coordenacao tira a instituicao da comissaria",
                 r.status_code == 200, r.text[:140])

        r = cc.get("/criancas", params={"comissario_id": bia.id, "por_pagina": 100})
        verifica("e as criancas que estavam no nome dela sao soltas",
                 r.json()["total"] == 0, str(r.json()["total"]))

        r = cc.patch(f"/criancas/{ana['id']}", json={"comissario_id": caio.id})
        verifica("outro comissario do time assume sem problema",
                 r.status_code == 200 and r.json()["comissario_id"] == caio.id, r.text[:140])

        print("\nRemocao")
        # A tela pede a conta antes de apagar: o modal so libera o botao
        # depois de mostrar o que vai junto.
        r = cc.get(f"/criancas/{bruno['id']}/dependencias")
        conta = r.json() if r.status_code == 200 else {}
        verifica("a conta do que vai junto vem antes de apagar",
                 r.status_code == 200, r.text[:140])
        verifica("e vem com o nome de quem sera apagada",
                 conta.get("nome") == bruno["nome"], str(conta.get("nome")))
        chaves = {i["chave"]: i["quantidade"] for i in conta.get("itens", [])}
        verifica("a propria crianca entra na conta", chaves.get("criancas") == 1,
                 str(chaves))
        verifica("nada de edicao ou instituicao e arrastado junto",
                 "edicoes" not in chaves and "instituicoes" not in chaves, str(chaves))

        r = cmon.get(f"/criancas/{bruno['id']}/dependencias")
        verifica("monitor NAO pede a conta (nao apaga crianca)",
                 r.status_code == 403, str(r.status_code))

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
