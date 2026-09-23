"""Auditoria de seguranca: tenta atacar o sistema de verdade.

Nao confere se o codigo "parece" seguro — tenta vazar dados de outra cidade,
forjar sessao, subir arquivo malicioso, escapar da pasta de arquivos, injetar
SQL, virar administrador. Cada verificacao abaixo e um ataque que FALHOU.

Rodar com:  python -m tests.test_seguranca
"""

import json
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    Apadrinhamento,
    Cartao,
    Cidade,
    Crianca,
    Edicao,
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

MARCA = "ZZ_SEG"
SENHA = "senha-de-teste-123"

ok = 0
falhas: list[str] = []


def bloqueado(d: str, c: bool, extra: str = "") -> None:
    """c=True significa que o ataque foi barrado."""
    global ok
    if c:
        ok += 1
        print(f"  barrado  {d}")
    else:
        falhas.append(d)
        print(f"  VAZOU    {d} {extra}")


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
                db.execute(delete(Cartao).where(Cartao.crianca_id.in_(cris)))
                db.execute(delete(Apadrinhamento).where(Apadrinhamento.crianca_id.in_(cris)))
            if pads:
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


def entrar(cliente: TestClient, email: str, senha: str = SENHA):
    r = cliente.post("/auth/login", json={"email": email, "senha": senha})
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

    # Duas cidades independentes. O atacante e da A e tenta alcancar a B.
    ca = Cidade(nome=f"{MARCA} CidadeA", uf="CE")
    cb = Cidade(nome=f"{MARCA} CidadeB", uf="SP")
    db.add_all([ca, cb]); db.flush()
    ea = Edicao(cidade_id=ca.id, ano=2026, nome=f"{MARCA} A 2026", valor_cesta=120, valor_festa=60)
    eb = Edicao(cidade_id=cb.id, ano=2026, nome=f"{MARCA} B 2026", valor_cesta=120, valor_festa=60)
    db.add_all([ea, eb]); db.flush()
    ia = Instituicao(cidade_id=ca.id, nome=f"{MARCA} EscolaA")
    ia2 = Instituicao(cidade_id=ca.id, nome=f"{MARCA} EscolaA2")
    ib = Instituicao(cidade_id=cb.id, nome=f"{MARCA} EscolaB")
    db.add_all([ia, ia2, ib]); db.flush()

    minha = Crianca(edicao_id=ea.id, instituicao_id=ia.id, codigo="001",
                    nome="Crianca Minha Instituicao", idade=8, sexo="F")
    vizinha = Crianca(edicao_id=ea.id, instituicao_id=ia2.id, codigo="002",
                      nome="Crianca Outra Instituicao", idade=9, sexo="M")
    secreta = Crianca(edicao_id=eb.id, instituicao_id=ib.id, codigo="003",
                      nome="Crianca Segredo Outra Cidade", idade=7, sexo="F")
    db.add_all([minha, vizinha, secreta]); db.flush()

    padrinho_b = Padrinho(edicao_id=eb.id, nome=f"{MARCA} Padrinho Secreto B")
    db.add(padrinho_b); db.flush()
    cartao_b = Cartao(crianca_id=secreta.id, tipo="cesta", arquivo="cartoes/B/2026/SEGREDO.jpg")
    db.add(cartao_b); db.flush()

    def usuario(sufixo, perfil, edicao, instituicoes=(), admin=False):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA), admin_geral=admin)
        db.add(u); db.flush()
        if edicao:
            v = UsuarioEdicao(usuario_id=u.id, edicao_id=edicao, perfil_id=perfis[perfil].id)
            db.add(v); db.flush()
            for i in instituicoes:
                db.add(UsuarioInstituicao(usuario_edicao_id=v.id, instituicao_id=i))
        return u

    # O atacante: comissario da cidade A, responsavel por UMA instituicao.
    atacante = usuario("Atacante", "Comissario", ea.id, [ia.id])
    coord_b = usuario("CoordB", "Coordenacao", eb.id)
    db.commit()

    try:
        c = TestClient(app); entrar(c, atacante.email)

        print("\n1. Alcancar dados de outra cidade pelo ID (IDOR)")
        r = c.get(f"/criancas/{secreta.id}")
        bloqueado("ler crianca de outra cidade pelo id", r.status_code == 404, str(r.status_code))

        r = c.get(f"/padrinhos/{padrinho_b.id}")
        bloqueado("ler padrinho de outra cidade pelo id", r.status_code == 404, str(r.status_code))

        r = c.get(f"/cartoes/{cartao_b.id}/imagem")
        bloqueado("baixar cartao de outra cidade", r.status_code == 404, str(r.status_code))

        r = c.get(f"/painel/{eb.id}")
        bloqueado("ver o painel de outra cidade", r.status_code in (403, 404), str(r.status_code))

        r = c.patch(f"/criancas/{secreta.id}", json={"nome": "Alterado pelo atacante"})
        bloqueado("editar crianca de outra cidade", r.status_code in (403, 404), str(r.status_code))

        r = c.delete(f"/criancas/{secreta.id}")
        bloqueado("apagar crianca de outra cidade", r.status_code in (403, 404), str(r.status_code))

        print("\n2. Alcancar instituicao vizinha, da MESMA cidade")
        r = c.get(f"/criancas/{vizinha.id}")
        bloqueado("ler crianca de instituicao que nao e sua", r.status_code == 404, str(r.status_code))

        r = c.get("/criancas")
        nomes = [x["nome"] for x in r.json()["itens"]]
        bloqueado("listagem so traz a instituicao dele",
                  nomes == ["Crianca Minha Instituicao"], str(nomes))

        r = c.get("/criancas", params={"instituicao_id": ia2.id})
        bloqueado("forcar instituicao_id de outra instituicao nao vaza",
                  r.json()["total"] == 0, str(r.json()["total"]))

        r = c.get("/criancas", params={"edicao_id": eb.id})
        bloqueado("forcar edicao_id de outra cidade nao vaza",
                  r.json()["total"] == 0, str(r.json()["total"]))

        print("\n3. Virar administrador (mass assignment)")
        r = c.patch(f"/criancas/{minha.id}", json={"nome": "Ok", "edicao_id": eb.id})
        depois = db.get(Crianca, minha.id)
        db.refresh(depois)
        bloqueado("mudar a edicao da crianca por campo extra",
                  depois.edicao_id == ea.id, str(depois.edicao_id))

        r = c.post("/padrinhos", json={"edicao_id": ea.id, "nome": "X Padrinho",
                                       "criado_por": 1, "id": 99999})
        if r.status_code == 201:
            bloqueado("forcar id do padrinho por campo extra", r.json()["id"] != 99999, str(r.json()["id"]))
        else:
            bloqueado("forcar id do padrinho por campo extra", True)

        print("\n4. Forjar ou adulterar a sessao")
        token_falso = jwt.encode(
            {"sub": str(coord_b.id), "csrf": "x",
             "exp": datetime.now(UTC) + timedelta(hours=8)},
            "segredo-errado", algorithm="HS256",
        )
        c2 = TestClient(app)
        c2.cookies.set(config.cookie_nome, token_falso)
        r = c2.get("/auth/eu")
        bloqueado("token assinado com outro segredo", r.status_code == 401, str(r.status_code))

        # Algoritmo "none": classico de biblioteca JWT mal configurada.
        sem_assinatura = jwt.encode(
            {"sub": str(coord_b.id), "csrf": "x",
             "exp": datetime.now(UTC) + timedelta(hours=8)},
            key="", algorithm="none",
        )
        c3 = TestClient(app)
        c3.cookies.set(config.cookie_nome, sem_assinatura)
        r = c3.get("/auth/eu")
        bloqueado("token com algoritmo 'none'", r.status_code == 401, str(r.status_code))

        # Token valido, mas ja expirado.
        expirado = jwt.encode(
            {"sub": str(coord_b.id), "csrf": "x",
             "exp": datetime.now(UTC) - timedelta(hours=1)},
            config.jwt_secret, algorithm=config.jwt_algoritmo,
        )
        c4 = TestClient(app)
        c4.cookies.set(config.cookie_nome, expirado)
        r = c4.get("/auth/eu")
        bloqueado("token expirado", r.status_code == 401, str(r.status_code))

        print("\n5. CSRF")
        c5 = TestClient(app); entrar(c5, atacante.email)
        del c5.headers["X-CSRF-Token"]
        r = c5.post("/padrinhos", json={"edicao_id": ea.id, "nome": "Sem CSRF"})
        bloqueado("POST sem cabecalho CSRF", r.status_code == 403, str(r.status_code))

        # O atacante conhece o cookie legivel de OUTRA sessao? Nao adianta:
        # o valor tem de bater com o que esta DENTRO do token da sessao atual.
        c6 = TestClient(app); entrar(c6, atacante.email)
        c6.headers["X-CSRF-Token"] = "valor-de-outra-sessao"
        r = c6.post("/padrinhos", json={"edicao_id": ea.id, "nome": "CSRF errado"})
        bloqueado("POST com CSRF de outra sessao", r.status_code == 403, str(r.status_code))

        print("\n6. Injecao de SQL")
        for carga in ["' OR '1'='1", "'; DROP TABLE criancas; --", "%' UNION SELECT * FROM usuarios --"]:
            r = c.get("/criancas", params={"busca": carga})
            vazou = r.status_code != 200 or r.json()["total"] > 1
            bloqueado(f"busca com {carga[:24]!r}", not vazou, str(r.status_code))
        # As tabelas continuam de pe?
        bloqueado("a tabela criancas continua existindo",
                  db.scalar(select(func.count()).select_from(Crianca)) >= 3)

        print("\n7. Escapar da pasta de arquivos (path traversal)")
        from app.servicos.arquivos import dentro_da_pasta
        for caminho in ["../../etc/passwd", "/etc/passwd", "cartoes/../../../.env",
                        "../" * 12 + "etc/passwd"]:
            try:
                dentro_da_pasta(caminho)
                escapou = True
            except ValueError:
                escapou = False
            bloqueado(f"caminho {caminho[:28]!r}", not escapou)

        # %2F NAO e barra: e um nome de arquivo estranho, e fica dentro da
        # pasta. Numa URL o FastAPI ja decodifica antes de chegar aqui, e ai
        # cai no caso acima. O que importa e que o resultado nao escape.
        resolvido = dentro_da_pasta("..%2F..%2Fetc%2Fpasswd")
        bloqueado("caminho com %2F nao escapa da pasta",
                  resolvido.is_relative_to(config.caminho_arquivos.resolve()))

        # E pela rota? Um cartao com caminho malicioso gravado na base.
        malicioso = Cartao(crianca_id=minha.id, tipo="festa", arquivo="../../../../etc/passwd")
        db.add(malicioso); db.commit()
        r = c.get(f"/cartoes/{malicioso.id}/imagem")
        bloqueado("rota de imagem com caminho malicioso na base",
                  r.status_code == 404, str(r.status_code))

        print("\n8. Identificador de importacao/cartao forjado")
        # Aqui e preciso um usuario que TENHA a permissao: se o 403 vier antes,
        # o teste nao chega a exercitar a validacao do identificador.
        monitor = usuario("Monitor", "Monitor", ea.id, [ia.id])
        coord_a = usuario("CoordA", "Coordenacao", ea.id)
        db.commit()

        cmon = TestClient(app); entrar(cmon, monitor.email)
        r = cmon.post("/cartoes/confirmar", json={"id": "../../../etc/passwd",
                                                  "crianca_id": minha.id, "tipo": "cesta"})
        bloqueado("id de analise com travessia (com permissao de subir)",
                  r.status_code == 400, str(r.status_code))

        r = cmon.post("/cartoes/confirmar", json={"id": "..%2F..%2Fetc%2Fpasswd",
                                                  "crianca_id": minha.id, "tipo": "cesta"})
        bloqueado("id de analise com %2F", r.status_code == 400, str(r.status_code))

        ccoord = TestClient(app); entrar(ccoord, coord_a.email)
        r = ccoord.post("/criancas/importar/..%2F..%2Fetc%2Fpasswd/confirmar")
        bloqueado("id de importacao com travessia (com permissao de importar)",
                  r.status_code in (400, 404), str(r.status_code))

        print("\n9. Arquivo gigante (negacao de servico)")
        # 20 MB, acima do teto de 15. Sem limite, a aplicacao carregaria tudo
        # na memoria — e alguns pedidos simultaneos derrubariam o servidor.
        gigante = b"\xff\xd8\xff\xe0" + b"\x00" * (20 * 1024 * 1024)
        r = cmon.post(
            "/cartoes/analisar",
            files={"imagem": ("gigante.jpg", gigante, "image/jpeg")},
            data={"codigo": "001", "edicao_id": str(ea.id)},
        )
        bloqueado("foto de 20 MB e recusada", r.status_code == 413, str(r.status_code))

        r = ccoord.post(
            "/criancas/importar",
            files={"arquivo": ("gigante.xlsx", gigante, "application/vnd.ms-excel")},
            data={"edicao_id": str(ea.id)},
        )
        bloqueado("planilha de 20 MB e recusada", r.status_code == 413, str(r.status_code))

        r = cmon.post(
            "/cartoes/analisar",
            files={"imagem": ("vazio.jpg", b"", "image/jpeg")},
            data={"codigo": "001", "edicao_id": str(ea.id)},
        )
        bloqueado("arquivo vazio e recusado", r.status_code == 400, str(r.status_code))

        # Executavel com nome de foto: o OpenCV nao consegue abrir e recusa.
        r = cmon.post(
            "/cartoes/analisar",
            files={"imagem": ("virus.jpg", b"MZ\x90\x00" + b"executavel" * 100, "image/jpeg")},
            data={"codigo": "001", "edicao_id": str(ea.id)},
        )
        bloqueado("arquivo que nao e imagem e recusado", r.status_code == 400, str(r.status_code))

        print("\n10. Enumeracao de usuarios")
        c7 = TestClient(app)
        r1 = c7.post("/auth/login", json={"email": "nao-existe@exemplo.org", "senha": "x"})
        r2 = c7.post("/auth/login", json={"email": atacante.email, "senha": "senha-errada"})
        bloqueado("login nao revela se o email existe",
                  r1.json()["detail"] == r2.json()["detail"] and r1.status_code == r2.status_code)

        e1 = c7.post("/auth/esqueci-senha", json={"email": "nao-existe@exemplo.org"}).json()
        e2 = c7.post("/auth/esqueci-senha", json={"email": atacante.email}).json()
        bloqueado("esqueci-senha nao revela quem tem conta",
                  e1["mensagem"] == e2["mensagem"])

        print("\n11. Escalar privilegio pela rota de usuarios")
        r = c.get("/usuarios")
        bloqueado("comissario nao lista usuarios", r.status_code == 403, str(r.status_code))

        r = c.post("/usuarios", json={
            "dados": {"nome": f"{MARCA} Novo", "email": f"{MARCA.lower()}.novo@exemplo.org"},
            "vinculo": {"edicao_id": ea.id, "perfil_id": perfis["Coordenacao"].id, "instituicoes": []},
        })
        bloqueado("comissario nao cria coordenador", r.status_code == 403, str(r.status_code))

        r = c.post("/cidades", json={"nome": f"{MARCA} Invadida", "uf": "RJ"})
        bloqueado("comissario nao cria cidade", r.status_code == 403, str(r.status_code))

        print("\n12. Conta desativada continua entrando?")
        atacante_db = db.get(Usuario, atacante.id)
        atacante_db.ativo = False
        db.commit()
        r = c.get("/auth/eu")
        bloqueado("sessao de conta desativada para de valer", r.status_code == 401, str(r.status_code))
        atacante_db.ativo = True
        db.commit()

        print("\n13. Senha e segredo nunca aparecem na resposta")
        c8 = TestClient(app)
        r = entrar(c8, atacante.email)
        corpo = r.text.lower()
        bloqueado("resposta do login nao traz hash de senha",
                  "argon2" not in corpo and "senha_hash" not in corpo)
        bloqueado("resposta do login nao traz o segredo do jwt",
                  config.jwt_secret.lower() not in corpo)

    finally:
        limpar(db, log_inicial)
        db.close()

    print(f"\n{ok} ataque(s) barrado(s), {len(falhas)} vazamento(s)")
    if falhas:
        for f in falhas:
            print("  !!!", f)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
