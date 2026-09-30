"""Testa padrinhos, apadrinhamentos e pagamentos (fase 6).

Rodar com:  python -m tests.test_padrinhos
"""

import json
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    Apadrinhamento,
    Cidade,
    Crianca,
    Edicao,
    EnvioCartao,
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
from app.servicos import arquivos

MARCA = "ZZ_PAD"
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

    usuarios = db.scalars(select(Usuario).where(Usuario.nome.ilike(f"{MARCA}%"))).all()
    ids = [u.id for u in usuarios]
    if ids:
        db.execute(delete(LogAtividade).where(LogAtividade.usuario_id.in_(ids)))
        db.execute(delete(TokenAcesso).where(TokenAcesso.usuario_id.in_(ids)))

    cids = [c.id for c in db.scalars(select(Cidade).where(Cidade.nome.ilike(f"{MARCA}%"))).all()]
    if cids:
        eds = list(db.scalars(select(Edicao.id).where(Edicao.cidade_id.in_(cids))).all())
        if eds:
            pads = list(db.scalars(select(Padrinho.id).where(Padrinho.edicao_id.in_(eds))).all())
            cris = list(db.scalars(select(Crianca.id).where(Crianca.edicao_id.in_(eds))).all())
            if pads or cris:
                db.execute(delete(Apadrinhamento).where(
                    Apadrinhamento.padrinho_id.in_(pads or [0])
                    | Apadrinhamento.crianca_id.in_(cris or [0])
                ))
            if pads:
                db.execute(delete(Pagamento).where(Pagamento.padrinho_id.in_(pads)))
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

    # Duas cidades, para testar o apadrinhamento entre cidades.
    c1 = Cidade(nome=f"{MARCA} Fortaleza", uf="CE")
    c2 = Cidade(nome=f"{MARCA} Caucaia", uf="CE")
    db.add_all([c1, c2]); db.flush()
    e1 = Edicao(cidade_id=c1.id, ano=2026, nome=f"{MARCA} Fortaleza 2026", valor_cesta=120, valor_festa=60)
    e2 = Edicao(cidade_id=c2.id, ano=2026, nome=f"{MARCA} Caucaia 2026", valor_cesta=150, valor_festa=70)
    db.add_all([e1, e2]); db.flush()
    i1 = Instituicao(cidade_id=c1.id, nome=f"{MARCA} Escola A")
    i2 = Instituicao(cidade_id=c2.id, nome=f"{MARCA} Creche B")
    db.add_all([i1, i2]); db.flush()

    ana = Crianca(edicao_id=e1.id, instituicao_id=i1.id, codigo="001", nome="Ana Clara Avila", idade=8, sexo="F")
    bruno = Crianca(edicao_id=e1.id, instituicao_id=i1.id, codigo="002", nome="Bruno Lima", idade=10, sexo="M")
    carla = Crianca(edicao_id=e2.id, instituicao_id=i2.id, codigo="001", nome="Carla Souza", idade=7, sexo="F")
    # As duas ultimas sao da MESMA escola do comissario, e existem para provar
    # que a instituicao nao basta: uma e do colega, a outra nao tem responsavel.
    duda = Crianca(edicao_id=e1.id, instituicao_id=i1.id, codigo="003", nome="Duda Rocha", idade=9, sexo="F")
    elias = Crianca(edicao_id=e1.id, instituicao_id=i1.id, codigo="004", nome="Elias Pinto", idade=11, sexo="M")
    db.add_all([ana, bruno, carla, duda, elias]); db.flush()

    def usuario(sufixo, perfil, edicoes, instituicoes=()):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        for ed in edicoes:
            vinculo = UsuarioEdicao(usuario_id=u.id, edicao_id=ed, perfil_id=perfis[perfil].id)
            db.add(vinculo); db.flush()
            for inst in instituicoes:
                db.add(UsuarioInstituicao(usuario_edicao_id=vinculo.id, instituicao_id=inst))
        return u

    coord = usuario("Coord", "Coordenacao", [e1.id, e2.id])
    comissario = usuario("Comissario", "Comissario", [e1.id], [i1.id])
    # O colega do mesmo TIME da Escola A: alcanca a mesma instituicao, mas
    # outras criancas.
    colega = usuario("Colega", "Comissario", [e1.id], [i1.id])
    monitor = usuario("Monitor", "Monitor", [e1.id])
    db.flush()

    # Quem responde por quem. Sem isto o comissario nao alcanca crianca nenhuma:
    # a instituicao e a cerca de fora, a atribuicao e a lista de dentro.
    ana.comissario_id = comissario.id
    bruno.comissario_id = comissario.id
    carla.comissario_id = coord.id
    duda.comissario_id = colega.id
    # `elias` fica sem responsavel de proposito.
    db.commit()

    try:
        cc = TestClient(app); entrar(cc, coord.email)
        ck = TestClient(app); entrar(ck, comissario.email)
        cm = TestClient(app); entrar(cm, monitor.email)

        print("\nPadrinhos")
        r = ck.post("/padrinhos", json={"edicao_id": e1.id, "nome": "  Jose   Doador  ", "whatsapp": "85999990000"})
        verifica("comissario capta padrinho", r.status_code == 201, r.text[:130])
        jose = r.json() if r.status_code == 201 else {}
        verifica("espacos extras do nome sao limpos", jose.get("nome") == "Jose Doador", str(jose.get("nome")))

        r = cm.post("/padrinhos", json={"edicao_id": e1.id, "nome": "Nao Deveria"})
        verifica("monitor NAO capta padrinho", r.status_code == 403, str(r.status_code))

        print("\nAs duas perguntas da captacao")
        # Nulo nao e "nao": e "ninguem perguntou". Quem cadastra as vezes so tem
        # o nome e o zap na mao, e um `false` ali afirmaria que a pessoa NAO e
        # membro e NAO quer contribuir — duas coisas que ninguem apurou.
        verifica("quem nao foi perguntado fica nulo, e nao falso",
                 jose.get("membro_ser_feliz") is None
                 and jose.get("interesse_mensal") is None,
                 f"{jose.get('membro_ser_feliz')} / {jose.get('interesse_mensal')}")

        r = ck.post("/padrinhos", json={
            "edicao_id": e1.id, "nome": "Clara Perguntada",
            "membro_ser_feliz": True, "interesse_mensal": False,
        })
        clara = r.json() if r.status_code == 201 else {}
        verifica("e as respostas dadas no cadastro sao guardadas",
                 clara.get("membro_ser_feliz") is True
                 and clara.get("interesse_mensal") is False,
                 f"{clara.get('membro_ser_feliz')} / {clara.get('interesse_mensal')}")

        # A resposta quase nunca vem no cadastro: o doador diz "esse ano quero
        # contribuir todo mes" semanas depois, e a ficha tem de aceitar isso.
        r = ck.patch(f"/padrinhos/{jose['id']}", json={"interesse_mensal": True})
        verifica("responder depois, pela ficha, funciona",
                 r.status_code == 200 and r.json().get("interesse_mensal") is True,
                 r.text[:130])
        verifica("e nao contamina a outra pergunta",
                 r.json().get("membro_ser_feliz") is None,
                 str(r.json().get("membro_ser_feliz")))

        # Voltar para "nao perguntado" tem de ser possivel: quem marcou por
        # engano precisa poder desfazer, e nao so trocar sim por nao.
        r = ck.patch(f"/padrinhos/{jose['id']}", json={"interesse_mensal": None})
        verifica("da para voltar a nao perguntado",
                 r.status_code == 200 and r.json().get("interesse_mensal") is None,
                 r.text[:130])

        r = ck.post("/padrinhos", json={"edicao_id": e2.id, "nome": "Fora do alcance"})
        verifica("comissario nao capta padrinho na edicao de outra cidade", r.status_code == 403)

        print("\nApadrinhamentos")
        r = ck.post("/apadrinhamentos", json={"crianca_id": ana.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("liga padrinho a crianca", r.status_code == 201, r.text[:130])
        dados = r.json() if r.status_code == 201 else {}
        verifica("valor vem da edicao da crianca", dados["apadrinhamentos"][0]["valor"] == "120.00",
                 str(dados["apadrinhamentos"][0]["valor"]) if dados else "")
        verifica("padrinho recebe so o primeiro nome da crianca",
                 dados["apadrinhamentos"][0]["crianca_primeiro_nome"] == "Ana",
                 str(dados["apadrinhamentos"][0]["crianca_primeiro_nome"]) if dados else "")

        r = ck.post("/apadrinhamentos", json={"crianca_id": ana.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("recusa dois padrinhos de cesta para a mesma crianca", r.status_code == 409)

        r = ck.post("/apadrinhamentos", json={"crianca_id": ana.id, "padrinho_id": jose["id"], "tipo": "festa"})
        verifica("a mesma crianca aceita padrinho de festa", r.status_code == 201, r.text[:110])

        r = ck.post("/apadrinhamentos", json={"crianca_id": bruno.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("o mesmo padrinho apadrinha uma segunda crianca", r.status_code == 201, r.text[:110])

        r = ck.post("/apadrinhamentos", json={"crianca_id": carla.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("comissario de Fortaleza nao alcanca crianca de Caucaia", r.status_code == 403, str(r.status_code))

        # A lista dele, e nao a escola dele: as duas abaixo sao da Escola A, que
        # esta atribuida a ele, e as duas tem de ser recusadas.
        r = ck.post("/apadrinhamentos", json={"crianca_id": duda.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("comissario nao apadrinha crianca da lista do colega",
                 r.status_code == 403, str(r.status_code))
        verifica("e o erro diz de quem ela e", "Colega" in r.text, r.text[:160])

        r = ck.post("/apadrinhamentos", json={"crianca_id": elias.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("comissario nao apadrinha crianca sem responsavel",
                 r.status_code == 403, str(r.status_code))
        verifica("e o erro manda falar com a coordenacao",
                 "coordenacao" in r.text.lower(), r.text[:160])

        r = cc.post("/apadrinhamentos", json={"crianca_id": elias.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("a coordenacao apadrinha a crianca sem responsavel", r.status_code == 201, r.text[:140])
        if r.status_code == 201:
            de_elias = [a for a in r.json()["apadrinhamentos"] if a["crianca_id"] == elias.id][0]
            verifica("a etiqueta do apadrinhamento nomeia quem o registrou",
                     de_elias["comissario_id"] == coord.id and "Coord" in (de_elias["comissario"] or ""),
                     str(de_elias.get("comissario")))
            # Desfeito aqui para as contas abaixo continuarem sendo as de
            # sempre: este apadrinhamento so existiu para provar a regra.
            r = ck.delete(f"/apadrinhamentos/{de_elias['id']}")
            verifica("e o apadrinhamento de prova sai da ficha", r.status_code == 204, str(r.status_code))

        r = cc.post("/apadrinhamentos", json={"crianca_id": carla.id, "padrinho_id": jose["id"], "tipo": "cesta"})
        verifica("coordenacao das duas cidades faz o apadrinhamento cruzado", r.status_code == 201, r.text[:130])
        cruzado = r.json() if r.status_code == 201 else {}
        if cruzado:
            de_carla = [a for a in cruzado["apadrinhamentos"] if a["crianca_id"] == carla.id][0]
            verifica("no cruzado, o valor vem da edicao da crianca (150, nao 120)",
                     de_carla["valor"] == "150.00", str(de_carla["valor"]))
            verifica("padrinho acumula 4 apadrinhamentos", len(cruzado["apadrinhamentos"]) == 4,
                     str(len(cruzado["apadrinhamentos"])))
            verifica("total combinado soma certo (120+60+120+150)",
                     cruzado["total_combinado"] == "450.00", str(cruzado["total_combinado"]))

        # A ficha do padrinho tem de casar com a linha da planilha: sem o
        # codigo, nao da para dizer QUAL Ana Clara e esta.
        de_ana_na_ficha = cruzado["apadrinhamentos"][0]
        verifica("o apadrinhamento traz o codigo da crianca",
                 bool(de_ana_na_ficha.get("crianca_codigo")), str(de_ana_na_ficha.get("crianca_codigo")))
        verifica("e o nome completo, nao so o primeiro",
                 " " in (de_ana_na_ficha.get("crianca_nome") or ""), str(de_ana_na_ficha.get("crianca_nome")))
        verifica("o primeiro nome continua saindo, para o cartao",
                 de_ana_na_ficha.get("crianca_primeiro_nome", "").count(" ") == 0,
                 str(de_ana_na_ficha.get("crianca_primeiro_nome")))

        # O padrinho tem criancas de duas maos: as do comissario e a que a
        # coordenacao trouxe de Caucaia. Na ficha, cada linha diz de quem veio.
        de_carla_na_ficha = [a for a in cruzado["apadrinhamentos"] if a["crianca_id"] == carla.id][0]
        das_minhas = [a for a in cruzado["apadrinhamentos"] if a["crianca_id"] == ana.id][0]
        verifica("a crianca trazida pelo comissario tem a etiqueta dele",
                 das_minhas.get("comissario_id") == comissario.id, str(das_minhas.get("comissario")))
        verifica("e a trazida pela coordenacao tem a etiqueta dela",
                 de_carla_na_ficha.get("comissario_id") == coord.id,
                 str(de_carla_na_ficha.get("comissario")))

        print("\nPagamentos")
        ids_cesta = [a["id"] for a in cruzado["apadrinhamentos"] if a["tipo"] == "cesta"][:2]
        # O comissario registra o pagamento dos padrinhos dele — e o pagamento
        # que confirma o apadrinhamento, entao sem isto o trabalho dele so
        # entraria nos numeros quando a coordenacao passasse por ali.
        r = ck.get("/pagamentos")
        verifica("comissario VE os pagamentos dos padrinhos que alcanca",
                 r.status_code == 200, str(r.status_code))

        r = ck.post("/pagamentos", json={
            "padrinho_id": jose["id"], "valor": "120.00", "data": str(date(2026, 11, 9)),
            "forma": "pix", "apadrinhamentos": [],
        })
        verifica("e registra um pagamento", r.status_code == 201, r.text[:140])
        do_comissario = r.json() if r.status_code == 201 else {}

        # Mas a fronteira do caixa continua de pe: conferir e auditoria, apagar
        # desfaz dinheiro, e a aba Recebimentos e a edicao inteira.
        r = ck.patch(f"/pagamentos/{do_comissario.get('id')}", json={"conferido": True})
        verifica("comissario NAO confere o proprio pagamento",
                 r.status_code == 403, str(r.status_code))
        r = ck.patch(f"/pagamentos/{do_comissario.get('id')}", json={"forma": "dinheiro"})
        verifica("mas corrige os dados do que registrou",
                 r.status_code == 200, r.text[:140])
        r = ck.delete(f"/pagamentos/{do_comissario.get('id')}")
        verifica("comissario NAO apaga pagamento", r.status_code == 403, str(r.status_code))
        r = ck.get("/recebimentos", params={"edicao_id": e1.id})
        verifica("comissario NAO alcanca o financeiro da edicao",
                 r.status_code == 403, str(r.status_code))

        r = cc.delete(f"/pagamentos/{do_comissario.get('id')}")
        verifica("a coordenacao apaga o pagamento de teste",
                 r.status_code == 204, str(r.status_code))

        r = cc.post("/pagamentos", json={
            "padrinho_id": jose["id"], "valor": "240.00", "data": str(date(2026, 11, 10)),
            "forma": "pix", "apadrinhamentos": ids_cesta,
        })
        verifica("um pagamento quita varios apadrinhamentos", r.status_code == 201, r.text[:140])
        pagamento = r.json() if r.status_code == 201 else {}
        verifica("o pagamento guarda os apadrinhamentos que quitou",
                 len(pagamento.get("apadrinhamentos", [])) == 2, str(pagamento.get("apadrinhamentos")))

        r = ck.get(f"/padrinhos/{jose['id']}")
        verifica("total pago reflete os quitados", r.json()["total_pago"] == "240.00", r.json()["total_pago"])
        pagos = [a for a in r.json()["apadrinhamentos"] if a["pago"]]
        verifica("dois apadrinhamentos aparecem como pagos", len(pagos) == 2, str(len(pagos)))

        r = cc.post("/pagamentos", json={
            "padrinho_id": jose["id"], "valor": "60.00", "data": str(date(2026, 11, 11)),
            "apadrinhamentos": ids_cesta[:1],
        })
        verifica("recusa quitar duas vezes o mesmo apadrinhamento", r.status_code == 409, str(r.status_code))

        outro = ck.post("/padrinhos", json={"edicao_id": e1.id, "nome": "Outro Doador"}).json()
        r = cc.post("/pagamentos", json={
            "padrinho_id": outro["id"], "valor": "10.00", "data": str(date(2026, 11, 12)),
            "apadrinhamentos": ids_cesta[:1],
        })
        verifica("recusa pagamento com apadrinhamento de outro padrinho", r.status_code == 422, str(r.status_code))

        r = cc.patch(
            f"/pagamentos/{pagamento['id']}",
            json={"observacoes": "Pagou no balcao, comprovante fotografado."},
        )
        verifica("guarda a observacao do pagamento",
                 r.status_code == 200
                 and r.json()["observacoes"] == "Pagou no balcao, comprovante fotografado.",
                 r.text[:140])

        r = cc.patch(f"/pagamentos/{pagamento['id']}", json={"conferido": True})
        verifica("marca o pagamento como conferido", r.status_code == 200 and r.json()["conferido"], r.text[:110])

        r = cc.get("/pagamentos", params={"conferido": "true"})
        verifica("filtra pagamentos conferidos", r.json()["total"] == 1, str(r.json()["total"]))

        r = cc.get("/pagamentos", params={"comprovante": "false"})
        verifica("acha os pagamentos que ainda nao tem comprovante",
                 r.json()["total"] == 1, str(r.json()["total"]))
        r = cc.get("/pagamentos", params={"comprovante": "true"})
        verifica("e nao confunde com os que ja tem",
                 r.json()["total"] == 0, str(r.json()["total"]))

        print("\nComprovante")
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
            b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        r = cc.post(
            f"/pagamentos/{pagamento['id']}/comprovante",
            files={"arquivo": ("comprovante.png", png, "image/png")},
        )
        verifica("sobe o comprovante", r.status_code == 200, r.text[:140])
        caminho_1 = r.json().get("comprovante_arquivo") if r.status_code == 200 else None
        verifica("o pagamento passa a apontar para o arquivo", bool(caminho_1), str(caminho_1))

        r = cc.get(f"/pagamentos/{pagamento['id']}/comprovante")
        verifica("baixa o comprovante de volta",
                 r.status_code == 200 and r.content == png, str(r.status_code))

        r = cc.post(
            f"/pagamentos/{pagamento['id']}/comprovante",
            files={"arquivo": ("planilha.xlsx", b"nao sou imagem", "application/vnd.ms-excel")},
        )
        verifica("recusa comprovante que nao e imagem nem PDF", r.status_code == 415, str(r.status_code))

        # Trocar o comprovante nao pode deixar o anterior orfao no disco.
        antigo = arquivos.dentro_da_pasta(caminho_1) if caminho_1 else None
        r = cc.post(
            f"/pagamentos/{pagamento['id']}/comprovante",
            files={"arquivo": ("outro.pdf", b"%PDF-1.4 nada", "application/pdf")},
        )
        verifica("troca o comprovante", r.status_code == 200, r.text[:140])
        verifica("o comprovante trocado sai do disco",
                 antigo is not None and not antigo.exists(), str(antigo))

        r = cm.post(
            f"/pagamentos/{pagamento['id']}/comprovante",
            files={"arquivo": ("c.png", png, "image/png")},
        )
        verifica("monitor NAO sobe comprovante", r.status_code == 403, str(r.status_code))
        r = cm.get(f"/pagamentos/{pagamento['id']}/comprovante")
        verifica("monitor NAO baixa comprovante", r.status_code == 403, str(r.status_code))

        print("\nComprovante no Drive Compartilhado")
        import httpx2 as httpx
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        from app.config import config as cfg
        from app.servicos import drive

        # Desligado: o comprovante sobe do mesmo jeito, so sem link do Drive.
        cfg.drive_credenciais = ""
        cfg.drive_pasta_id = ""
        r = cc.post(
            f"/pagamentos/{pagamento['id']}/comprovante",
            files={"arquivo": ("c.png", png, "image/png")},
        )
        verifica("Drive desligado: o comprovante sobe assim mesmo", r.status_code == 200, r.text[:140])
        verifica("e nao ha link do Drive",
                 r.json().get("comprovante_drive_link") is None, str(r.json().get("comprovante_drive_link")))

        # Chave de verdade: o codigo assina RS256 e o teste exercita isso.
        chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = chave.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        cfg.drive_credenciais = json.dumps(
            {"client_email": "nl@projeto.iam.gserviceaccount.com", "private_key": pem}
        )
        cfg.drive_pasta_id = "PASTA_DO_EVENTO"
        drive.esquecer_token()

        vistos = {}

        def google_ok(req):
            if req.url.host == "oauth2.googleapis.com":
                return httpx.Response(200, json={"access_token": "TOK", "expires_in": 3600})
            vistos["params"] = dict(req.url.params)
            vistos["auth"] = req.headers.get("authorization")
            vistos["corpo"] = req.content
            return httpx.Response(
                200, json={"id": "DRIVE_1", "webViewLink": "https://drive.google.com/file/d/DRIVE_1"}
            )

        original = drive._cliente
        drive._cliente = lambda: httpx.Client(transport=httpx.MockTransport(google_ok))
        try:
            r = cc.post(
                f"/pagamentos/{pagamento['id']}/comprovante",
                files={"arquivo": ("c.png", png, "image/png")},
            )
            verifica("Drive ligado: sobe e devolve o link", r.status_code == 200, r.text[:140])
            verifica("o link do Drive volta na resposta",
                     r.json().get("comprovante_drive_link", "").endswith("DRIVE_1"),
                     str(r.json().get("comprovante_drive_link")))
            verifica("usou supportsAllDrives (senao nao enxerga Drive Compartilhado)",
                     vistos.get("params", {}).get("supportsAllDrives") == "true", str(vistos.get("params")))
            verifica("mandou o token no cabecalho", vistos.get("auth") == "Bearer TOK", str(vistos.get("auth")))
            verifica("gravou dentro da pasta configurada",
                     b"PASTA_DO_EVENTO" in vistos.get("corpo", b""), "pasta ausente no corpo")
            verifica("o nome do arquivo leva cidade e ano",
                     b"ZZ_PAD_FORTALEZA_2026" in vistos.get("corpo", b""), "nome sem cidade/ano")

            # Falha do Drive nao pode derrubar o comprovante.
            drive.esquecer_token()

            def google_sem_cota(req):
                if req.url.host == "oauth2.googleapis.com":
                    return httpx.Response(200, json={"access_token": "TOK", "expires_in": 3600})
                return httpx.Response(
                    403, json={"error": {"errors": [{"reason": "storageQuotaExceeded"}]}}
                )

            drive._cliente = lambda: httpx.Client(transport=httpx.MockTransport(google_sem_cota))
            r = cc.post(
                f"/pagamentos/{pagamento['id']}/comprovante",
                files={"arquivo": ("c.png", png, "image/png")},
            )
            verifica("Drive falhando: o comprovante AINDA sobe", r.status_code == 200, r.text[:140])
            verifica("e o link fica vazio",
                     r.json().get("comprovante_drive_link") is None, str(r.json().get("comprovante_drive_link")))
            verifica("o arquivo local continua la",
                     bool(r.json().get("comprovante_arquivo")), str(r.json().get("comprovante_arquivo")))

            caiu = db.scalar(
                select(LogAtividade).where(LogAtividade.acao == "comprovante_drive_falhou")
                .order_by(LogAtividade.id.desc())
            )
            verifica("a falha ficou registrada no log", caiu is not None)
            verifica("com a explicacao do Drive Compartilhado",
                     caiu is not None and "Drive Compartilhado" in (caiu.detalhes or {}).get("erro", ""),
                     str((caiu.detalhes or {}).get("erro") if caiu else None))
        finally:
            drive._cliente = original
            drive.esquecer_token()
            cfg.drive_credenciais = ""
            cfg.drive_pasta_id = ""

        print("\nRemocao")
        r = ck.delete(f"/apadrinhamentos/{ids_cesta[0]}")
        verifica("recusa apagar apadrinhamento ja pago", r.status_code == 409, str(r.status_code))

        r = cc.delete(f"/pagamentos/{pagamento['id']}")
        verifica("apaga o pagamento", r.status_code == 204, str(r.status_code))

        r = ck.get(f"/padrinhos/{jose['id']}")
        verifica("apagar o pagamento solta os apadrinhamentos", r.json()["total_pago"] == "0.00", r.json()["total_pago"])

        r = ck.delete(f"/apadrinhamentos/{ids_cesta[0]}")
        verifica("agora o apadrinhamento pode ser apagado", r.status_code == 204, str(r.status_code))

        print("\nVisibilidade do caso entre cidades")
        # Um comissario so de Caucaia deve enxergar o padrinho de Fortaleza que
        # apadrinhou uma crianca de Caucaia.
        so_caucaia = usuario("SoCaucaia", "Comissario", [e2.id])
        db.commit()
        cs = TestClient(app); entrar(cs, so_caucaia.email)

        r = cs.get("/padrinhos")
        nomes = [p["nome"] for p in r.json()["itens"]]
        verifica("comissario de Caucaia ve o padrinho de Fortaleza que apadrinhou crianca dele",
                 "Jose Doador" in nomes, str(nomes))
        verifica("mas nao ve o padrinho sem ligacao com a cidade dele",
                 "Outro Doador" not in nomes, str(nomes))

        print("\nCartao de agradecimento")
        # Relido agora: o bloco de remocao acima ja apagou o de cesta da Ana.
        vivos = ck.get(f"/padrinhos/{jose['id']}").json()["apadrinhamentos"]
        de_ana = [a for a in vivos if a["crianca_id"] == ana.id][0]

        # Promessa nao e apadrinhamento: o cartao AGRADECE, e nao ha o que
        # agradecer antes do dinheiro. Neste ponto o de_ana esta sem pagamento
        # (o bloco acima apagou o pagamento que o quitava).
        r = ck.get(f"/apadrinhamentos/{de_ana['id']}/agradecimento")
        verifica("promessa sem pagamento nao gera cartao", r.status_code == 409, str(r.status_code))
        verifica("e a recusa explica o que falta",
                 "pagamento" in r.text.lower(), r.text[:140])
        r = ck.post(f"/apadrinhamentos/{de_ana['id']}/agradecimento/enviar")
        verifica("nem envia pelo WhatsApp", r.status_code == 409, str(r.status_code))

        # Registrado o pagamento, o mesmo apadrinhamento passa a valer.
        r = cc.post("/pagamentos", json={
            "padrinho_id": jose["id"], "valor": "60.00", "data": str(date(2026, 11, 20)),
            "apadrinhamentos": [de_ana["id"]],
        })
        verifica("a coordenacao registra o pagamento da promessa",
                 r.status_code == 201, r.text[:140])

        r = ck.get(f"/apadrinhamentos/{de_ana['id']}/agradecimento")
        verifica("gera o cartao", r.status_code == 200, r.text[:110])
        verifica("responde PNG", r.headers.get("content-type") == "image/png",
                 str(r.headers.get("content-type")))
        disposicao = r.headers.get("content-disposition", "")
        verifica("baixa como anexo", "attachment" in disposicao, disposicao)
        verifica("arquivo e CODIGO_NOME_DA_CRIANCA.png",
                 f'filename="{ana.codigo}_ANA_CLARA_AVILA.png"' in disposicao, disposicao)
        verifica("nome do arquivo e ASCII puro, sem espaco",
                 disposicao.isascii() and " " not in disposicao.split('filename="')[-1],
                 disposicao)

        if r.status_code == 200:
            from io import BytesIO
            from PIL import Image
            img = Image.open(BytesIO(r.content))
            verifica("PNG abre e tem tamanho de arte", img.size[0] >= 800 and img.size[1] >= 800,
                     str(img.size))

        r = ck.get("/apadrinhamentos/99999999/agradecimento")
        verifica("apadrinhamento inexistente da 404", r.status_code == 404, str(r.status_code))

        # O cartao leva nome, codigo e instituicao: exige ver_criancas na
        # edicao DA CRIANCA, e nao so ver_padrinhos.
        r = cm.get(f"/apadrinhamentos/{de_ana['id']}/agradecimento")
        verifica("monitor (sem ver_padrinhos) nao baixa cartao",
                 r.status_code == 403, str(r.status_code))

        print("\nEnvio pelo WhatsApp (Cloud API)")
        import httpx2 as httpx
        from app.config import config as cfg
        from app.servicos import whatsapp as ws

        verifica("numero brasileiro ganha o 55",
                 ws.telefone_e164("(27) 99999-8888") == "5527999998888",
                 str(ws.telefone_e164("(27) 99999-8888")))
        verifica("numero que ja tem 55 passa intacto",
                 ws.telefone_e164("5527999998888") == "5527999998888")
        verifica("numero curto demais e recusado", ws.telefone_e164("99998888") is None)

        # Desligado: a rota avisa em vez de estourar.
        cfg.whatsapp_token = ""
        cfg.whatsapp_phone_number_id = ""
        r = ck.post(f"/apadrinhamentos/{de_ana['id']}/agradecimento/enviar")
        verifica("sem credenciais, responde 503 e explica", r.status_code == 503, r.text[:120])

        cfg.whatsapp_token = "TOKEN_DE_TESTE"
        cfg.whatsapp_phone_number_id = "999"

        # A Meta nunca e chamada de verdade: trocamos o transporte.
        chamadas = []

        def meta_ok(req):
            chamadas.append(req.url.path)
            if req.url.path.endswith("/media"):
                return httpx.Response(200, json={"id": "MEDIA_1"})
            return httpx.Response(200, json={"messages": [{"id": "wamid.TESTE"}]})

        original = ws._cliente
        ws._cliente = lambda: httpx.Client(transport=httpx.MockTransport(meta_ok))
        try:
            r = ck.post(f"/apadrinhamentos/{de_ana['id']}/agradecimento/enviar")
            verifica("envia o cartao", r.status_code == 200, r.text[:130])
            if r.status_code == 200:
                verifica("devolve o id da mensagem",
                         r.json()["mensagem_id"] == "wamid.TESTE", r.text[:110])
                verifica("status enviado", r.json()["status"] == "enviado")
            verifica("subiu a imagem antes de mandar o template",
                     len(chamadas) == 2 and chamadas[0].endswith("/media")
                     and chamadas[1].endswith("/messages"), str(chamadas))

            r = ck.get(f"/padrinhos/{jose['id']}")
            do_cartao = [a for a in r.json()["apadrinhamentos"] if a["id"] == de_ana["id"]][0]
            verifica("a tela passa a mostrar que o cartao foi enviado",
                     do_cartao["cartao_status"] == "enviado", str(do_cartao["cartao_status"]))
        finally:
            ws._cliente = original

        # Falha da Meta: o erro e traduzido e a tentativa fica gravada.
        def meta_falha(req):
            if req.url.path.endswith("/media"):
                return httpx.Response(200, json={"id": "MEDIA_2"})
            return httpx.Response(400, json={"error": {"code": 131026,
                                                       "message": "Receiver incapable"}})

        ws._cliente = lambda: httpx.Client(transport=httpx.MockTransport(meta_falha))
        try:
            r = ck.post(f"/apadrinhamentos/{de_ana['id']}/agradecimento/enviar")
            verifica("falha da Meta vira 502", r.status_code == 502, str(r.status_code))
            verifica("erro traduzido para portugues",
                     "nao tem WhatsApp" in r.json().get("detail", ""), r.text[:130])

            envios = db.scalars(
                select(EnvioCartao).where(EnvioCartao.apadrinhamento_id == de_ana["id"])
            ).all()
            verifica("as duas tentativas ficaram gravadas", len(envios) == 2, str(len(envios)))
            verifica("uma enviada e uma falhada",
                     sorted(e.status for e in envios) == ["enviado", "falhou"],
                     str([e.status for e in envios]))
        finally:
            ws._cliente = original
            cfg.whatsapp_token = ""
            cfg.whatsapp_phone_number_id = ""

        print("\nPermissoes")
        r = cm.get("/padrinhos")
        verifica("monitor NAO ve padrinhos", r.status_code == 403, str(r.status_code))
        r = cm.get("/pagamentos")
        verifica("monitor NAO ve pagamentos", r.status_code == 403, str(r.status_code))

        print("\nDesfazer engano de captacao (so a coordenacao)")
        # Um apadrinhamento pago, ligado por engano. Quem capta nao desfaz: o
        # dinheiro ja entrou, e isso deixou de ser correcao de digitacao.
        ids_agora = [a["id"] for a in ck.get(f"/padrinhos/{jose['id']}").json()["apadrinhamentos"]]
        alvo = ids_agora[0]
        r = cc.post("/pagamentos", json={
            "padrinho_id": jose["id"], "valor": "120.00", "data": str(date(2026, 11, 25)),
            "apadrinhamentos": [alvo],
        })
        verifica("pagamento registrado no apadrinhamento errado",
                 r.status_code == 201, r.text[:140])

        r = ck.delete(f"/apadrinhamentos/{alvo}")
        verifica("comissario NAO desfaz apadrinhamento pago",
                 r.status_code == 409, str(r.status_code))
        verifica("e a recusa manda procurar a coordenacao",
                 "coordenacao" in r.text.lower(), r.text[:140])

        antes = len(cc.get("/pagamentos", params={"padrinho_id": jose["id"]}).json()["itens"])
        r = cc.delete(f"/apadrinhamentos/{alvo}")
        verifica("a coordenacao desfaz", r.status_code == 204, str(r.status_code))

        # O PAGAMENTO fica: o dinheiro entrou de verdade, o que foi engano e a
        # crianca a que ele foi ligado. Apagar junto sumiria com uma entrada
        # real do caixa.
        depois = cc.get("/pagamentos", params={"padrinho_id": jose["id"]}).json()["itens"]
        verifica("e o pagamento continua no caixa", len(depois) == antes, f"{antes} -> {len(depois)}")
        verifica("so que sem destino", all(alvo not in p["apadrinhamentos"] for p in depois),
                 str([p["apadrinhamentos"] for p in depois]))

        print("\nApagar o cadastro do padrinho")
        r = ck.get(f"/padrinhos/{jose['id']}/dependencias")
        verifica("comissario NAO ve o que cai junto", r.status_code == 403, str(r.status_code))

        r = cc.get(f"/padrinhos/{jose['id']}/dependencias")
        verifica("a coordenacao ve a conta antes", r.status_code == 200, r.text[:140])
        conta = {i["chave"]: i["quantidade"] for i in r.json()["itens"]}
        verifica("e a conta inclui apadrinhamentos e pagamentos",
                 conta.get("apadrinhamentos", 0) > 0 and conta.get("pagamentos", 0) > 0,
                 str(conta))
        # A crianca NAO cai: ela volta a poder ser apadrinhada, que e o ponto.
        verifica("e NAO leva crianca nenhuma", conta.get("criancas", 0) == 0, str(conta))

        r = ck.delete(f"/padrinhos/{jose['id']}")
        verifica("comissario NAO apaga padrinho", r.status_code == 403, str(r.status_code))

        r = cc.delete(f"/padrinhos/{jose['id']}")
        verifica("a coordenacao apaga", r.status_code == 204, str(r.status_code))
        r = ck.get(f"/padrinhos/{jose['id']}")
        verifica("e o padrinho some", r.status_code == 404, str(r.status_code))

        # A crianca continua de pe e livre para ser apadrinhada de novo.
        db.expire_all()
        verifica("a crianca continua cadastrada", db.get(Crianca, ana.id) is not None)
        verifica("e sem apadrinhamento nenhum preso a ela",
                 db.scalar(select(func.count()).select_from(Apadrinhamento)
                           .where(Apadrinhamento.crianca_id == ana.id)) == 0)

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
