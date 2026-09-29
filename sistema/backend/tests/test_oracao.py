"""Testa o convite de oracao do dia.

Tres promessas, e o teste existe por causa delas:

  1. o nome nao vaza. O convite passa pelo mesmo filtro das telas — o
     comissario so pode receber crianca que ja e dele;
  2. a crianca nao troca no meio do dia. Chamar duas vezes devolve a mesma;
  3. a lista gira. Em dias seguidos, nomes diferentes, ate a lista acabar —
     e nao um sorteio que repete um nome e esquece outro por semanas.

Rodar com:  python -m tests.test_oracao
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
from app.seguranca.contexto import montar_contexto
from app.seguranca.senhas import gerar_hash
from app.servicos import oracao

MARCA = "ZZ_ORA"
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

    # 5 criancas na A, 1 na B — 6 na edicao. O numero importa: a rotacao e
    # conferida andando 7 dias e exigindo 6 nomes distintos e a volta ao
    # primeiro no setimo.
    criancas = [
        Crianca(edicao_id=edicao.id, instituicao_id=inst.id, dia_evento_id=dia.id,
                codigo=f"A{i}", nome=f"Crianca A{i} Sobrenome", idade=8, sexo="F")
        for i in range(1, 6)
    ]
    crianca_b = Crianca(edicao_id=edicao.id, instituicao_id=inst_b.id, dia_evento_id=dia.id,
                        codigo="B1", nome="Crianca B1 Sobrenome", idade=9, sexo="M")
    db.add_all([*criancas, crianca_b]); db.flush()

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
    # Duas das cinco criancas da Escola A sao dele; as outras tres e a da B nao.
    com = usuario("Com", "Comissario", [inst.id])
    com_vazio = usuario("ComVazio", "Comissario", [inst.id])

    criancas[0].comissario_id = com.id
    criancas[1].comissario_id = com.id
    db.commit()

    dele = {criancas[0].nome, criancas[1].nome}

    try:
        print("\nO convite chega")
        cc = TestClient(app); entrar(cc, coord.email)
        r = cc.get(f"/oracao/{edicao.id}")
        verifica("a coordenacao recebe um convite", r.status_code == 200, r.text[:130])
        convite = r.json() if r.status_code == 200 else {}
        verifica("com o nome de uma crianca", bool(convite.get("crianca")), str(convite))
        verifica("e com a instituicao dela", bool(convite.get("instituicao")), str(convite))

        print("\nA crianca nao troca no meio do dia")
        segunda = cc.get(f"/oracao/{edicao.id}").json()
        verifica("chamar de novo devolve a mesma crianca",
                 segunda.get("crianca") == convite.get("crianca"),
                 f"{convite.get('crianca')} -> {segunda.get('crianca')}")

        print("\nAlcance: o comissario so recebe crianca que ja e dele")
        ck = TestClient(app); entrar(ck, com.email)
        do_com = ck.get(f"/oracao/{edicao.id}").json()
        verifica("o comissario recebe uma das duas criancas dele",
                 do_com.get("crianca") in dele, str(do_com))

        cv = TestClient(app); entrar(cv, com_vazio.email)
        r = cv.get(f"/oracao/{edicao.id}")
        verifica("comissario sem crianca atribuida recebe 200, nao 403",
                 r.status_code == 200, str(r.status_code))
        verifica("e o convite vem vazio", r.json().get("crianca") is None, r.text[:130])

        print("\nA lista gira: 6 criancas, 6 dias, 6 nomes — e no 7o volta ao primeiro")
        ctx = montar_contexto(db, coord)
        hoje_de_verdade = oracao.dia_de_hoje
        try:
            nomes = []
            base = hoje_de_verdade()
            for passo in range(7):
                oracao.dia_de_hoje = lambda p=passo: base + p
                escolhida = oracao.crianca_do_dia(db, ctx, edicao.id)
                nomes.append(escolhida.nome if escolhida else None)
        finally:
            oracao.dia_de_hoje = hoje_de_verdade

        verifica("os 6 nomes da edicao saem sem repetir", len(set(nomes[:6])) == 6, str(nomes))
        verifica("no 7o dia a lista recomeca do primeiro nome", nomes[6] == nomes[0], str(nomes))

        print("\nQuem desistiu fica de fora")
        criancas[1].desistiu_em = func.now()
        db.commit()
        # Sobra so a primeira crianca do comissario: qualquer dia cai nela.
        ck2 = TestClient(app); entrar(ck2, com.email)
        so_uma = ck2.get(f"/oracao/{edicao.id}").json()
        verifica("o convite nao cai em quem desistiu",
                 so_uma.get("crianca") == criancas[0].nome, str(so_uma))

        print("\nEdicao fora do alcance")
        outra = Edicao(cidade_id=cidade.id, ano=2027, nome=f"{MARCA} Outra",
                       valor_cesta=1, valor_festa=1)
        db.add(outra); db.commit()
        r = ck2.get(f"/oracao/{outra.id}")
        verifica("edicao sem vinculo devolve convite vazio, nao erro",
                 r.status_code == 200 and r.json().get("crianca") is None,
                 f"{r.status_code} {r.text[:100]}")

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
