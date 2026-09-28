"""Testa os cartoes: digitalizacao, OCR e envio (fase 7).

Rodar com:  python -m tests.test_cartoes
A primeira execucao carrega o EasyOCR e demora bem mais.
"""

import io

import cv2
import numpy as np
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
from app.servicos import arquivos

MARCA = "ZZ_CAR"
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
    # Previa de lote que o teste nao confirmou deixa pasta e JSON no temp.
    import shutil as _sh
    temp = config.caminho_arquivos / "cartoes_temp"
    if temp.is_dir():
        for c in temp.iterdir():
            if c.is_dir():
                _sh.rmtree(c, ignore_errors=True)
            elif c.suffix == ".json":
                c.unlink(missing_ok=True)

    db.rollback()
    db.execute(delete(LogAtividade).where(LogAtividade.id > log_inicial))

    usuarios = db.scalars(select(Usuario).where(Usuario.nome.like(f"{MARCA}%"))).all()
    ids = [u.id for u in usuarios]
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

    # Imagens deixadas pelo teste
    pasta = arquivos.pasta_dos_cartoes(f"{MARCA} Cidade", 2026)
    if pasta.is_dir():
        for arquivo in pasta.glob("*.jpg"):
            arquivo.unlink()


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


def foto_de_cartao(nome: str, em_perspectiva: bool = True) -> bytes:
    """Cria a foto de um cartao, opcionalmente torta sobre um fundo escuro."""
    cartao = np.full((400, 640, 3), 255, np.uint8)
    cv2.putText(cartao, f"Nome: {nome}", (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 4)
    cv2.putText(cartao, "Obrigado!", (30, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

    if not em_perspectiva:
        return cv2.imencode(".jpg", cartao)[1].tobytes()

    fundo = np.full((900, 1200, 3), 30, np.uint8)
    origem = np.float32([[0, 0], [640, 0], [640, 400], [0, 400]])
    destino = np.float32([[180, 140], [1020, 90], [1060, 720], [140, 660]])
    m = cv2.getPerspectiveTransform(origem, destino)
    composta = cv2.warpPerspective(cartao, m, (1200, 900), fundo.copy(), borderMode=cv2.BORDER_TRANSPARENT)
    return cv2.imencode(".jpg", composta)[1].tobytes()


def main() -> None:
    db = SessionLocal()
    log_inicial = db.scalar(select(func.max(LogAtividade.id))) or 0
    limpar(db)

    perfis = {p.nome: p for p in db.scalars(select(Perfil)).all()}

    cidade = Cidade(nome=f"{MARCA} Cidade", uf="CE"); db.add(cidade); db.flush()
    edicao = Edicao(cidade_id=cidade.id, ano=2026, nome=f"{MARCA} Edicao 2026",
                    valor_cesta=120, valor_festa=60); db.add(edicao); db.flush()
    inst_a = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola A")
    inst_b = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola B")
    db.add_all([inst_a, inst_b]); db.flush()

    ana = Crianca(edicao_id=edicao.id, instituicao_id=inst_a.id, codigo="001",
                  nome="Ana Clara Avila", idade=8, sexo="F")
    # Mesma instituicao da ana: serve para testar o lote com mais de um.
    joao = Crianca(edicao_id=edicao.id, instituicao_id=inst_a.id, codigo="EA10",
                   nome="Joao Miguel Souza", idade=9, sexo="M")
    fora = Crianca(edicao_id=edicao.id, instituicao_id=inst_b.id, codigo="002",
                   nome="Bruno Lima", idade=10, sexo="M")
    db.add_all([ana, joao, fora]); db.flush()

    def usuario(sufixo, perfil, instituicoes=()):
        u = Usuario(nome=f"{MARCA} {sufixo}", email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA))
        db.add(u); db.flush()
        v = UsuarioEdicao(usuario_id=u.id, edicao_id=edicao.id, perfil_id=perfis[perfil].id)
        db.add(v); db.flush()
        for i in instituicoes:
            db.add(UsuarioInstituicao(usuario_edicao_id=v.id, instituicao_id=i))
        return u

    monitor = usuario("Monitor", "Monitor", [inst_a.id])
    comissario = usuario("Comissario", "Comissario", [inst_a.id])
    # Sem instituicao atribuida: a coordenacao alcanca a edicao inteira.
    coord = usuario("Coord", "Coordenacao")
    # O comissario so alcanca as criancas atribuidas a ele. O monitor nao
    # precisa disto: ele continua com a instituicao inteira, que e o que o
    # trabalho dele exige.
    ana.comissario_id = comissario.id
    joao.comissario_id = comissario.id
    db.commit()

    try:
        cm = TestClient(app); entrar(cm, monitor.email)
        ck = TestClient(app); entrar(ck, comissario.email)

        print("\nLote: o codigo vem do NOME DO ARQUIVO")
        # A crianca e achada pelo codigo do arquivo, nao pelo nome escrito no
        # cartao — que e justamente o que o OCR errava.
        r = cm.post(
            "/cartoes/lote",
            files=[
                ("arquivos", (f"{ana.codigo}.jpg", foto_de_cartao("ANA CLARA"), "image/jpeg")),
                ("arquivos", (f"IMG_20261110_{joao.codigo}.jpg", foto_de_cartao("JOAO"), "image/jpeg")),
                ("arquivos", ("cartao_sem_codigo.jpg", foto_de_cartao("X"), "image/jpeg")),
                ("arquivos", ("ZZ999.jpg", foto_de_cartao("Y"), "image/jpeg")),
            ],
            data={"tipo": "cesta", "edicao_id": edicao.id},
        )
        verifica("a previa responde", r.status_code == 200, r.text[:160])
        previa = r.json() if r.status_code == 200 else {"arquivos": []}
        por_arquivo = {a["arquivo"]: a for a in previa.get("arquivos", [])}

        verifica("4 arquivos, 2 validos", previa.get("total") == 4 and previa.get("validas") == 2,
                 f"total={previa.get('total')} validas={previa.get('validas')}")
        verifica("nome limpo casa com a crianca",
                 por_arquivo.get(f"{ana.codigo}.jpg", {}).get("crianca_id") == ana.id)
        verifica("nome sujo do celular tambem casa",
                 por_arquivo.get(f"IMG_20261110_{joao.codigo}.jpg", {}).get("crianca_id") == joao.id)
        verifica("arquivo sem codigo vira erro, nao chute",
                 por_arquivo.get("cartao_sem_codigo.jpg", {}).get("valida") is False)
        verifica("codigo inexistente vira erro",
                 por_arquivo.get("ZZ999.jpg", {}).get("valida") is False)
        verifica("a previa traz miniatura para conferir",
                 bool(por_arquivo.get(f"{ana.codigo}.jpg", {}).get("miniatura")))
        meus = [ana.id, joao.id, fora.id]
        verifica("a previa NAO gravou nada ainda",
                 db.scalar(select(func.count()).select_from(Cartao)
                           .where(Cartao.crianca_id.in_(meus))) == 0)

        print("\nLote: confirmar grava so o que passou")
        r = cm.post(f"/cartoes/lote/{previa['id']}/confirmar")
        verifica("confirma o lote", r.status_code == 200, r.text[:140])
        verifica("gravou os 2 validos e ignorou os 2",
                 r.json().get("gravados") == 2 and r.json().get("ignorados") == 0,
                 r.text[:110])

        cartoes = db.scalars(
            select(Cartao).where(Cartao.crianca_id.in_(meus)).order_by(Cartao.id)
        ).all()
        verifica("dois cartoes na base", len(cartoes) == 2, str(len(cartoes)))
        cartao = cm.get("/cartoes", params={"edicao_id": edicao.id}).json()["itens"][0]
        verifica("o arquivo ficou com o nome da crianca, nao o do upload",
                 ana.nome.split()[0].upper() in cartao["arquivo"].upper()
                 or joao.nome.split()[0].upper() in cartao["arquivo"].upper(),
                 cartao["arquivo"])
        verifica("a pasta temporaria do lote foi apagada",
                 not (config.caminho_arquivos / "cartoes_temp" / previa["id"]).exists())

        print("\nLote: quem ja tem cartao do tipo e recusado na previa")
        r = cm.post(
            "/cartoes/lote",
            files=[("arquivos", (f"{ana.codigo}.jpg", foto_de_cartao("ANA"), "image/jpeg"))],
            data={"tipo": "cesta", "edicao_id": edicao.id},
        )
        repetido = r.json()["arquivos"][0]
        verifica("acusa cartao repetido antes de gravar",
                 repetido["valida"] is False and any("ja tem cartao" in e for e in repetido["erros"]),
                 str(repetido["erros"]))

        print("\nLote: o outro tipo passa")
        r = cm.post(
            "/cartoes/lote",
            files=[("arquivos", (f"{ana.codigo}.jpg", foto_de_cartao("ANA"), "image/jpeg"))],
            data={"tipo": "festa", "edicao_id": edicao.id},
        )
        verifica("mesma crianca aceita cartao de festa", r.json()["validas"] == 1, r.text[:120])
        r = cm.post(f"/cartoes/lote/{r.json()['id']}/confirmar")
        verifica("grava o de festa", r.json().get("gravados") == 1, r.text[:110])
        cartao_festa = [c for c in cm.get("/cartoes", params={"edicao_id": edicao.id}).json()["itens"]
                        if c["tipo"] == "festa"][0]

        print("\nLote: isolamento por instituicao")
        # O monitor so alcanca a Escola A. O codigo da crianca da Escola B nem
        # entra na lista procurada: para ele o arquivo nao casa com ninguem —
        # e nao "casa mas nega", que ja vazaria a existencia da crianca.
        r = cm.post(
            "/cartoes/lote",
            files=[("arquivos", (f"{fora.codigo}.jpg", foto_de_cartao("BRUNO"), "image/jpeg"))],
            data={"tipo": "cesta", "edicao_id": edicao.id},
        )
        item = r.json()["arquivos"][0]
        verifica("crianca de outra instituicao nao casa para o monitor",
                 item["valida"] is False and item["crianca_id"] is None, str(item)[:100])

        r = ck.post(
            "/cartoes/lote",
            files=[("arquivos", (f"{fora.codigo}.jpg", foto_de_cartao("BRUNO"), "image/jpeg"))],
            data={"tipo": "cesta", "edicao_id": edicao.id},
        )
        verifica("comissario nem sobe cartao: nao tem a permissao",
                 r.status_code == 403, str(r.status_code))

        cc = TestClient(app); entrar(cc, coord.email)
        r = cc.post(
            "/cartoes/lote",
            files=[("arquivos", (f"{fora.codigo}.jpg", foto_de_cartao("BRUNO"), "image/jpeg"))],
            data={"tipo": "cesta", "edicao_id": edicao.id},
        )
        verifica("a coordenacao, que alcanca as duas escolas, casa normalmente",
                 r.json()["arquivos"][0]["crianca_id"] == fora.id, r.text[:120])

        print("\nLote: codigo so numerico exige nome exato")
        r = cm.post(
            "/cartoes/lote",
            files=[("arquivos", (f"IMG_20261110_{ana.codigo}.jpg", foto_de_cartao("ANA"), "image/jpeg"))],
            data={"tipo": "festa", "edicao_id": edicao.id},
        )
        item = r.json()["arquivos"][0]
        verifica("nome sujo com codigo so numerico e recusado, nao adivinhado",
                 item["valida"] is False and item["crianca_id"] is None, str(item["erros"])[:90])

        cartao = [c for c in cm.get("/cartoes", params={"edicao_id": edicao.id}).json()["itens"]
                  if c["tipo"] == "cesta"][0]

        print("\nImagem so por rota autenticada")
        r = cm.get(f"/cartoes/{cartao['id']}/imagem")
        verifica("monitor baixa a imagem do cartao",
                 r.status_code == 200 and r.headers["content-type"] == "image/jpeg",
                 str(r.status_code))

        sem_sessao = TestClient(app)
        r = sem_sessao.get(f"/cartoes/{cartao['id']}/imagem")
        verifica("sem sessao nao baixa a imagem", r.status_code == 401, str(r.status_code))

        print("\nEnvio aos padrinhos")
        r = ck.post("/cartoes/enviados", json={"cartoes": [cartao["id"]]})
        verifica("recusa enviar cartao sem padrinho", r.status_code == 409, str(r.status_code))

        padrinho = Padrinho(edicao_id=edicao.id, nome=f"{MARCA} Doador")
        db.add(padrinho); db.flush()
        db.add(Apadrinhamento(crianca_id=ana.id, padrinho_id=padrinho.id, tipo="cesta", valor=120))
        db.commit()

        r = ck.get("/cartoes", params={"crianca_id": ana.id})
        de_cesta = [c for c in r.json()["itens"] if c["tipo"] == "cesta"][0]
        verifica("o destinatario aparece via crianca + tipo -> apadrinhamento",
                 de_cesta["padrinho_nome"] == f"{MARCA} Doador", str(de_cesta["padrinho_nome"]))

        r = ck.post("/cartoes/enviados", json={"cartoes": [cartao["id"]]})
        verifica("marca como enviado", r.status_code == 200 and r.json()[0]["status"] == "enviado",
                 r.text[:120])
        verifica("grava quando foi enviado", r.json()[0]["enviado_em"] is not None)

        r = cm.post("/cartoes/enviados", json={"cartoes": [cartao_festa["id"]]})
        verifica("monitor NAO marca como enviado", r.status_code == 403, str(r.status_code))

        print("\nListagens")
        r = ck.get("/cartoes", params={"situacao": "enviado"})
        verifica("filtra por enviados", r.json()["total"] == 1, str(r.json()["total"]))

        r = ck.get("/cartoes", params={"sem_padrinho": "true"})
        ids = [c["id"] for c in r.json()["itens"]]
        verifica("filtra os que ainda nao tem padrinho",
                 cartao_festa["id"] in ids and cartao["id"] not in ids, str(ids))

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
