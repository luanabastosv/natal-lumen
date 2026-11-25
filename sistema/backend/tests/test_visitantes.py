"""Testa os visitantes do evento: o QR Code da pulseira, o cadastro e a planilha.

  1. a pagina publica do QR abre sem sessao e grava o visitante; o mesmo
     celular na mesma edicao nao duplica; dado ruim e recusado;
  2. o link das fotos so sai depois do cadastro, e nulo enquanto a galeria
     nao estiver pronta;
  3. a planilha, o QR Code e o link sao so da coordenacao geral: o monitor e
     quem nao esta logado levam 403/401; a coordenacao de outra edicao, 403;
  4. um QR Code por edicao (os dois dias): o de 2027 nao abre 2026.

Rodar com:  python -m tests.test_visitantes
"""

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    Cidade,
    Edicao,
    Instituicao,
    LogAtividade,
    Perfil,
    TokenAcesso,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
    Visitante,
)
from app.seguranca.senhas import gerar_hash

MARCA = "ZZ_VIS"
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
            db.execute(delete(Visitante).where(Visitante.edicao_id.in_(eds)))
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

    cidade = Cidade(nome=f"{MARCA} Cidade", uf="CE"); db.add(cidade); db.flush()
    edicao = Edicao(cidade_id=cidade.id, ano=2026, nome=f"{MARCA} Natal Lumen 2026",
                    valor_cesta=120, valor_festa=60); db.add(edicao); db.flush()
    outra = Edicao(cidade_id=cidade.id, ano=2027, nome=f"{MARCA} Natal Lumen 2027",
                   valor_cesta=120, valor_festa=60); db.add(outra); db.flush()
    inst = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola"); db.add(inst); db.flush()

    def usuario(sufixo, perfil, ed, instituicoes=()):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        v = UsuarioEdicao(usuario_id=u.id, edicao_id=ed.id, perfil_id=perfis[perfil].id)
        db.add(v); db.flush()
        for i in instituicoes:
            db.add(UsuarioInstituicao(usuario_edicao_id=v.id, instituicao_id=i))
        return u

    coord = usuario("Coord", "Coordenacao", edicao)
    coord27 = usuario("Coord27", "Coordenacao", outra)
    monitor = usuario("Monitor", "Monitoria - monitores", edicao, [inst.id])
    db.commit()

    try:
        cc = TestClient(app); entrar(cc, coord.email)
        c27 = TestClient(app); entrar(c27, coord27.email)
        cm = TestClient(app); entrar(cm, monitor.email)
        anon = TestClient(app)

        print("\nO painel cria o codigo do QR Code")
        r = cc.get("/visitantes", params={"edicao_id": edicao.id})
        verifica("a coordenacao abre a tela", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        cod = r.json().get("codigo_fotos", "") if r.status_code == 200 else ""
        verifica("um codigo so para a edicao, pelo ano", cod.startswith("nl26"), cod)
        verifica("o endereco do QR leva a pagina /acesso/f/",
                 r.json().get("endereco_qr", "").endswith(f"/acesso/f/{cod}"), r.text[:200])
        r = cc.get("/visitantes", params={"edicao_id": edicao.id})
        verifica("abrir de novo nao troca o codigo (pode estar impresso)",
                 r.json()["codigo_fotos"] == cod)

        print("\nA pagina publica")
        r = anon.get(f"/visitantes/publico/{cod}")
        verifica("abre sem sessao", r.status_code == 200, r.text[:200])
        verifica("e nao entrega o link das fotos antes do cadastro", "link" not in r.text, r.text[:200])
        r = anon.get("/visitantes/publico/nao-existe")
        verifica("codigo que nao existe: 404", r.status_code == 404, str(r.status_code))

        r = anon.post(f"/visitantes/publico/{cod}", json={"nome": "  Luana   Bastos ", "celular": "(85) 98888-7777"})
        verifica("o cadastro grava", r.status_code == 200, r.text[:200])
        verifica("e, sem galeria ainda, o link vem nulo", r.json().get("link_fotos") is None, r.text)
        v = db.scalar(select(Visitante).where(Visitante.edicao_id == edicao.id))
        verifica("nome limpo e celular so com digitos",
                 v is not None and v.nome == "Luana Bastos" and v.celular == "85988887777",
                 f"{v and v.nome!r} {v and v.celular!r}")

        r = anon.post(f"/visitantes/publico/{cod}", json={"nome": "Luana B.", "celular": "85 9 8888 7777"})
        db.expire_all()
        n = db.scalar(select(func.count()).where(Visitante.edicao_id == edicao.id))
        v = db.scalar(select(Visitante).where(Visitante.edicao_id == edicao.id))
        verifica("o mesmo celular nao duplica, so atualiza o nome",
                 r.status_code == 200 and n == 1 and v.nome == "Luana B.", f"{n} {v.nome}")

        for desc, corpo in [
            ("celular sem DDD", {"nome": "Fulano", "celular": "98888777"}),
            ("celular com digitos demais", {"nome": "Fulano", "celular": "859888877771"}),
            ("nome vazio", {"nome": "   ", "celular": "85988887777"}),
            ("nome gigante", {"nome": "x" * 300, "celular": "85988887777"}),
        ]:
            r = anon.post(f"/visitantes/publico/{cod}", json=corpo)
            verifica(f"{desc}: 422", r.status_code == 422, str(r.status_code))

        r = anon.post(f"/visitantes/publico/{cod}",
                      json={"nome": "Robert'); DROP TABLE visitantes;--", "celular": "85911112222"})
        n = db.scalar(select(func.count()).where(Visitante.edicao_id == edicao.id))
        verifica("texto malicioso no nome e so texto", r.status_code == 200 and n == 2, str(n))

        print("\nO link das fotos")
        r = cc.put("/visitantes/link", params={"edicao_id": edicao.id}, json={"link_fotos": "http://fotos.exemplo.com"})
        verifica("link sem https e recusado", r.status_code == 422, str(r.status_code))
        r = cc.put("/visitantes/link", params={"edicao_id": edicao.id}, json={"link_fotos": "https://fotos.exemplo.com/2026"})
        verifica("a coordenacao salva o link", r.status_code == 200 and r.json()["link_fotos"].endswith("/2026"),
                 r.text[:200])
        r = anon.post(f"/visitantes/publico/{cod}", json={"nome": "Maria Lima", "celular": "85933334444"})
        verifica("agora o cadastro devolve o link",
                 r.json().get("link_fotos") == "https://fotos.exemplo.com/2026", r.text)

        print("\nSo a coordenacao geral")
        r = cc.get("/visitantes", params={"edicao_id": edicao.id})
        lista = r.json()["visitantes"]
        verifica("a planilha da tela traz os cadastros, com celular formatado",
                 len(lista) == 3 and any(x["celular"] == "(85) 98888-7777" for x in lista), str(lista[:2]))
        r = cm.get("/visitantes", params={"edicao_id": edicao.id})
        verifica("o monitor leva 403", r.status_code == 403, str(r.status_code))
        r = anon.get("/visitantes", params={"edicao_id": edicao.id})
        verifica("sem sessao: 401", r.status_code == 401, str(r.status_code))
        r = c27.get("/visitantes", params={"edicao_id": edicao.id})
        verifica("a coordenacao de outra edicao leva 403", r.status_code == 403, str(r.status_code))
        r = c27.put("/visitantes/link", params={"edicao_id": edicao.id}, json={"link_fotos": "https://golpe.exemplo.com"})
        verifica("e nao troca o link de 2026", r.status_code == 403, str(r.status_code))
        r = cm.get("/visitantes/qrcode", params={"edicao_id": edicao.id})
        verifica("o monitor nao baixa o QR", r.status_code == 403, str(r.status_code))
        r = cm.get("/visitantes/planilha", params={"edicao_id": edicao.id})
        verifica("nem a planilha", r.status_code == 403, str(r.status_code))
        anon2 = TestClient(app)
        r = anon2.put("/visitantes/link", params={"edicao_id": edicao.id}, json={"link_fotos": "https://golpe.exemplo.com"})
        verifica("sem sessao nao troca o link", r.status_code in (401, 403), str(r.status_code))

        print("\nArquivos")
        r = cc.get("/visitantes/qrcode", params={"edicao_id": edicao.id})
        verifica("QR Code em PNG", r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n",
                 str(r.status_code))
        r = cc.get("/visitantes/qrcode", params={"edicao_id": edicao.id, "formato": "svg"})
        verifica("QR Code em SVG para a grafica", r.status_code == 200 and b"<svg" in r.content[:300],
                 r.text[:120])
        r = cc.get("/visitantes/planilha", params={"edicao_id": edicao.id})
        verifica("planilha .xlsx", r.status_code == 200 and r.content[:2] == b"PK", str(r.status_code))

        print("\nCada edicao com o seu QR Code")
        r = c27.get("/visitantes", params={"edicao_id": outra.id})
        c27_cod = r.json()["codigo_fotos"] if r.status_code == 200 else ""
        verifica("2027 ganha codigo proprio", c27_cod.startswith("nl27") and c27_cod != cod, c27_cod)
        r = anon.post(f"/visitantes/publico/{c27_cod}", json={"nome": "Ze", "celular": "85988887777"})
        n26 = db.scalar(select(func.count()).where(Visitante.edicao_id == edicao.id))
        n27 = db.scalar(select(func.count()).where(Visitante.edicao_id == outra.id))
        verifica("e o cadastro cai na edicao certa (o mesmo celular conta nas duas)",
                 n26 == 3 and n27 == 1, f"{n26} {n27}")
        r = c27.get("/visitantes", params={"edicao_id": outra.id})
        verifica("a planilha de 2027 nao mostra os de 2026", len(r.json()["visitantes"]) == 1)
    finally:
        limpar(db, log_inicial)
        db.close()

    print(f"\n{ok} verificacoes ok, {len(falhas)} falha(s)")
    if falhas:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
