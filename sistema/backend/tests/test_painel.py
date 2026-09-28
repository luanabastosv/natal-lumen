"""Testa o painel: apadrinhamento de cesta e de festa (fase 9).

Dois pontos delicados. O primeiro: os numeros tem de respeitar o mesmo filtro
das telas — quem so alcanca uma instituicao ve os numeros dela, nao os da
edicao inteira. O segundo: a lista de comissarios comeca pelo TIME da edicao, e
nao pelas criancas atribuidas, senao o comissario sem nenhuma crianca na mao —
que e exatamente quem a coordenacao precisa achar — nao apareceria.

Rodar com:  python -m tests.test_painel
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
    Compra,
    Crianca,
    DiaEvento,
    Edicao,
    Grupo,
    Instituicao,
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

MARCA = "ZZ_PAI"
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
    dia = DiaEvento(edicao_id=edicao.id, data=date(2026, 12, 20), descricao="sabado")
    db.add(dia); db.flush()

    inst_a = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola A")
    inst_b = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola B")
    db.add_all([inst_a, inst_b]); db.flush()

    # 3 criancas na A, 2 na B.
    criancas_a = [
        Crianca(edicao_id=edicao.id, instituicao_id=inst_a.id, dia_evento_id=dia.id,
                codigo=f"A{i}", nome=f"Crianca A{i} Sobrenome", idade=8, sexo="F")
        for i in range(1, 4)
    ]
    criancas_b = [
        Crianca(edicao_id=edicao.id, instituicao_id=inst_b.id, dia_evento_id=dia.id,
                codigo=f"B{i}", nome=f"Crianca B{i} Sobrenome", idade=9, sexo="M")
        for i in range(1, 3)
    ]
    db.add_all(criancas_a + criancas_b); db.flush()

    padrinho = Padrinho(edicao_id=edicao.id, nome=f"{MARCA} Doador"); db.add(padrinho); db.flush()

    # A1 completa (cesta + festa), A2 so cesta, A3 nenhum. B1 so cesta.
    db.add_all([
        Apadrinhamento(crianca_id=criancas_a[0].id, padrinho_id=padrinho.id, tipo="cesta", valor=120),
        Apadrinhamento(crianca_id=criancas_a[0].id, padrinho_id=padrinho.id, tipo="festa", valor=60),
        Apadrinhamento(crianca_id=criancas_a[1].id, padrinho_id=padrinho.id, tipo="cesta", valor=120),
        Apadrinhamento(crianca_id=criancas_b[0].id, padrinho_id=padrinho.id, tipo="cesta", valor=120),
    ])
    db.flush()

    # Um pagamento quita a cesta da A1.
    pagamento = Pagamento(padrinho_id=padrinho.id, valor=120, data=date(2026, 11, 1))
    db.add(pagamento); db.flush()
    a1_cesta = db.scalar(select(Apadrinhamento).where(
        Apadrinhamento.crianca_id == criancas_a[0].id, Apadrinhamento.tipo == "cesta"))
    a1_cesta.pagamento_id = pagamento.id

    db.add_all([
        Cartao(crianca_id=criancas_a[0].id, tipo="cesta", arquivo="x.jpg", status="enviado"),
        Cartao(crianca_id=criancas_a[0].id, tipo="festa", arquivo="y.jpg"),
        Cartao(crianca_id=criancas_b[0].id, tipo="cesta", arquivo="z.jpg"),
    ])
    db.add_all([
        Kit(crianca_id=criancas_a[0].id, status="entregue"),
        Kit(crianca_id=criancas_a[1].id, status="montado"),
    ])
    db.add(Compra(edicao_id=edicao.id, descricao="Cestas", quantidade=5,
                  valor_total=1000, data=date(2026, 11, 1)))

    criancas_a[0].checkin_em = func.now()
    db.flush()

    def usuario(sufixo, perfil, instituicoes=(), grupo_id=None):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        v = UsuarioEdicao(usuario_id=u.id, edicao_id=edicao.id, perfil_id=perfis[perfil].id,
                          grupo_id=grupo_id)
        db.add(v); db.flush()
        for i in instituicoes:
            db.add(UsuarioInstituicao(usuario_edicao_id=v.id, instituicao_id=i))
        return u

    grupo = Grupo(cidade_id=cidade.id, nome="Elyon", nome_normalizado="elyon")
    db.add(grupo); db.flush()

    coord = usuario("Coord", "Coordenacao")
    so_a = usuario("SoA", "Monitor", [inst_a.id])
    # Dois comissarios: um com criancas na mao, outro sem nenhuma ainda.
    com_a = usuario("ComA", "Comissario", [inst_a.id], grupo_id=grupo.id)
    usuario("ComVazio", "Comissario", [inst_b.id], grupo_id=grupo.id)

    # A1 (completa) e A3 (sem nenhum padrinho) sao do ComA. A2 e as da B ficam
    # sem responsavel, para a linha "Sem comissario" ter o que contar.
    criancas_a[0].comissario_id = com_a.id
    criancas_a[2].comissario_id = com_a.id
    db.commit()

    try:
        cc = TestClient(app); entrar(cc, coord.email)

        print("\nNumeros da edicao inteira")
        r = cc.get(f"/painel/{edicao.id}")
        verifica("o painel responde", r.status_code == 200, r.text[:140])
        rel = r.json() if r.status_code == 200 else {}
        resumo = rel.get("resumo", {})

        verifica("conta as 5 criancas", resumo.get("criancas") == 5, str(resumo.get("criancas")))
        verifica("conta as 2 instituicoes", resumo.get("instituicoes") == 2, str(resumo.get("instituicoes")))
        verifica("conta 3 cestas apadrinhadas",
                 resumo.get("cesta_feitos") == 3, str(resumo.get("cesta_feitos")))
        verifica("conta 1 festa apadrinhada",
                 resumo.get("festa_feitos") == 1, str(resumo.get("festa_feitos")))
        verifica("o painel nao carrega mais numero que nao seja de apadrinhamento",
                 not (set(resumo) & {"cartoes_digitalizados", "kits_entregues", "valor_pago",
                                     "checkin_feitos", "compras_total"}),
                 str(sorted(resumo)))

        print("\nQuebra por instituicao")
        por_inst = {l["instituicao"]: l for l in rel.get("por_instituicao", [])}
        verifica("quebra pelas 2 instituicoes", len(por_inst) == 2, str(list(por_inst)))
        verifica("Escola A tem 3 criancas",
                 por_inst.get(f"{MARCA} Escola A", {}).get("criancas") == 3,
                 str(por_inst.get(f"{MARCA} Escola A")))
        verifica("Escola A tem 2 cestas e 1 festa",
                 (por_inst.get(f"{MARCA} Escola A", {}).get("cesta"),
                  por_inst.get(f"{MARCA} Escola A", {}).get("festa")) == (2, 1),
                 str(por_inst.get(f"{MARCA} Escola A")))
        verifica("Escola B tem 1 cesta e nenhuma festa",
                 (por_inst.get(f"{MARCA} Escola B", {}).get("cesta"),
                  por_inst.get(f"{MARCA} Escola B", {}).get("festa")) == (1, 0),
                 str(por_inst.get(f"{MARCA} Escola B")))

        print("\nQuebra por comissario")
        por_com = {l["comissario"]: l for l in rel.get("por_comissario", [])}
        linha_a = por_com.get(f"{MARCA} ComA", {})
        verifica("o comissario aparece com o grupo dele",
                 linha_a.get("grupo") == "Elyon", str(linha_a.get("grupo")))
        verifica("conta as 2 criancas atribuidas a ele",
                 linha_a.get("criancas") == 2, str(linha_a.get("criancas")))
        verifica("uma delas esta completa, a outra falta",
                 (linha_a.get("completas"), linha_a.get("faltam")) == (1, 1),
                 f"{linha_a.get('completas')}/{linha_a.get('faltam')}")
        verifica("separa cesta e festa das criancas dele",
                 (linha_a.get("cesta"), linha_a.get("festa")) == (1, 1),
                 f"{linha_a.get('cesta')}/{linha_a.get('festa')}")

        vazio = por_com.get(f"{MARCA} ComVazio", {})
        verifica("o comissario sem nenhuma crianca tambem aparece, zerado",
                 vazio.get("criancas") == 0 and vazio.get("faltam") == 0,
                 str(vazio))

        sem = por_com.get("Sem comissário", {})
        verifica("as 3 criancas sem responsavel viram uma linha propria",
                 sem.get("criancas") == 3 and sem.get("comissario_id") is None, str(sem))
        verifica("a linha sem responsavel e a ultima",
                 rel.get("por_comissario", [])[-1]["comissario_id"] is None,
                 str([l["comissario"] for l in rel.get("por_comissario", [])]))
        verifica("a coordenacao, que nao assumiu crianca, fica fora da lista",
                 f"{MARCA} Coord" not in por_com, str(list(por_com)))

        print("\nSem ver_painel nao ha relatorio")
        ca = TestClient(app); entrar(ca, so_a.email)
        r = ca.get(f"/painel/{edicao.id}")
        verifica(
            "monitor nao tem ver_painel, entao nao ve o relatorio",
            r.status_code == 403,
            str(r.status_code),
        )

        print("\nCom ver_painel, os numeros respeitam o filtro por instituicao")
        # Perfis vivem na base justamente para poderem mudar. Aqui damos
        # ver_painel ao Monitor para exercitar o caminho filtrado, e desfazemos
        # no fim.
        from app.models import Permissao

        perfil_monitor = perfis["Monitor"]
        ver_painel = db.scalar(select(Permissao).where(Permissao.codigo == "ver_painel"))
        perfil_monitor.permissoes.append(ver_painel)
        db.commit()

        ca = TestClient(app); entrar(ca, so_a.email)
        r = ca.get(f"/painel/{edicao.id}")
        verifica("com a permissao, o monitor ve o relatorio", r.status_code == 200, r.text[:130])
        so_escola_a = r.json()["resumo"] if r.status_code == 200 else {}

        verifica("ve so as 3 criancas da instituicao dele",
                 so_escola_a.get("criancas") == 3, str(so_escola_a.get("criancas")))
        verifica("ve so 1 instituicao", so_escola_a.get("instituicoes") == 1, str(so_escola_a.get("instituicoes")))
        verifica("ve so as 2 cestas e 1 festa da Escola A",
                 (so_escola_a.get("cesta_feitos"), so_escola_a.get("festa_feitos")) == (2, 1),
                 f"{so_escola_a.get('cesta_feitos')}/{so_escola_a.get('festa_feitos')}")
        verifica("a quebra por instituicao mostra so a dele",
                 len(r.json().get("por_instituicao", [])) == 1,
                 str(len(r.json().get("por_instituicao", []))))
        # O time inteiro continua na lista — inclusive o comissario da Escola B,
        # que nao e alcancada por ele. O que o filtro esconde sao as CRIANCAS,
        # nao os nomes de quem trabalha na edicao.
        com_filtrado = {l["comissario"]: l for l in r.json().get("por_comissario", [])}
        verifica("o comissario da Escola A conta so 2 criancas",
                 com_filtrado.get(f"{MARCA} ComA", {}).get("criancas") == 2,
                 str(com_filtrado.get(f"{MARCA} ComA")))
        verifica("a linha sem responsavel so conta a crianca da Escola A",
                 com_filtrado.get("Sem comissário", {}).get("criancas") == 1,
                 str(com_filtrado.get("Sem comissário")))

        perfil_monitor.permissoes.remove(ver_painel)
        db.commit()

        print("\nAlcance")
        outra = Edicao(cidade_id=cidade.id, ano=2027, nome=f"{MARCA} Outra",
                       valor_cesta=1, valor_festa=1)
        db.add(outra); db.commit()
        r = cc.get(f"/painel/{outra.id}")
        verifica("edicao sem vinculo devolve 404", r.status_code == 404, str(r.status_code))

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
