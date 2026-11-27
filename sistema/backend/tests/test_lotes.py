"""Testa o apadrinhamento em lote (um grupo que apadrinhou junto).

Rodar com:  python -m tests.test_lotes
"""

import io
import json
import shutil
import zipfile
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from openpyxl import Workbook
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
    LoteApadrinhamento,
    Padrinho,
    Pagamento,
    Perfil,
    TokenAcesso,
    Usuario,
    UsuarioEdicao,
)
from app.seguranca.senhas import gerar_hash
from app.servicos import arquivos

MARCA = "ZZ_LOTE"
SENHA = "senha-de-teste-123"
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

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
    usuarios = db.scalars(select(Usuario).where(Usuario.nome.ilike(f"{MARCA}%"))).all()
    ids = [u.id for u in usuarios]
    if ids:
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
            db.execute(delete(LoteApadrinhamento).where(LoteApadrinhamento.edicao_id.in_(eds)))
            db.execute(delete(Crianca).where(Crianca.edicao_id.in_(eds)))
            db.execute(delete(UsuarioEdicao).where(UsuarioEdicao.edicao_id.in_(eds)))
            db.execute(delete(Edicao).where(Edicao.id.in_(eds)))
        db.execute(delete(Instituicao).where(Instituicao.cidade_id.in_(cids)))
        db.execute(delete(Cidade).where(Cidade.id.in_(cids)))
    if ids:
        db.execute(delete(Usuario).where(Usuario.id.in_(ids)))
    db.commit()
    pasta = config.caminho_arquivos / "comprovantes" / arquivos.limpar_texto(f"{MARCA} Cidade")
    shutil.rmtree(pasta, ignore_errors=True)


def entrar(cliente: TestClient, email: str):
    r = cliente.post("/auth/login", json={"email": email, "senha": SENHA})
    for nome in (config.cookie_nome, config.cookie_csrf):
        valor = next((ck.value for ck in cliente.cookies.jar if ck.name == nome), None)
        if valor:
            cliente.cookies.set(nome, valor, path="/")
    cliente.headers["X-CSRF-Token"] = next(
        ck.value for ck in cliente.cookies.jar if ck.name == config.cookie_csrf
    )
    return r


def planilha(*linhas) -> bytes:
    livro = Workbook()
    folha = livro.active
    folha.append(["Lista do grupo"])
    folha.append([])
    folha.append(["Nome do padrinho", "WhatsApp"])
    for linha in linhas:
        folha.append(list(linha))
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


