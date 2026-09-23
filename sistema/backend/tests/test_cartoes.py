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
    fora = Crianca(edicao_id=edicao.id, instituicao_id=inst_b.id, codigo="002",
                   nome="Bruno Lima", idade=10, sexo="M")
    db.add_all([ana, fora]); db.flush()

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
    db.commit()

    try:
        cm = TestClient(app); entrar(cm, monitor.email)
        ck = TestClient(app); entrar(ck, comissario.email)

        print("\nDigitalizacao e OCR (a primeira vez carrega o EasyOCR)")
        foto = foto_de_cartao("ANA CLARA")
        r = cm.post(
            "/cartoes/analisar",
            files={"imagem": ("cartao.jpg", foto, "image/jpeg")},
            data={"codigo": "001", "edicao_id": str(edicao.id)},
        )
        verifica("analisa o cartao", r.status_code == 200, r.text[:160])
        analise = r.json() if r.status_code == 200 else {}

        if analise:
            verifica("acha a crianca pelo codigo", analise["crianca_nome"] == "Ana Clara Avila")
            verifica("corrige a perspectiva (sem aviso de bordas)", analise["aviso"] is None,
                     str(analise["aviso"]))
            verifica("le o nome escrito no cartao",
                     "ANA" in analise["nome_sugerido"].upper(), repr(analise["nome_sugerido"]))
            verifica("devolve a imagem para pre-visualizacao", len(analise["imagem_base64"]) > 1000)
            verifica("devolve os textos detectados", len(analise["textos"]) >= 1)

        print("\nFoto sem bordas detectaveis")
        r2 = cm.post(
            "/cartoes/analisar",
            files={"imagem": ("plano.jpg", foto_de_cartao("BRUNO", em_perspectiva=False), "image/jpeg")},
            data={"codigo": "001", "edicao_id": str(edicao.id)},
        )
        verifica("aceita foto sem bordas, com aviso",
                 r2.status_code == 200 and r2.json()["aviso"] == "bordas nao detectadas",
                 str(r2.json().get("aviso") if r2.status_code == 200 else r2.status_code))

        print("\nIsolamento")
        r = cm.post(
            "/cartoes/analisar",
            files={"imagem": ("cartao.jpg", foto, "image/jpeg")},
            data={"codigo": "002", "edicao_id": str(edicao.id)},
        )
        verifica("monitor nao digitaliza crianca de instituicao que nao e dele",
                 r.status_code == 404, str(r.status_code))

        r = ck.post(
            "/cartoes/analisar",
            files={"imagem": ("cartao.jpg", foto, "image/jpeg")},
            data={"codigo": "001", "edicao_id": str(edicao.id)},
        )
        verifica("comissario nao sobe cartao", r.status_code == 403, str(r.status_code))

        print("\nConfirmacao e nome do arquivo")
        r = cm.post("/cartoes/confirmar", json={
            "id": analise["id"], "crianca_id": ana.id, "tipo": "cesta",
            "texto_ocr": analise["nome_sugerido"],
        })
        verifica("confirma e grava o cartao", r.status_code == 201, r.text[:150])
        cartao = r.json() if r.status_code == 201 else {}

        if cartao:
            verifica("arquivo segue INSTITUICAO_NOME_TIPO.jpg",
                     cartao["arquivo"].endswith("ZZ_CAR_ESCOLA_A_ANA_CLARA_AVILA_CESTA.jpg"),
                     cartao["arquivo"])
            verifica("fica na pasta da cidade e do ano",
                     "cartoes/ZZ_CAR_CIDADE/2026/" in cartao["arquivo"].replace("\\", "/"),
                     cartao["arquivo"])
            verifica("nasce como digitalizado", cartao["status"] == "digitalizado")
            verifica("ainda nao tem padrinho", cartao["padrinho_id"] is None)

            caminho = arquivos.dentro_da_pasta(cartao["arquivo"])
            verifica("o arquivo existe no disco", caminho.is_file())

        r = cm.post("/cartoes/confirmar", json={
            "id": analise["id"], "crianca_id": ana.id, "tipo": "cesta",
        })
        verifica("a mesma analise nao serve duas vezes", r.status_code == 404, str(r.status_code))

        print("\nSegundo cartao do mesmo tipo")
        nova = cm.post(
            "/cartoes/analisar",
            files={"imagem": ("cartao.jpg", foto, "image/jpeg")},
            data={"codigo": "001", "edicao_id": str(edicao.id)},
        ).json()
        r = cm.post("/cartoes/confirmar", json={
            "id": nova["id"], "crianca_id": ana.id, "tipo": "cesta",
        })
        verifica("recusa dois cartoes de cesta para a mesma crianca", r.status_code == 409, str(r.status_code))

        r = cm.post("/cartoes/confirmar", json={
            "id": nova["id"], "crianca_id": ana.id, "tipo": "festa",
        })
        verifica("aceita o cartao de festa", r.status_code == 201, r.text[:120])
        cartao_festa = r.json() if r.status_code == 201 else {}

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
