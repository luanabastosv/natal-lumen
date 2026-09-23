"""Testa kits, compras e check-in (fase 8).

Rodar com:  python -m tests.test_logistica
"""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    Apadrinhamento,
    Cartao,
    Cidade,
    Compra,
    Crianca,
    DiaEvento,
    Edicao,
    Instituicao,
    Kit,
    LogAtividade,
    Padrinho,
    Perfil,
    TokenAcesso,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.seguranca.senhas import gerar_hash

MARCA = "ZZ_LOG"
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

    ids = [u.id for u in db.scalars(select(Usuario).where(Usuario.nome.like(f"{MARCA}%"))).all()]
    if ids:
        db.execute(delete(LogAtividade).where(LogAtividade.usuario_id.in_(ids)))
        db.execute(delete(TokenAcesso).where(TokenAcesso.usuario_id.in_(ids)))

    cids = [c.id for c in db.scalars(select(Cidade).where(Cidade.nome.like(f"{MARCA}%"))).all()]
    if cids:
        eds = list(db.scalars(select(Edicao.id).where(Edicao.cidade_id.in_(cids))).all())
        if eds:
            cris = list(db.scalars(select(Crianca.id).where(Crianca.edicao_id.in_(eds))).all())
            pads = list(db.scalars(select(Padrinho.id).where(Padrinho.edicao_id.in_(eds))).all())
            if cris:
                db.execute(delete(Kit).where(Kit.crianca_id.in_(cris)))
                db.execute(delete(Cartao).where(Cartao.crianca_id.in_(cris)))
                db.execute(delete(Apadrinhamento).where(Apadrinhamento.crianca_id.in_(cris)))
            if pads:
                db.execute(delete(Padrinho).where(Padrinho.id.in_(pads)))
            db.execute(delete(Compra).where(Compra.edicao_id.in_(eds)))
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
    edicao = Edicao(cidade_id=cidade.id, ano=2026, nome=f"{MARCA} Edicao", valor_cesta=120, valor_festa=60)
    db.add(edicao); db.flush()
    hoje = DiaEvento(edicao_id=edicao.id, data=date.today(), descricao="hoje")
    outro = DiaEvento(edicao_id=edicao.id, data=date.today() + timedelta(days=7), descricao="depois")
    db.add_all([hoje, outro]); db.flush()
    inst = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola A"); db.add(inst); db.flush()

    ana = Crianca(edicao_id=edicao.id, instituicao_id=inst.id, dia_evento_id=hoje.id,
                  codigo="001", nome="Ana Clara", idade=8, sexo="F")
    bruno = Crianca(edicao_id=edicao.id, instituicao_id=inst.id, dia_evento_id=outro.id,
                    codigo="002", nome="Bruno Lima", idade=10, sexo="M")
    carla = Crianca(edicao_id=edicao.id, instituicao_id=inst.id,
                    codigo="003", nome="Carla Souza", idade=7, sexo="F")
    db.add_all([ana, bruno, carla]); db.flush()

    def usuario(sufixo, perfil):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        v = UsuarioEdicao(usuario_id=u.id, edicao_id=edicao.id, perfil_id=perfis[perfil].id)
        db.add(v); db.flush()
        db.add(UsuarioInstituicao(usuario_edicao_id=v.id, instituicao_id=inst.id))
        return u

    estrutura = usuario("Estrutura", "Estrutura")
    comissario = usuario("Comissario", "Comissario")
    db.commit()

    try:
        ce = TestClient(app); entrar(ce, estrutura.email)
        ck = TestClient(app); entrar(ck, comissario.email)

        print("\nKits")
        r = ce.get("/kits")
        verifica("lista parte das criancas, nao dos kits", r.json()["total"] == 3, str(r.json()["total"]))
        verifica("crianca sem kit conta como pendente",
                 r.json()["resumo"].get("pendente") == 3, str(r.json()["resumo"]))

        r = ce.post("/kits", json={"criancas": [ana.id, bruno.id], "status": "montado"})
        verifica("monta kits em lote", r.status_code == 200 and len(r.json()) == 2, r.text[:120])

        r = ce.get("/kits")
        verifica("resumo acompanha", r.json()["resumo"] == {"montado": 2, "pendente": 1}, str(r.json()["resumo"]))

        r = ce.get("/kits", params={"situacao": "pendente"})
        verifica("filtra pendentes incluindo quem nao tem registro",
                 r.json()["total"] == 1 and r.json()["itens"][0]["crianca_id"] == carla.id,
                 str(r.json()["total"]))

        r = ce.post("/kits", json={"criancas": [ana.id], "status": "entregue"})
        verifica("marca como entregue e grava a hora", r.json()[0]["entregue_em"] is not None)

        r = ce.post("/kits", json={"criancas": [ana.id], "status": "montado"})
        verifica("voltar atras limpa a hora de entrega", r.json()[0]["entregue_em"] is None)

        r = ck.post("/kits", json={"criancas": [ana.id], "status": "entregue"})
        verifica("comissario NAO mexe em kits", r.status_code == 403, str(r.status_code))

        print("\nCompras")
        r = ce.post("/compras", json={
            "edicao_id": edicao.id, "descricao": "Cestas basicas", "categoria": "cesta",
            "quantidade": 100, "valor_total": "5000.00", "fornecedor": "Atacado X",
            "data": str(date.today()),
        })
        verifica("registra compra", r.status_code == 201, r.text[:130])
        verifica("guarda quem registrou", r.json()["responsavel"] == estrutura.nome, str(r.json()["responsavel"]))

        ce.post("/compras", json={
            "edicao_id": edicao.id, "descricao": "Brinquedos", "categoria": "presente",
            "quantidade": 100, "valor_total": "3000.00", "data": str(date.today()),
        })
        ce.post("/compras", json={
            "edicao_id": edicao.id, "descricao": "Sabonetes", "categoria": "cesta",
            "quantidade": 100, "valor_total": "500.00", "data": str(date.today()),
        })

        r = ce.get("/compras")
        verifica("soma o total gasto", r.json()["total_gasto"] == "8500.00", r.json()["total_gasto"])
        verifica("agrupa por categoria",
                 r.json()["por_categoria"] == {"cesta": "5500.00", "presente": "3000.00"},
                 str(r.json()["por_categoria"]))

        r = ck.get("/compras")
        verifica("comissario NAO ve compras", r.status_code == 403, str(r.status_code))

        print("\nCheck-in")
        r = ck.post("/checkin", json={"codigo": "001", "edicao_id": edicao.id})
        verifica("comissario faz check-in", r.status_code == 200, r.text[:130])
        entrada = r.json() if r.status_code == 200 else {}

        if entrada:
            verifica("identifica a crianca", entrada["nome"] == "Ana Clara")
            verifica("nao e repetido na primeira vez", entrada["ja_tinha_checkin"] is False)
            verifica("avisa que nao tem padrinho",
                     any("padrinho" in a for a in entrada["avisos"]), str(entrada["avisos"]))
            verifica("avisa sobre os cartoes que faltam",
                     any("cartoes" in a for a in entrada["avisos"]), str(entrada["avisos"]))
            verifica("nao avisa do dia, porque e hoje",
                     not any("dia dela" in a for a in entrada["avisos"]), str(entrada["avisos"]))

        r = ck.post("/checkin", json={"codigo": "001", "edicao_id": edicao.id})
        verifica("check-in repetido avisa, mas nao recusa",
                 r.status_code == 200 and r.json()["ja_tinha_checkin"] is True, str(r.status_code))

        r = ck.post("/checkin", json={"codigo": "002", "edicao_id": edicao.id})
        verifica("avisa quando o dia da crianca nao e hoje",
                 any("nao hoje" in a for a in r.json()["avisos"]), str(r.json()["avisos"]))

        r = ck.post("/checkin", json={"codigo": "003", "edicao_id": edicao.id})
        verifica("avisa quando a crianca nao esta marcada em nenhum dia",
                 any("nenhum dia" in a for a in r.json()["avisos"]), str(r.json()["avisos"]))

        r = ck.post("/checkin", json={"codigo": "999", "edicao_id": edicao.id})
        verifica("codigo inexistente devolve 404", r.status_code == 404, str(r.status_code))

        db.expire_all()
        verifica("o check-in ficou gravado na crianca", db.get(Crianca, ana.id).checkin_em is not None)

        print("\nQR code do cracha")
        r = ck.get(f"/checkin/qrcode/{ana.id}")
        verifica("gera o QR code", r.status_code == 200 and r.headers["content-type"] == "image/png",
                 str(r.status_code))
        verifica("o PNG tem conteudo", len(r.content) > 200, str(len(r.content)))

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