def main() -> None:
    db = SessionLocal()
    log_inicial = db.scalar(select(func.max(LogAtividade.id))) or 0
    limpar(db)
    perfis = {p.nome: p for p in db.scalars(select(Perfil)).all()}

    cidade = Cidade(nome=f"{MARCA} Cidade", uf="CE")
    db.add(cidade); db.flush()
    ed = Edicao(cidade_id=cidade.id, ano=2026, nome=f"{MARCA} 2026", valor_cesta=130, valor_festa=130)
    db.add(ed); db.flush()
    escola = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola")
    creche = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Creche")
    db.add_all([escola, creche]); db.flush()
    kids = [
        Crianca(edicao_id=ed.id, instituicao_id=escola.id, codigo=f"ES{n}", nome=f"Crianca {n} Silva",
                idade=8, sexo="F")
        for n in (1, 2, 10, 3)
    ]
    desistente = Crianca(edicao_id=ed.id, instituicao_id=escola.id, codigo="ES4", nome="Desistiu Souza",
                         idade=8, sexo="M", desistiu_em=datetime.now(UTC))
    db.add_all(kids + [desistente]); db.flush()
    es1, es2, es10, es3 = kids

    admin = Usuario(nome=f"{MARCA} Admin", email=f"{MARCA.lower()}.admin@exemplo.org",
                    senha_hash=gerar_hash(SENHA), admin_geral=True)
    coord = Usuario(nome=f"{MARCA} Coord", email=f"{MARCA.lower()}.coord@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
    db.add_all([admin, coord]); db.flush()
    db.add(UsuarioEdicao(usuario_id=coord.id, edicao_id=ed.id, perfil_id=perfis["Coordenacao"].id))
    # Um padrinho que ja existe: o lote tem de usar o cadastro dele.
    antigo = Padrinho(edicao_id=ed.id, nome="Maria Antiga Lima", whatsapp="85988887777")
    db.add(antigo); db.commit()

    try:
        ca = TestClient(app); entrar(ca, admin.email)
        cc = TestClient(app); entrar(cc, coord.email)

        print("\nSo a administracao geral")
        for metodo, caminho in (("get", f"/lotes?edicao_id={ed.id}"),
                                ("get", f"/lotes/instituicoes?edicao_id={ed.id}")):
            r = getattr(cc, metodo)(caminho)
            verifica(f"coordenacao NAO entra em {caminho.split('?')[0]}", r.status_code == 403, str(r.status_code))
        r = cc.post("/lotes", data={"dados": "{}"}, files={"comprovante": ("c.png", PNG, "image/png")})
        verifica("coordenacao NAO grava lote", r.status_code == 403, str(r.status_code))

        print("\nVagas")
        r = ca.get("/lotes/instituicoes", params={"edicao_id": ed.id})
        inst = {i["id"]: i for i in r.json()["instituicoes"]}
        verifica("conta as cestas livres, sem a desistente", inst[escola.id]["cesta_livres"] == 4, r.text[:200])
        verifica("festa fechada nao conta", inst[escola.id]["festa_livres"] == 0)
        r = ca.get("/lotes/vagas", params={"edicao_id": ed.id, "instituicao_ids": str(escola.id)})
        codigos = [c["codigo"] for c in r.json()["criancas"]]
        verifica("vagas em ordem de codigo, ES2 antes de ES10", codigos == ["ES1", "ES2", "ES3", "ES10"], str(codigos))

        print("\nPlanilha")
        arquivo = planilha(
            ("JOSE CARLOS SILVA", "(85) 99999-0001"),
            ("Ana Paula", "85999990002"),
            ("maria antiga lima", "85988887777"),
            ("José Carlos Silva", "85999990001"),
            ("", ""),
            ("Zé", ""),
        )
        r = ca.post("/lotes/ler-planilha", data={"edicao_id": ed.id},
                    files={"arquivo": ("grupo.xlsx", arquivo, "application/octet-stream")})
        verifica("le a planilha com titulo em cima", r.status_code == 200, r.text[:200])
        linhas = r.json()["linhas"]
        verifica("pula a linha vazia", len(linhas) == 5, str(len(linhas)))
        verifica("nome vem arrumado", linhas[0]["nome"] == "Jose Carlos Silva", linhas[0]["nome"])
        verifica("acha o padrinho que ja existe", (linhas[2]["padrinho_existente"] or {}).get("id") == antigo.id)
        verifica("avisa quem aparece duas vezes", any("2 vezes" in a for a in linhas[0]["avisos"]), str(linhas[0]))
        verifica("nome curto e erro", linhas[4]["erros"] == ["nome muito curto"], str(linhas[4]))

        numerados = planilha(("Padrinho Fraternos 1", "85988712107"), ("Padrinho Fraternos 2", "85999987788"))
        r = ca.post("/lotes/ler-planilha", data={"edicao_id": ed.id},
                    files={"arquivo": ("grupo.xlsx", numerados, "application/octet-stream")})
        verifica("'Fraternos 1' e 'Fraternos 2' sao duas pessoas",
                 all(not l["avisos"] for l in r.json()["linhas"]), r.text[:300])

        csv = "Nome,Telefone\nA. Uchoa,(85) 99921-0691\nVinícius Magalhães,(85) 98877-7223\n".encode()
        r = ca.post("/lotes/ler-planilha", data={"edicao_id": ed.id},
                    files={"arquivo": ("grupo.csv", csv, "text/csv")})
        verifica("le o CSV 'Nome,Telefone' separado por virgula",
                 r.status_code == 200 and [l["whatsapp"] for l in r.json()["linhas"]]
                 == ["(85) 99921-0691", "(85) 98877-7223"], r.text[:200])

        print("\nGravar")
        itens = [
            {"linha": 4, "nome": "Jose Carlos Silva", "whatsapp": "(85) 99999-0001", "crianca_id": es1.id, "tipo": "cesta"},
            {"linha": 5, "nome": "Ana Paula", "whatsapp": "85999990002", "crianca_id": es2.id, "tipo": "cesta"},
            {"linha": 6, "nome": "Maria Antiga Lima", "padrinho_id": antigo.id, "crianca_id": es3.id, "tipo": "cesta"},
            {"linha": 7, "nome": "Jose Carlos Silva", "whatsapp": "85999990001", "crianca_id": es10.id, "tipo": "cesta"},
        ]
        corpo = {"edicao_id": ed.id, "nome": "Grupo Teste", "data": "2026-11-27", "forma": "Pix",
                 "chave_envio": "lote-teste-1", "itens": itens}

        ruim = dict(corpo, chave_envio="lote-ruim", itens=itens + [
            {"nome": "Desistente Padrinho", "crianca_id": desistente.id, "tipo": "cesta"}])
        r = ca.post("/lotes", data={"dados": json.dumps(ruim)}, files={"comprovante": ("c.png", PNG, "image/png")})
        verifica("crianca desistente derruba o lote inteiro", r.status_code == 409, r.text[:200])
        verifica("e nada fica gravado",
                 db.scalar(select(func.count()).select_from(Padrinho).where(Padrinho.edicao_id == ed.id)) == 1)

        r = ca.post("/lotes", data={"dados": json.dumps(corpo)}, files={"comprovante": ("c.txt", b"x", "text/plain")})
        verifica("comprovante que nao e imagem nem PDF e recusado", r.status_code == 415, str(r.status_code))

        r = ca.post("/lotes", data={"dados": json.dumps(corpo)}, files={"comprovante": ("c.png", PNG, "image/png")})
        verifica("grava o lote", r.status_code == 201, r.text[:300])
        lote = r.json()
        verifica("tres pessoas, quatro criancas", (lote.get("padrinhos"), lote.get("apadrinhamentos")) == (3, 4),
                 str(lote)[:200])
        verifica("total e a soma", float(lote.get("total", 0)) == 520.0, str(lote.get("total")))

        db.expire_all()
        pags = db.scalars(select(Pagamento).where(Pagamento.lote_id == lote["id"])).all()
        verifica("um pagamento por pessoa", len(pags) == 3, str(len(pags)))
        jose = next(p for p in pags if p.padrinho.nome == "Jose Carlos Silva")
        verifica("quem aparece duas vezes paga as duas", float(jose.valor) == 260.0, str(jose.valor))
        verifica("cada pagamento tem o seu arquivo de comprovante",
                 len({p.comprovante_arquivo for p in pags}) == 3
                 and all((config.caminho_arquivos / p.comprovante_arquivo).is_file() for p in pags))
        verifica("a observacao diz que e do lote", all("Grupo Teste" in (p.observacoes or "") for p in pags))
        verifica("o padrinho antigo nao foi duplicado",
                 db.scalar(select(func.count()).select_from(Padrinho)
                           .where(Padrinho.edicao_id == ed.id, Padrinho.nome.ilike("maria antiga%"))) == 1)

        r = ca.post("/lotes", data={"dados": json.dumps(corpo)}, files={"comprovante": ("c.png", PNG, "image/png")})
        verifica("mesma chave devolve o mesmo lote, sem gravar de novo",
                 r.status_code == 201 and r.json()["id"] == lote["id"]
                 and db.scalar(select(func.count()).select_from(Pagamento).where(Pagamento.lote_id == lote["id"])) == 3)

        r = ca.post("/lotes", data={"dados": json.dumps(dict(corpo, chave_envio="lote-teste-2"))},
                    files={"comprovante": ("c.png", PNG, "image/png")})
        verifica("crianca ja apadrinhada derruba outro lote", r.status_code == 409, r.text[:200])

        print("\nAgradecimentos")
        r = ca.get(f"/lotes/{lote['id']}/agradecimentos")
        verifica("baixa o ZIP", r.status_code == 200 and r.headers["content-type"] == "application/zip",
                 str(r.status_code))
        nomes = sorted(zipfile.ZipFile(io.BytesIO(r.content)).namelist())
        verifica("um arquivo por crianca, com o nome completo do padrinho na frente",
                 nomes == ["ANA_PAULA_ES2_CRIANCA.png", "JOSE_CARLOS_SILVA_ES10_CRIANCA.png",
                           "JOSE_CARLOS_SILVA_ES1_CRIANCA.png", "MARIA_ANTIGA_LIMA_ES3_CRIANCA.png"], str(nomes))
        r = cc.get(f"/lotes/{lote['id']}/agradecimentos")
        verifica("coordenacao NAO baixa o ZIP do lote", r.status_code == 403, str(r.status_code))

        r = ca.get("/lotes", params={"edicao_id": ed.id})
        verifica("o lote aparece na lista", [l["id"] for l in r.json()] == [lote["id"]], r.text[:200])
        r = ca.get(f"/lotes/{lote['id']}")
        verifica("o detalhe traz as quatro linhas", len(r.json()["linhas"]) == 4)
        verifica("ninguem recebeu ainda", all(l["enviado_em"] is None for l in r.json()["linhas"]))

        print("\nEnvio do agradecimento")
        jose_ids = [l["apadrinhamento_id"] for l in r.json()["linhas"] if l["padrinho"] == "Jose Carlos Silva"]
        r = cc.post(f"/lotes/{lote['id']}/enviados", json={"apadrinhamento_ids": jose_ids})
        verifica("coordenacao NAO marca envio do lote", r.status_code == 403, str(r.status_code))
        r = ca.post(f"/lotes/{lote['id']}/enviados", json={"apadrinhamento_ids": jose_ids})
        verifica("marca o envio das duas criancas do Jose", r.status_code == 200, r.text[:200])
        enviados = {l["padrinho"] for l in r.json()["linhas"] if l["enviado_em"]}
        verifica("so o Jose aparece como enviado", enviados == {"Jose Carlos Silva"}, str(enviados))
        r = ca.get(f"/padrinhos/{jose.padrinho_id}")
        verifica("a ficha do padrinho tambem mostra enviado",
                 r.status_code == 200
                 and {a["cartao_status"] for a in r.json()["apadrinhamentos"]} == {"enviado"}, r.text[:200])
        r = ca.post(f"/lotes/{lote['id']}/enviados", json={"apadrinhamento_ids": [999999]})
        verifica("apadrinhamento de fora do lote e recusado", r.status_code == 404, str(r.status_code))
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
