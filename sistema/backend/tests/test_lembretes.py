"""Testa a lista do lembrete do evento (tela de envio de cartoes).

O que ela promete:

  1. um lembrete por padrinho POR DIA: quem tem criancas no sabado e no
     domingo aparece nos dois, sabendo que tem outro;
  2. so fica pronto quem tem TODOS os cartoes daquele dia subidos — e sem
     WhatsApp valido nao fica pronto, fica "sem_whatsapp";
  3. promessa e crianca desistente ficam de fora;
  4. cesta e festa da mesma crianca sao dois cartoes;
  5. so quem enxerga a edicao inteira monta a lista.

Rodar com:  python -m tests.test_lembretes
"""

from datetime import date

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
    DiaEvento,
    Edicao,
    Instituicao,
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

MARCA = "ZZ_LEM"
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
                db.execute(delete(Cartao).where(Cartao.crianca_id.in_(cris)))
                db.execute(delete(Apadrinhamento).where(Apadrinhamento.crianca_id.in_(cris)))
            if pads:
                db.execute(delete(Pagamento).where(Pagamento.padrinho_id.in_(pads)))
                db.execute(delete(Padrinho).where(Padrinho.id.in_(pads)))
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
    sabado = DiaEvento(edicao_id=edicao.id, data=date(2026, 12, 19), descricao="Sabado")
    domingo = DiaEvento(edicao_id=edicao.id, data=date(2026, 12, 20), descricao="Domingo")
    db.add_all([sabado, domingo]); db.flush()

    inst_a = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola A")
    inst_b = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola B")
    db.add_all([inst_a, inst_b]); db.flush()

    def crianca(codigo, inst, dia):
        c = Crianca(edicao_id=edicao.id, instituicao_id=inst.id,
                    dia_evento_id=dia.id if dia else None,
                    codigo=codigo, nome=f"Crianca {codigo} Sobrenome", idade=8, sexo="F")
        db.add(c); db.flush()
        return c

    a1 = crianca("A1", inst_a, sabado)
    a2 = crianca("A2", inst_a, sabado)
    a3 = crianca("A3", inst_a, sabado)
    a4 = crianca("A4", inst_a, sabado)
    a5 = crianca("A5", inst_a, sabado)
    a6 = crianca("A6", inst_a, sabado)
    b1 = crianca("B1", inst_b, domingo)
    sem_dia = crianca("S1", inst_b, None)
    a5.desistiu_em = func.now()

    def padrinho(nome, whatsapp):
        p = Padrinho(edicao_id=edicao.id, nome=f"{MARCA} {nome}", whatsapp=whatsapp)
        db.add(p); db.flush()
        return p

    dois_dias = padrinho("Dois Dias", "(85) 99999-0001")
    sem_zap = padrinho("Sem Zap", None)
    prometeu = padrinho("Prometeu", "(85) 99999-0002")
    cesta_e_festa = padrinho("Cesta e Festa", "(85) 99999-0003")

    def apadrinhar(p, c, tipo, pago=True):
        pagamento = None
        if pago:
            pagamento = Pagamento(padrinho_id=p.id, valor=120, data=date(2026, 10, 1))
            db.add(pagamento); db.flush()
        db.add(Apadrinhamento(crianca_id=c.id, padrinho_id=p.id, tipo=tipo, valor=120,
                              pagamento_id=pagamento.id if pagamento else None))

    def cartao(c, tipo):
        db.add(Cartao(crianca_id=c.id, tipo=tipo, arquivo=f"zz/{c.codigo}_{tipo}.jpg"))

    # Dois Dias: sabado completo (A1 cesta, A2 festa), domingo sem o cartao (B1).
    # A desistente A5 e dele tambem, e sem cartao: se entrasse, o sabado nao
    # ficaria pronto.
    apadrinhar(dois_dias, a1, "cesta"); cartao(a1, "cesta")
    apadrinhar(dois_dias, a2, "festa"); cartao(a2, "festa")
    apadrinhar(dois_dias, b1, "cesta")
    apadrinhar(dois_dias, a5, "cesta")
    # Sem Zap: o cartao esta aqui, falta o numero. E tem uma crianca sem dia.
    apadrinhar(sem_zap, a3, "cesta"); cartao(a3, "cesta")
    apadrinhar(sem_zap, sem_dia, "festa")
    # Prometeu: promessa nao recebe lembrete.
    apadrinhar(prometeu, a4, "cesta", pago=False); cartao(a4, "cesta")
    # Cesta e Festa da mesma crianca: dois cartoes, so um subiu.
    apadrinhar(cesta_e_festa, a6, "cesta"); cartao(a6, "cesta")
    apadrinhar(cesta_e_festa, a6, "festa")

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
    coord_captacao = usuario("CoordCap", "Comissarios - coordenacao")
    comissario = usuario("Com", "Comissarios - comissario", [inst_a.id, inst_b.id])
    monitor = usuario("Mon", "Monitoria - coordenacao")
    for c in (a1, a2, a3, a4, a5, a6, b1, sem_dia):
        c.comissario_id = comissario.id
    db.commit()

    try:
        print("\nA lista por dia")
        cc = TestClient(app); entrar(cc, coord.email)
        r = cc.get(f"/lembretes?edicao_id={edicao.id}")
        verifica("coordenacao recebe 200", r.status_code == 200, r.text[:200])
        dias = r.json()
        verifica("sabado, domingo e o grupo sem dia, nessa ordem",
                 [d["descricao"] for d in dias] == ["Sabado", "Domingo", None],
                 str([d["descricao"] for d in dias]))

        def do_dia(i):
            return {p["padrinho_nome"].removeprefix(f"{MARCA} "): p for p in dias[i]["padrinhos"]}

        sab, dom, nenhum = do_dia(0), do_dia(1), do_dia(2)

        print("\nUm lembrete por dia")
        verifica("Dois Dias aparece no sabado e no domingo",
                 "Dois Dias" in sab and "Dois Dias" in dom)
        verifica("e sabe que tem outro dia", sab["Dois Dias"]["outros_dias"] == 1
                 and dom["Dois Dias"]["outros_dias"] == 1)
        verifica("o sabado leva so os cartoes do sabado",
                 sorted(c["crianca_codigo"] for c in sab["Dois Dias"]["cartoes"]) == ["A1", "A2"])

        print("\nPronto so com tudo na mao")
        verifica("sabado completo e pronto", sab["Dois Dias"]["situacao"] == "pronto")
        verifica("domingo sem o cartao fica em progresso",
                 dom["Dois Dias"]["situacao"] == "em_progresso" and dom["Dois Dias"]["faltam"] == 1)
        verifica("cartoes completos sem WhatsApp fica sem_whatsapp",
                 sab["Sem Zap"]["situacao"] == "sem_whatsapp"
                 and sab["Sem Zap"]["whatsapp_valido"] is False)

        print("\nQuem fica de fora")
        verifica("promessa nao recebe lembrete", "Prometeu" not in sab)
        verifica("a desistente nao entra no lembrete",
                 all(c["crianca_codigo"] != "A5" for p in sab.values() for c in p["cartoes"]))
        verifica("crianca sem dia cai no grupo sem dia",
                 [c["crianca_codigo"] for c in nenhum["Sem Zap"]["cartoes"]] == ["S1"])

        print("\nCesta e festa da mesma crianca")
        cf = sab["Cesta e Festa"]
        verifica("sao dois cartoes", sorted(c["tipo"] for c in cf["cartoes"]) == ["cesta", "festa"])
        verifica("e falta o de festa", cf["faltam"] == 1 and cf["situacao"] == "em_progresso")

        print("\nQuem monta a lista")
        cap = TestClient(app); entrar(cap, coord_captacao.email)
        verifica("coordenacao da captacao recebe 200",
                 cap.get(f"/lembretes?edicao_id={edicao.id}").status_code == 200)
        com = TestClient(app); entrar(com, comissario.email)
        verifica("comissario recebe 403: so ve as proprias criancas",
                 com.get(f"/lembretes?edicao_id={edicao.id}").status_code == 403)
        mon = TestClient(app); entrar(mon, monitor.email)
        verifica("monitoria recebe 403: nao envia cartao",
                 mon.get(f"/lembretes?edicao_id={edicao.id}").status_code == 403)
    finally:
        limpar(db, log_inicial)
        db.close()

    print(f"\n{ok} ok, {len(falhas)} falha(s)")
    if falhas:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
