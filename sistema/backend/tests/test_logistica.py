"""Testa kits, financeiro (saidas e recebimentos) e check-in (fase 8).

Rodar com:  python -m tests.test_logistica
"""

from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text

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
    InstituicaoDia,
    Kit,
    LogAtividade,
    Padrinho,
    Perfil,
    Recebimento,
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
                db.execute(delete(Padrinho).where(Padrinho.id.in_(pads)))
            db.execute(delete(Compra).where(Compra.edicao_id.in_(eds)))
            db.execute(delete(Recebimento).where(Recebimento.edicao_id.in_(eds)))
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
    db.add(InstituicaoDia(edicao_id=edicao.id, instituicao_id=inst.id, dia_evento_id=hoje.id))
    db.flush()

    def usuario(sufixo, perfil):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        v = UsuarioEdicao(usuario_id=u.id, edicao_id=edicao.id, perfil_id=perfis[perfil].id)
        db.add(v); db.flush()
        db.add(UsuarioInstituicao(usuario_edicao_id=v.id, instituicao_id=inst.id))
        return u

    estrutura = usuario("Estrutura", "Estrutura")
    comissario = usuario("Comissario", "Comissarios - comissario")
    # Os recebimentos sao da coordenacao: e a mesma permissao dos pagamentos.
    coord = usuario("Coord", "Coordenacao")
    monitor = usuario("Monitor", "Monitoria - monitores")
    padrinho = Padrinho(edicao_id=edicao.id, nome=f"{MARCA} Padrinho")
    db.add(padrinho); db.flush()
    # No Bruno e na Carla, nunca na Ana: o check-in dela confere justamente o
    # aviso de crianca SEM padrinho, e apadrinha-la aqui calaria esse aviso.
    cesta_bruno = Apadrinhamento(
        crianca_id=bruno.id, padrinho_id=padrinho.id, tipo="cesta", valor=120
    )
    festa_bruno = Apadrinhamento(
        crianca_id=bruno.id, padrinho_id=padrinho.id, tipo="festa", valor=60
    )
    cesta_carla = Apadrinhamento(
        crianca_id=carla.id, padrinho_id=padrinho.id, tipo="cesta", valor=120
    )
    festa_carla = Apadrinhamento(
        crianca_id=carla.id, padrinho_id=padrinho.id, tipo="festa", valor=60
    )
    db.add_all([cesta_bruno, festa_bruno, cesta_carla, festa_carla]); db.flush()
    db.commit()

    try:
        ce = TestClient(app); entrar(ce, estrutura.email)
        ck = TestClient(app); entrar(ck, comissario.email)
        cc = TestClient(app); entrar(cc, coord.email)
        cm = TestClient(app); entrar(cm, monitor.email)

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

        verifica("marcar montado grava a hora",
                 r.json()["itens"][0]["montado_em"] is not None
                 or any(i["montado_em"] for i in ce.get("/kits").json()["itens"]),
                 "nenhum montado_em preenchido")

        r = ce.post("/kits", json={"criancas": [ana.id], "status": "pendente"})
        verifica("desmarcar limpa a hora da montagem",
                 r.json()[0]["montado_em"] is None, str(r.json()[0]["montado_em"]))

        # O estado "entregue" saiu do sistema em 30/09/2026: o kit e montado ou
        # nao, e a entrega no dia quem acompanha e o check-in.
        r = ce.post("/kits", json={"criancas": [ana.id], "status": "entregue"})
        verifica("o estado entregue nao existe mais",
                 r.status_code == 422, str(r.status_code))
        r = ce.get("/kits", params={"situacao": "entregue"})
        verifica("nem como filtro", r.status_code == 422, str(r.status_code))

        r = ce.post("/kits", json={"criancas": [ana.id], "status": "montado"})
        verifica("e montado volta a valer", r.status_code == 200, r.text[:120])

        print("\nKits: o que a estrutura precisa para montar")
        item = next(i for i in ce.get("/kits").json()["itens"] if i["crianca_id"] == ana.id)
        verifica("a linha traz codigo, idade e sexo",
                 item.get("crianca_codigo") and item.get("idade") and item.get("sexo"),
                 str({k: item.get(k) for k in ("crianca_codigo", "idade", "sexo")}))
        verifica("e diz se a crianca desistiu",
                 "desistiu_em" in item, str(sorted(item)))

        print("\nKits: quem montou e quem conferiu")
        verifica("a linha diz quem montou", item.get("montado_por") == estrutura.nome,
                 str(item.get("montado_por")))
        verifica("e ainda ninguem conferiu", item.get("conferido_por") is None,
                 str(item.get("conferido_por")))

        r = ce.post(f"/kits/{carla.id}/conferir")
        verifica("kit nao montado nao se confere", r.status_code == 409, str(r.status_code))

        r = ce.post(f"/kits/{ana.id}/conferir")
        verifica("conferir grava quem conferiu",
                 r.status_code == 200 and r.json()["conferido_por"] == estrutura.nome
                 and r.json()["conferido_em"] is not None, r.text[:160])
        item = next(i for i in ce.get("/kits").json()["itens"] if i["crianca_id"] == ana.id)
        verifica("e a lista mostra", item["conferido_por"] == estrutura.nome, str(item))

        r = ck.post(f"/kits/{ana.id}/conferir")
        verifica("comissario NAO confere kit", r.status_code == 403, str(r.status_code))

        r = ce.post("/kits/conferir", json={"criancas": [ana.id, bruno.id, carla.id]})
        por_id = {k["crianca_id"]: k for k in r.json()} if r.status_code == 200 else {}
        verifica("confere em lote", r.status_code == 200 and len(por_id) == 3, r.text[:160])
        verifica("o lote confere o montado que faltava",
                 por_id.get(bruno.id, {}).get("conferido_por") == estrutura.nome, str(por_id.get(bruno.id)))
        verifica("e pula o que nao esta montado, sem recusar o resto",
                 por_id.get(carla.id, {}).get("conferido_por") is None, str(por_id.get(carla.id)))

        r = ce.post("/kits", json={"criancas": [ana.id], "status": "pendente"})
        verifica("desmontar apaga a conferencia",
                 r.json()[0]["conferido_por"] is None and r.json()[0]["montado_por"] is None,
                 str(r.json()[0]))
        ce.post("/kits", json={"criancas": [ana.id], "status": "montado"})

        print("\nKits: duas pessoas marcando a mesma crianca")
        # A equipe de estrutura marca em paralelo na semana do evento. Antes,
        # "procura e se nao houver cria" deixava as duas inserirem, e a segunda
        # levava 500 pela unicidade. Aqui a outra pessoa chega primeiro: o kit
        # ja existe quando este pedido entra.
        db.execute(text("DELETE FROM kits WHERE crianca_id = :c"), {"c": carla.id})
        db.commit()
        db.execute(
            text("INSERT INTO kits (crianca_id, status) VALUES (:c, 'pendente')"),
            {"c": carla.id},
        )
        db.commit()

        r = ce.post("/kits", json={"criancas": [carla.id], "status": "montado"})
        verifica("marcar kit que outra pessoa acabou de criar nao quebra",
                 r.status_code == 200, r.text[:140])
        verifica("e o estado vale", r.json()[0]["status"] == "montado", r.text[:120])

        r = ce.post("/kits", json={"criancas": [carla.id], "status": "montado"})
        verifica("marcar duas vezes seguidas tambem nao quebra",
                 r.status_code == 200, r.text[:140])

        print("\nKits: a ordem e do servidor")
        r = ce.get("/kits")
        codigos = [i["crianca_codigo"] for i in r.json()["itens"]]
        verifica("a lista vem por codigo, sem ninguem pedir",
                 codigos == sorted(codigos), str(codigos))

        r = ce.get("/kits", params={"ordenar_por": "idade", "ordem": "desc"})
        idades = [i["idade"] for i in r.json()["itens"]]
        verifica("ordena por idade, da maior para a menor",
                 idades == sorted(idades, reverse=True), str(idades))

        r = ce.get("/kits", params={"ordenar_por": "nome"})
        nomes = [i["crianca_nome"] for i in r.json()["itens"]]
        verifica("e por nome", nomes == sorted(nomes), str(nomes))

        r = ce.get("/kits", params={"ordenar_por": "inventado"})
        verifica("coluna que nao existe e recusada", r.status_code == 422, str(r.status_code))

        print("\nKits: abas por instituicao")
        r = ce.get("/kits/instituicoes", params={"edicao_id": edicao.id})
        verifica("as abas respondem", r.status_code == 200, r.text[:130])
        abas = r.json() if r.status_code == 200 else []
        verifica("uma aba por instituicao com crianca", len(abas) >= 1, str(len(abas)))
        verifica("a aba conta total e montados",
                 all("total" in a and "montados" in a and "desistentes" in a for a in abas),
                 str(abas[:1]))
        somados = sum(a["total"] for a in abas)
        verifica("e os totais das abas somam a lista inteira",
                 somados == ce.get("/kits").json()["total"], f"{somados}")

        verifica("a aba traz o dia da instituicao",
                 all("dia_evento" in a and "dia_evento_descricao" in a for a in abas),
                 str(abas[:1]))

        aba = next(a for a in abas if a["instituicao_id"] == inst.id)
        verifica("e e o dia que a instituicao vai",
                 aba["dia_evento"] == str(hoje.data) and aba["dia_evento_descricao"] == "hoje",
                 str(aba))

        r = ce.get("/kits/perfil", params={"edicao_id": edicao.id})
        verifica("o perfil por idade e sexo responde", r.status_code == 200, r.text[:130])
        perfil = r.json() if r.status_code == 200 else []
        verifica("o perfil conta idade e sexo",
                 any(p["idade"] == 8 and p["sexo"] == "F" for p in perfil), str(perfil[:3]))
        desistentes = sum(a["desistentes"] for a in abas)
        verifica("e soma a lista inteira, sem as desistentes",
                 sum(p["quantidade"] for p in perfil) == somados - desistentes,
                 f"{sum(p['quantidade'] for p in perfil)} de {somados} - {desistentes}")

        print("\nKits: a desistente nao e caixa a montar")
        db.refresh(carla)
        carla.desistiu_em = datetime.now(UTC)
        db.commit()
        r = ce.get("/kits", params={"edicao_id": edicao.id})
        itens = r.json()["itens"]
        esperado = sum(1 for i in itens if i["status"] == "pendente" and not i["desistiu_em"])
        verifica("o 'a montar' nao conta a desistente",
                 r.json()["resumo"].get("pendente", 0) == esperado,
                 f"{r.json()['resumo']} esperado {esperado}")
        verifica("mas ela continua na lista",
                 any(i["crianca_id"] == carla.id for i in itens), str(len(itens)))
        r = ce.post("/kits", json={"criancas": [carla.id], "status": "montado"})
        verifica("kit de desistente nao se marca", r.status_code == 409, str(r.status_code))
        r = ce.post("/kits", json={"criancas": [ana.id, carla.id], "status": "montado"})
        verifica("nem misturado num lote", r.status_code == 409, str(r.status_code))
        r = ce.post(f"/kits/{carla.id}/conferir")
        verifica("nem se confere", r.status_code == 409, str(r.status_code))
        carla.desistiu_em = None
        db.commit()

        r = ce.get("/kits", params={"instituicao_id": abas[0]["instituicao_id"]})
        verifica("a lista filtra por instituicao",
                 all(i["instituicao_id"] == abas[0]["instituicao_id"] for i in r.json()["itens"]),
                 str(r.json()["total"]))

        r = ck.post("/kits", json={"criancas": [ana.id], "status": "montado"})
        verifica("comissario NAO mexe em kits", r.status_code == 403, str(r.status_code))

        print("\nEstrutura: so os kits")
        r = ce.get("/criancas")
        verifica("estrutura NAO abre a lista de criancas", r.status_code == 403, str(r.status_code))
        r = ce.get("/compras")
        verifica("estrutura NAO ve as saidas", r.status_code == 403, str(r.status_code))

        print("\nFinanceiro — saidas")
        r = cc.post("/compras", json={
            "edicao_id": edicao.id, "descricao": "Cestas basicas", "categoria": "cesta",
            "quantidade": 100, "valor_total": "5000.00", "fornecedor": "Atacado X",
            "data": str(date.today()),
        })
        verifica("registra compra", r.status_code == 201, r.text[:130])
        verifica("guarda quem registrou", r.json()["responsavel"] == coord.nome, str(r.json()["responsavel"]))

        cc.post("/compras", json={
            "edicao_id": edicao.id, "descricao": "Brinquedos", "categoria": "presente",
            "quantidade": 100, "valor_total": "3000.00", "data": str(date.today()),
        })
        cc.post("/compras", json={
            "edicao_id": edicao.id, "descricao": "Sabonetes", "categoria": "cesta",
            "quantidade": 100, "valor_total": "500.00", "data": str(date.today()),
        })

        r = cc.get("/compras")
        verifica("soma o total gasto", r.json()["total_gasto"] == "8500.00", r.json()["total_gasto"])
        verifica("agrupa por categoria",
                 r.json()["por_categoria"] == {"cesta": "5500.00", "presente": "3000.00"},
                 str(r.json()["por_categoria"]))

        r = ck.get("/compras")
        verifica("comissario NAO ve compras", r.status_code == 403, str(r.status_code))

        print("\nFinanceiro — recebimentos")
        r = cc.post("/recebimentos", json={
            "edicao_id": edicao.id, "descricao": "Doacao da padaria", "categoria": "doacao",
            "valor": "1000.00", "data": str(date.today()), "doador": "Padaria do Bairro",
            "forma": "Pix",
        })
        verifica("registra recebimento solto", r.status_code == 201, r.text[:130])
        doacao_id = r.json()["id"] if r.status_code == 201 else None
        verifica("guarda quem lancou", r.json().get("responsavel") == coord.nome,
                 str(r.json().get("responsavel")))
        verifica("nasce a conferir e sem comprovante",
                 r.json().get("conferido") is False
                 and r.json().get("comprovante_arquivo") is None, r.text[:130])

        cc.post("/recebimentos", json={
            "edicao_id": edicao.id, "descricao": "Patrocinio do buffet", "categoria": "outros",
            "valor": "500.00", "data": str(date.today()),
        })

        r = cc.post("/recebimentos", json={
            "edicao_id": edicao.id, "descricao": "Valor invalido", "categoria": "doacao",
            "valor": "0", "data": str(date.today()),
        })
        verifica("recusa recebimento de valor zero", r.status_code == 422, str(r.status_code))

        # A categoria e conjunto fechado: apadrinhamento nao se digita, vem do
        # que o pagamento quita.
        r = cc.post("/recebimentos", json={
            "edicao_id": edicao.id, "descricao": "Apadrinhamento na mao",
            "categoria": "apadrinhamento_cesta", "valor": "120.00", "data": str(date.today()),
        })
        verifica("recusa categoria de apadrinhamento digitada",
                 r.status_code == 422, str(r.status_code))

        r = cc.post("/recebimentos", json={
            "edicao_id": edicao.id, "descricao": "Sem categoria",
            "valor": "10.00", "data": str(date.today()),
        })
        verifica("categoria e obrigatoria", r.status_code == 422, str(r.status_code))

        r = ce.get("/recebimentos")
        verifica("estrutura NAO ve recebimentos", r.status_code == 403, str(r.status_code))

        # Tres pagamentos, um de cada forma: so cesta, so festa, e os dois no
        # mesmo pagamento.
        pagou = {}
        for nome, apadrinhamentos, valor in (
            ("cesta", [cesta_bruno.id], "120.00"),
            ("festa", [festa_bruno.id], "60.00"),
            ("misto", [cesta_carla.id, festa_carla.id], "180.00"),
        ):
            r = cc.post("/pagamentos", json={
                "padrinho_id": padrinho.id, "valor": valor, "data": str(date.today()),
                "forma": "Pix", "apadrinhamentos": apadrinhamentos,
                "observacoes": f"pagamento de {nome}",
            })
            pagou[nome] = r.json().get("id")
            verifica(f"registra o pagamento de {nome}", r.status_code == 201, r.text[:130])

        r = cc.get("/recebimentos", params={"edicao_id": edicao.id})
        dados = r.json()
        verifica("a lista junta as duas origens", dados["total"] == 5, str(dados["total"]))
        verifica("soma tudo o que entrou",
                 dados["total_recebido"] == "1860.00", dados["total_recebido"])
        verifica("conta quantos pagamentos de padrinho sao",
                 dados["pagamentos"] == 3, str(dados["pagamentos"]))
        verifica("separa o que veio do apadrinhamento",
                 dados["apadrinhamento"] == "360.00", dados["apadrinhamento"])
        verifica("a categoria do apadrinhamento vem do que ele quita",
                 dados["por_categoria"] == {
                     # O misto entra partido: 120 na cesta, 60 na festa.
                     "apadrinhamento_cesta": "240.00",
                     "apadrinhamento_festa": "120.00",
                     "doacao": "1000.00",
                     "outros": "500.00",
                 },
                 str(dados["por_categoria"]))
        verifica("tudo nasce a conferir", dados["a_conferir"] == "1860.00", dados["a_conferir"])
        verifica("e tudo nasce sem comprovante",
                 dados["sem_comprovante"] == 5, str(dados["sem_comprovante"]))

        linha_paga = next(
            (l for l in dados["itens"] if l["fonte"] == "pagamento" and l["id"] == pagou["misto"]),
            None,
        )
        verifica("o pagamento aparece como linha de recebimento", linha_paga is not None)
        if linha_paga:
            verifica("com o nome do padrinho", linha_paga["quem"] == padrinho.nome,
                     str(linha_paga["quem"]))
            verifica("cesta e festa sao duas etiquetas, e nao uma juntas",
                     linha_paga["categorias"] == ["apadrinhamento_cesta", "apadrinhamento_festa"],
                     str(linha_paga["categorias"]))
            verifica("e com o que ele quita escrito",
                     linha_paga["descricao"] == "1 cesta + 1 festa", linha_paga["descricao"])
            verifica("a observacao do pagamento chega na linha",
                     linha_paga["observacoes"] == "pagamento de misto",
                     str(linha_paga["observacoes"]))

        r = cc.get("/recebimentos", params={"edicao_id": edicao.id, "categoria": "doacao"})
        verifica("filtra por categoria", r.json()["total"] == 1, str(r.json()["total"]))
        r = cc.get("/recebimentos", params={"edicao_id": edicao.id, "categoria": "apadrinhamento_festa"})
        verifica("o filtro de festa traz tambem o pagamento misto",
                 r.json()["total"] == 2, str(r.json()["total"]))
        verifica("mas o total continua o da edicao inteira",
                 r.json()["total_recebido"] == "1860.00", r.json()["total_recebido"])

        cc.patch(f"/pagamentos/{pagou['cesta']}", json={"conferido": True})
        r = cc.patch(f"/recebimentos/{doacao_id}", json={"conferido": True})
        verifica("confere um recebimento solto",
                 r.status_code == 200 and r.json()["conferido"] is True, r.text[:130])

        r = cc.get("/recebimentos", params={"edicao_id": edicao.id})
        verifica("conferir desconta do que falta conferir",
                 r.json()["a_conferir"] == "740.00", r.json()["a_conferir"])
        r = cc.get("/recebimentos", params={"edicao_id": edicao.id, "conferido": "false"})
        verifica("e da para listar so o que falta conferir",
                 r.json()["total"] == 3, str(r.json()["total"]))

        # Comprovante de doacao: mesma maquina do comprovante de pagamento.
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000a49444154789c6300010000050001"
            "0d0a2db40000000049454e44ae426082"
        )
        r = cc.post(
            f"/recebimentos/{doacao_id}/comprovante",
            files={"arquivo": ("recibo.png", png, "image/png")},
        )
        verifica("sobe o comprovante de uma doacao", r.status_code == 200, r.text[:140])
        caminho = r.json().get("comprovante_arquivo") if r.status_code == 200 else None
        verifica("guardou o caminho do arquivo", bool(caminho), str(caminho))
        if caminho:
            verifica("o arquivo existe no disco",
                     (config.caminho_arquivos / caminho).is_file(), caminho)

        r = cc.get(f"/recebimentos/{doacao_id}/comprovante")
        verifica("baixa o comprovante da doacao de volta",
                 r.status_code == 200 and r.content == png, str(r.status_code))

        r = cc.post(
            f"/recebimentos/{doacao_id}/comprovante",
            files={"arquivo": ("recibo.txt", b"nao sou imagem", "text/plain")},
        )
        verifica("recusa comprovante que nao e imagem nem PDF",
                 r.status_code == 415, str(r.status_code))

        r = cc.get("/recebimentos", params={"edicao_id": edicao.id})
        verifica("o que falta comprovante acompanha",
                 r.json()["sem_comprovante"] == 4, str(r.json()["sem_comprovante"]))
        r = cc.get("/recebimentos", params={"edicao_id": edicao.id, "comprovante": "true"})
        verifica("e da para listar so o que ja tem comprovante",
                 r.json()["total"] == 1, str(r.json()["total"]))

        r = ce.post(
            f"/recebimentos/{doacao_id}/comprovante",
            files={"arquivo": ("recibo.png", png, "image/png")},
        )
        verifica("estrutura NAO sobe comprovante de recebimento",
                 r.status_code == 403, str(r.status_code))

        r = cc.delete(f"/recebimentos/{doacao_id}")
        verifica("apaga recebimento", r.status_code == 204, str(r.status_code))
        if caminho:
            verifica("e o comprovante sai do disco junto",
                     not (config.caminho_arquivos / caminho).is_file(), caminho)

        r = cc.get("/recebimentos", params={"edicao_id": edicao.id})
        verifica("o total acompanha a remocao",
                 r.json()["total_recebido"] == "860.00", r.json()["total_recebido"])

        r = ck.get("/recebimentos")
        verifica("comissario NAO ve recebimentos", r.status_code == 403, str(r.status_code))

        print("\nCheck-in")
        r = ck.post("/checkin", json={"codigo": "001", "edicao_id": edicao.id})
        verifica("comissario NAO faz check-in", r.status_code == 403, str(r.status_code))

        r = ce.post("/checkin", json={"codigo": "001", "edicao_id": edicao.id})
        verifica("estrutura NAO faz check-in", r.status_code == 403, str(r.status_code))

        r = cm.post("/checkin", json={"codigo": "001", "edicao_id": edicao.id})
        verifica("monitor faz check-in", r.status_code == 200, r.text[:130])
        entrada = r.json() if r.status_code == 200 else {}

        if entrada:
            verifica("identifica a crianca", entrada["nome"] == "Ana Clara")
            verifica("nao e repetido na primeira vez", entrada["ja_tinha_checkin"] is False)
            # O monitor nao capta nem monta kit: na porta ele nao recebe o
            # aviso de nenhum dos dois. Cada equipe so e avisada do proprio
            # assunto — a mesma regra das colunas da planilha.
            verifica("NAO avisa de padrinho a quem nao capta",
                     not any("padrinho" in a for a in entrada["avisos"]),
                     str(entrada["avisos"]))
            verifica("NAO avisa de kit a quem nao monta",
                     not any("kit" in a for a in entrada["avisos"]),
                     str(entrada["avisos"]))
            verifica("avisa sobre os cartoes que faltam",
                     any("cartoes" in a for a in entrada["avisos"]), str(entrada["avisos"]))
            verifica("nao avisa do dia, porque e hoje",
                     not any("dia dela" in a for a in entrada["avisos"]), str(entrada["avisos"]))

        r = cm.post("/checkin", json={"codigo": "001", "edicao_id": edicao.id})
        verifica("check-in repetido avisa, mas nao recusa",
                 r.status_code == 200 and r.json()["ja_tinha_checkin"] is True, str(r.status_code))

        r = cm.post("/checkin", json={"codigo": "002", "edicao_id": edicao.id})
        verifica("avisa quando o dia da crianca nao e hoje",
                 any("nao hoje" in a for a in r.json()["avisos"]), str(r.json()["avisos"]))

        r = cm.post("/checkin", json={"codigo": "003", "edicao_id": edicao.id})
        verifica("avisa quando a crianca nao esta marcada em nenhum dia",
                 any("nenhum dia" in a for a in r.json()["avisos"]), str(r.json()["avisos"]))

        # Quem capta continua sendo avisado: a restricao e por permissao, e nao
        # um aviso que foi desligado para todo mundo.
        r = cc.post("/checkin", json={"codigo": "001", "edicao_id": edicao.id})
        verifica("a coordenacao, que capta, E avisada do padrinho que falta",
                 any("padrinho" in a for a in r.json()["avisos"]), str(r.json()["avisos"]))

        r = cm.post("/checkin", json={"codigo": "999", "edicao_id": edicao.id})
        verifica("codigo inexistente devolve 404", r.status_code == 404, str(r.status_code))

        db.expire_all()
        verifica("o check-in ficou gravado na crianca", db.get(Crianca, ana.id).checkin_em is not None)

        print("\nQR code do cracha")
        r = cm.get(f"/checkin/qrcode/{ana.id}")
        verifica("gera o QR code", r.status_code == 200 and r.headers["content-type"] == "image/png",
                 str(r.status_code))
        verifica("o PNG tem conteudo", len(r.content) > 200, str(len(r.content)))

        print("\nLista de check-in do monitor")
        # Uma escola que NAO e do monitor, criada so agora para nao mexer nas
        # contas de kit la de cima.
        inst_b = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola B"); db.add(inst_b); db.flush()
        db.add(Crianca(edicao_id=edicao.id, instituicao_id=inst_b.id, dia_evento_id=hoje.id,
                       codigo="004", nome="Davi Rocha", idade=9, sexo="M"))
        db.commit()

        r = cm.get("/checkin/lista", params={"edicao_id": edicao.id})
        verifica("o monitor recebe a lista", r.status_code == 200, r.text[:130])
        lista = r.json() if r.status_code == 200 else []
        verifica("so com as criancas da instituicao dele",
                 [l["codigo"] for l in lista] == ["001", "002", "003"], str([l["codigo"] for l in lista]))
        ana_na_lista = next((l for l in lista if l["codigo"] == "001"), {})
        verifica("quem ja fez check-in vem marcado", ana_na_lista.get("checkin_em") is not None)
        verifica("e a linha nao fala de kit nem de padrinho",
                 not {"kit_status", "padrinhos"} & set(ana_na_lista), str(sorted(ana_na_lista)))

        r = cm.post("/checkin", json={"codigo": "004", "edicao_id": edicao.id})
        verifica("o monitor NAO confirma crianca de outra escola", r.status_code == 404, str(r.status_code))

        r = cc.get("/checkin/lista", params={"edicao_id": edicao.id})
        verifica("a coordenacao alcanca a edicao inteira", len(r.json()) == 4, str(len(r.json())))

        r = ck.get("/checkin/lista", params={"edicao_id": edicao.id})
        verifica("comissario NAO ve a lista de check-in", r.status_code == 403, str(r.status_code))

        print("\nCheck-in so no dia do evento")
        r = cm.get("/checkin/aberto", params={"edicao_id": edicao.id})
        verifica("hoje e dia do evento: o check-in esta aberto",
                 r.status_code == 200 and r.json()["aberto"] is True, r.text[:130])

        # Tira o "hoje" da edicao: sobram so os dias que ainda vao chegar.
        hoje.data = date.today() + timedelta(days=1)
        db.commit()

        r = cm.get("/checkin/aberto", params={"edicao_id": edicao.id})
        verifica("fora do dia do evento, fechado",
                 r.status_code == 200 and r.json()["aberto"] is False, r.text[:130])
        verifica("e conta quando ele abre",
                 len(r.json()["dias"]) == 2, str(r.json()["dias"]))
        r = cm.get("/checkin/lista", params={"edicao_id": edicao.id})
        verifica("a lista do monitor NAO abre", r.status_code == 403, str(r.status_code))
        r = cm.post("/checkin", json={"codigo": "002", "edicao_id": edicao.id})
        verifica("o monitor NAO confirma presenca", r.status_code == 403, str(r.status_code))
        # O Davi e o unico que ainda nao entrou: os outros tres ja passaram
        # pelo check-in la em cima.
        r = cc.post("/checkin", json={"codigo": "004", "edicao_id": edicao.id})
        verifica("nem a coordenacao, pelo codigo", r.status_code == 403, str(r.status_code))
        db.expire_all()
        davi = db.scalar(select(Crianca).where(Crianca.edicao_id == edicao.id, Crianca.codigo == "004"))
        verifica("e nada foi gravado", davi.checkin_em is None)

        r = ck.get("/checkin/aberto", params={"edicao_id": edicao.id})
        verifica("comissario NAO pergunta pelo check-in", r.status_code == 403, str(r.status_code))

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
