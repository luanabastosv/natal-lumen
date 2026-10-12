"""Testa o painel da coordenacao da monitoria e a divisao em nucleos.

Rodar com:  python -m tests.test_monitoria
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    Apadrinhamento,
    Autorizacao,
    Cartao,
    Cidade,
    Compra,
    Crianca,
    DiaEvento,
    Edicao,
    Grupo,
    Instituicao,
    InstituicaoDia,
    Kit,
    LogAtividade,
    Padrinho,
    Pagamento,
    Perfil,
    TokenAcesso,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.seguranca.senhas import gerar_hash

MARCA = "ZZ_MON"
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
            cris = list(db.scalars(select(Crianca.id).where(Crianca.edicao_id.in_(eds))).all())
            pads = list(db.scalars(select(Padrinho.id).where(Padrinho.edicao_id.in_(eds))).all())
            if cris:
                db.execute(delete(Kit).where(Kit.crianca_id.in_(cris)))
                db.execute(delete(Cartao).where(Cartao.crianca_id.in_(cris)))
                db.execute(delete(Apadrinhamento).where(Apadrinhamento.crianca_id.in_(cris)))
            if pads:
                db.execute(delete(Pagamento).where(Pagamento.padrinho_id.in_(pads)))
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


def main() -> None:
    db = SessionLocal()
    log_inicial = db.scalar(select(func.max(LogAtividade.id))) or 0
    limpar(db)

    perfis = {p.nome: p for p in db.scalars(select(Perfil)).all()}

    cidade = Cidade(nome=f"{MARCA} Cidade", uf="CE"); db.add(cidade); db.flush()
    edicao = Edicao(cidade_id=cidade.id, ano=2026, nome=f"{MARCA} Edicao",
                    valor_cesta=120, valor_festa=60); db.add(edicao); db.flush()
    sab = DiaEvento(edicao_id=edicao.id, data=date(2026, 12, 20), descricao="Sabado")
    dom = DiaEvento(edicao_id=edicao.id, data=date(2026, 12, 21), descricao="Domingo")
    db.add_all([sab, dom]); db.flush()

    a = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola A", sigla="EA")
    b = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola B", sigla="EB")
    sem = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Sem Dia", sigla="SD")
    db.add_all([a, b, sem]); db.flush()
    db.add_all([
        InstituicaoDia(edicao_id=edicao.id, instituicao_id=a.id, dia_evento_id=sab.id),
        InstituicaoDia(edicao_id=edicao.id, instituicao_id=b.id, dia_evento_id=dom.id),
    ])

    ca = [Crianca(edicao_id=edicao.id, instituicao_id=a.id, dia_evento_id=sab.id,
                  codigo=f"EA{i}", nome=f"Crianca A{i}", idade=8, sexo="F") for i in range(3)]
    cb = [Crianca(edicao_id=edicao.id, instituicao_id=b.id, dia_evento_id=dom.id,
                  codigo=f"EB{i}", nome=f"Crianca B{i}", idade=9, sexo="M") for i in range(2)]
    cs = Crianca(edicao_id=edicao.id, instituicao_id=sem.id, codigo="SD0", nome="Crianca S", idade=7, sexo="F")
    db.add_all(ca + cb + [cs]); db.flush()
    # A ultima da A desistiu: sai de todas as contas.
    ca[2].desistiu_em = func.now()

    db.add_all([
        Cartao(crianca_id=ca[0].id, tipo="cesta", arquivo="x.jpg"),
        Cartao(crianca_id=ca[0].id, tipo="festa", arquivo="y.jpg"),
        Cartao(crianca_id=ca[1].id, tipo="cesta", arquivo="z.jpg"),
        Cartao(crianca_id=ca[2].id, tipo="cesta", arquivo="w.jpg"),  # da desistente
        Autorizacao(crianca_id=ca[0].id, arquivo="a.jpg", necessidade_especial=True,
                    necessidade_especial_qual="Cadeira de rodas", restricao_alimentar=False,
                    tem_observacao=False),
        Autorizacao(crianca_id=cb[0].id, arquivo="b.jpg", necessidade_especial=False,
                    restricao_alimentar=True, restricao_alimentar_qual="Lactose",
                    tem_observacao=False),
    ])

    def usuario(sufixo, perfil, instituicoes=()):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        v = UsuarioEdicao(usuario_id=u.id, edicao_id=edicao.id, perfil_id=perfis[perfil].id)
        db.add(v); db.flush()
        for i in instituicoes:
            db.add(UsuarioInstituicao(usuario_edicao_id=v.id, instituicao_id=i))
        return u

    coord_mon = usuario("CoordMon", "Monitoria - coordenacao")
    monitor = usuario("Monitor", "Monitoria - monitores", [a.id])
    coord = usuario("Coord", "Coordenacao")
    db.commit()

    try:
        cm = TestClient(app); entrar(cm, coord_mon.email)

        print("\nPainel da monitoria")
        r = cm.get(f"/monitoria/{edicao.id}/painel")
        verifica("a coordenacao da monitoria abre o painel", r.status_code == 200, r.text[:160])
        p = r.json() if r.status_code == 200 else {}
        verifica("conta so quem vai (sem a desistente)", p.get("criancas") == 5, str(p.get("criancas")))
        verifica("cartoes de cesta sem o da desistente", p.get("cartoes_cesta") == 2, str(p.get("cartoes_cesta")))
        verifica("cartoes de festa", p.get("cartoes_festa") == 1, str(p.get("cartoes_festa")))
        verifica("autorizacoes", p.get("autorizacoes") == 2, str(p.get("autorizacoes")))
        verifica("uma necessidade especial e uma restricao",
                 p.get("necessidade_especial") == 1 and p.get("restricao_alimentar") == 1, str(p))
        inst = {i["sigla"]: i for i in p.get("por_instituicao", [])}
        verifica("a Escola A tem 2 que vao e 2 cartoes de cesta",
                 inst.get("EA", {}).get("criancas") == 2 and inst["EA"]["cartoes_cesta"] == 2, str(inst.get("EA")))
        verifica("o cuidado vem com o nome e o que a autorizacao diz",
                 inst.get("EA", {}).get("cuidados", [{}])[0].get("necessidade_especial") == "Cadeira de rodas",
                 str(inst.get("EA", {}).get("cuidados")))
        dias = [d["descricao"] for d in p.get("por_dia", [])]
        verifica("por dia em ordem, e sem dia por ultimo", dias == ["Sabado", "Domingo", None], str(dias))

        print("\nNucleos")
        r = cm.put(f"/monitoria/{edicao.id}/nucleos", json={"instituicoes": [
            {"instituicao_id": a.id, "nucleo": "A", "cor_bata_nome": "Vermelho", "cor_bata_hex": "#D32F2F"},
            {"instituicao_id": b.id, "nucleo": "B", "cor_bata_nome": "Azul", "cor_bata_hex": "#1E63E9"},
        ]})
        verifica("grava nucleo e cor", r.status_code == 200, r.text[:160])
        inst = {i["sigla"]: i for i in r.json().get("por_instituicao", [])} if r.status_code == 200 else {}
        verifica("e devolve o painel com eles",
                 inst.get("EA", {}).get("nucleo") == "A" and inst["EA"]["cor_bata_hex"] == "#d32f2f", str(inst.get("EA")))
        r = cm.put(f"/monitoria/{edicao.id}/nucleos", json={"instituicoes": [
            {"instituicao_id": sem.id, "nucleo": "C"}]})
        verifica("instituicao sem dia nao entra em nucleo", r.status_code == 409, str(r.status_code))
        r = cm.put(f"/monitoria/{edicao.id}/nucleos", json={"instituicoes": [
            {"instituicao_id": a.id, "nucleo": "E"}]})
        verifica("nucleo fora de A a D e recusado", r.status_code == 422, str(r.status_code))

        print("\nQuem abre")
        cc = TestClient(app); entrar(cc, coord.email)
        verifica("a coordenacao geral tambem abre",
                 cc.get(f"/monitoria/{edicao.id}/painel").status_code == 200)
        mo = TestClient(app); entrar(mo, monitor.email)
        verifica("o monitor de base nao abre",
                 mo.get(f"/monitoria/{edicao.id}/painel").status_code == 403)
        verifica("nem grava nucleo",
                 mo.put(f"/monitoria/{edicao.id}/nucleos", json={"instituicoes": []}).status_code == 403)

        print("\nFicha da instituicao")
        r = cm.get(f"/instituicoes/{a.id}/ficha", params={"edicao_id": edicao.id})
        f = r.json() if r.status_code == 200 else {}
        verifica("a ficha abre com o dia, o nucleo e a contagem",
                 r.status_code == 200 and f.get("nucleo") == "A" and f.get("criancas") == 2
                 and f.get("desistentes") == 1 and f.get("dia_evento_descricao") == "Sabado", r.text[:200])
        verifica("e traz o monitor da instituicao com o contato",
                 [m["nome"] for m in f.get("monitores", [])] == [f"{MARCA} Monitor"]
                 and f["monitores"][0]["email"] == monitor.email, str(f.get("monitores")))
        r = mo.get(f"/instituicoes/{b.id}/ficha", params={"edicao_id": edicao.id})
        verifica("o monitor nao abre a ficha de instituicao que nao e dele", r.status_code == 404, str(r.status_code))
        r = mo.get(f"/instituicoes/{a.id}/ficha", params={"edicao_id": edicao.id})
        verifica("mas abre a da dele", r.status_code == 200, str(r.status_code))

        print("\nProgramacao do evento")
        r = cc.get(f"/programacao/{edicao.id}")
        verifica("sem programacao ainda, diz que nao existe",
                 r.status_code == 200 and r.json()["existe"] is False, r.text[:120])
        prog = {
            "atividades": [{"nome": "Teatro", "cor": "#c2185b"}],
            "blocos": [{"titulo": "Rodizios - Tarde", "horarios": [
                {"inicio": "13:45", "fim": "14:15", "modo": "por_nucleo",
                 "nucleos": {"A": "Teatro", "B": "Infláveis P", "C": None, "D": "Teatro"}},
                {"inicio": "15:05", "fim": "15:35", "modo": "todos", "atividade": "Mágico"},
            ]}],
        }
        r = cc.put(f"/programacao/{edicao.id}", json=prog)
        verifica("a coordenacao geral salva a programacao", r.status_code == 200, r.text[:160])
        r = cc.get(f"/programacao/{edicao.id}")
        p = r.json()
        verifica("e ela volta igual, com quem salvou",
                 p["existe"] and p["blocos"][0]["horarios"][1]["atividade"] == "Mágico"
                 and p["atualizado_por"] == f"{MARCA} Coord", str(p)[:200])
        sab = next((d for d in p["nucleos"] if d["descricao"] == "Sabado"), None)
        verifica("e traz os nucleos de cada dia, com a instituicao no dela",
                 sab is not None and any(i["nucleo"] == "A" and i["nome"] == a.nome
                                         for i in sab["instituicoes"]), str(p["nucleos"])[:300])
        ruim = {"atividades": [], "blocos": [{"titulo": "X", "horarios": [
            {"inicio": "14:00", "fim": "13:00", "modo": "todos", "atividade": "Y"}]}]}
        verifica("horario que termina antes de comecar e recusado",
                 cc.put(f"/programacao/{edicao.id}", json=ruim).status_code == 422)
        verifica("a coordenacao da monitoria nao mexe na programacao",
                 cm.put(f"/programacao/{edicao.id}", json=prog).status_code == 403)
        r = mo.get(f"/programacao/{edicao.id}")
        verifica("antes de concluida, o monitor ainda nao ve o quadro",
                 r.status_code == 200 and r.json()["existe"] is False
                 and r.json()["blocos"] == [], r.text[:160])
        verifica("o monitor nao conclui",
                 mo.put(f"/programacao/{edicao.id}/conclusao", json={"concluida": True}).status_code == 403)
        r = cc.put(f"/programacao/{edicao.id}/conclusao", json={"concluida": True})
        verifica("a coordenacao geral conclui",
                 r.status_code == 200 and r.json()["concluida_por"] == f"{MARCA} Coord", r.text[:160])
        r = mo.get(f"/programacao/{edicao.id}")
        p = r.json() if r.status_code == 200 else {}
        verifica("concluida, o monitor ve o quadro e os nucleos, sem poder editar",
                 p.get("existe") is True and p.get("pode_editar") is False
                 and p["blocos"][0]["horarios"][1]["atividade"] == "Mágico" and p.get("nucleos"),
                 str(p)[:200])
        verifica("e continua sem salvar",
                 mo.put(f"/programacao/{edicao.id}", json=prog).status_code == 403)
        r = cc.put(f"/programacao/{edicao.id}/conclusao", json={"concluida": False})
        verifica("reaberta, some de novo para o monitor",
                 r.status_code == 200 and mo.get(f"/programacao/{edicao.id}").json()["existe"] is False)
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
