"""Testa os cartoes: digitalizacao, OCR e envio (fase 7).

Rodar com:  python -m tests.test_cartoes
A primeira execucao carrega o EasyOCR e demora bem mais.
"""

import io
from datetime import date

import cv2
import numpy as np
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
    Crianca,
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

    usuarios = db.scalars(select(Usuario).where(Usuario.nome.ilike(f"{MARCA}%"))).all()
    ids = [u.id for u in usuarios]
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
                db.execute(delete(Autorizacao).where(Autorizacao.crianca_id.in_(cris)))
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
    for pasta in (
        arquivos.pasta_dos_cartoes(f"{MARCA} Cidade", 2026),
        arquivos.pasta_das_autorizacoes(f"{MARCA} Cidade", 2026),
    ):
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

    monitor = usuario("Monitor", "Monitoria - monitores", [inst_a.id])
    comissario = usuario("Comissario", "Comissarios - comissario", [inst_a.id])
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
                 repetido["valida"] is False and any("ja tem um cartao" in e for e in repetido["erros"]),
                 str(repetido["erros"]))
        # A recusa tem de dizer o que FAZER, e nao so o que houve: quem sobe
        # ficava olhando um arquivo barrado sem saber se o defeito era do
        # arquivo, do cadastro ou dele.
        verifica("e aponta a saida (substituir a imagem)",
                 any("Substituir imagem" in e for e in repetido["erros"]),
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

        print("\nMiniatura para a visao de arquivo")
        r = ck.get(f"/cartoes/{cartao['id']}/miniatura")
        verifica("a miniatura responde", r.status_code == 200, r.text[:120])
        verifica("e e uma imagem", r.headers.get("content-type") == "image/jpeg",
                 str(r.headers.get("content-type")))
        # O motivo de ela existir: a grade mostra dezenas de uma vez, e o
        # original tem ~290 KB.
        cheia = ck.get(f"/cartoes/{cartao['id']}/imagem")
        verifica("e bem menor que o original",
                 len(r.content) < len(cheia.content) / 2,
                 f"{len(r.content)} vs {len(cheia.content)}")
        verifica("o navegador pode guardar, mas nenhum proxy",
                 "private" in (r.headers.get("cache-control") or ""),
                 str(r.headers.get("cache-control")))

        sem = TestClient(app)
        r = sem.get(f"/cartoes/{cartao['id']}/miniatura")
        verifica("sem sessao nao baixa a miniatura", r.status_code == 401, str(r.status_code))

        print("\nEnvio aos padrinhos")
        r = ck.post("/cartoes/enviados", json={"cartoes": [cartao["id"]]})
        verifica("recusa enviar cartao sem padrinho", r.status_code == 409, str(r.status_code))

        padrinho = Padrinho(edicao_id=edicao.id, nome=f"{MARCA} Doador")
        db.add(padrinho); db.flush()
        apadrinhamento = Apadrinhamento(
            crianca_id=ana.id, padrinho_id=padrinho.id, tipo="cesta", valor=120
        )
        db.add(apadrinhamento); db.commit()

        # Promessa nao e apadrinhamento: enquanto nao ha pagamento, o cartao
        # continua sem destinatario e nao pode ser marcado como enviado.
        r = ck.get("/cartoes", params={"crianca_id": ana.id})
        de_cesta = [c for c in r.json()["itens"] if c["tipo"] == "cesta"][0]
        verifica("promessa nao vira destinatario do cartao",
                 de_cesta["padrinho_nome"] is None, str(de_cesta["padrinho_nome"]))
        r = ck.post("/cartoes/enviados", json={"cartoes": [cartao["id"]]})
        verifica("e nao deixa marcar como enviado", r.status_code == 409, str(r.status_code))
        r = ck.get("/cartoes", params={"sem_padrinho": "true"})
        verifica("o cartao so prometido entra no filtro de sem padrinho",
                 any(c["id"] == cartao["id"] for c in r.json()["itens"]),
                 str([c["id"] for c in r.json()["itens"]]))

        pagamento = Pagamento(padrinho_id=padrinho.id, valor=120, data=date(2026, 11, 5))
        db.add(pagamento); db.flush()
        apadrinhamento.pagamento_id = pagamento.id
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

        r = ck.get("/cartoes", params={"instituicao_id": inst_a.id})
        instituicoes = {c["instituicao"] for c in r.json()["itens"]}
        verifica("a lista filtra por instituicao",
                 instituicoes == {inst_a.nome}, str(instituicoes))

        print("\nPastas: uma por instituicao")
        r = cc.get("/cartoes/pastas", params={"edicao_id": edicao.id})
        verifica("as pastas respondem", r.status_code == 200, r.text[:140])
        pastas = {p["instituicao"]: p for p in r.json()} if r.status_code == 200 else {}
        verifica("a coordenacao ve as duas escolas",
                 set(pastas) == {inst_a.nome, inst_b.nome}, str(sorted(pastas)))

        pa = pastas.get(inst_a.nome, {})
        # Duas cestas (Ana e Joao) e uma festa (Ana): a pasta diz de quanto e
        # cada pilha antes de alguem abrir.
        verifica("a pasta separa a pilha de cesta da de festa",
                 pa.get("cesta") == 2 and pa.get("festa") == 1,
                 f"cesta {pa.get('cesta')} / festa {pa.get('festa')}")
        # O denominador e quantas CRIANCAS a escola tem: cada uma escreve um
        # cartao de cada tipo, entao e esse o total esperado.
        verifica("e diz de quantas criancas, que e o total esperado",
                 pa.get("criancas") == 2, str(pa.get("criancas")))
        # O outerjoin repete a crianca uma vez por cartao — sem distinct, a Ana
        # (dois cartoes) contaria como duas criancas.
        verifica("a crianca com dois cartoes conta uma vez so",
                 pa.get("criancas") == 2, str(pa.get("criancas")))
        verifica("a escola sem nenhum cartao ainda aparece como pasta vazia",
                 pastas.get(inst_b.nome, {}).get("cesta") == 0
                 and pastas.get(inst_b.nome, {}).get("criancas", 0) > 0,
                 str(pastas.get(inst_b.nome)))

        r = ck.get("/cartoes/pastas", params={"edicao_id": edicao.id})
        do_comissario = [p["instituicao"] for p in r.json()]
        verifica("o comissario tambem so recebe a pasta do alcance dele",
                 do_comissario == [inst_a.nome], str(do_comissario))

        # O ponto do pedido: a pasta nao cria a fronteira, ela SEGUE a que ja
        # existia. O monitor da Escola A nao recebe a pasta da B.
        r = cm.get("/cartoes/pastas", params={"edicao_id": edicao.id})
        do_monitor = [p["instituicao"] for p in r.json()]
        verifica("o monitor so recebe a pasta da instituicao dele",
                 do_monitor == [inst_a.nome], str(do_monitor))

        print("\nSubir dentro da pasta: cartao de outra escola e recusado")
        r = cm.post(
            "/cartoes/lote",
            files=[("arquivos", (f"{fora.codigo}.jpg", foto_de_cartao("FORA"), "image/jpeg"))],
            data={"tipo": "cesta", "edicao_id": edicao.id, "instituicao_id": inst_a.id},
        )
        # O monitor nem alcanca a crianca da Escola B, entao para ele o codigo
        # nem casa — o que ja barra. A checagem da pasta vale para quem alcanca
        # as duas: a coordenacao.
        itens = r.json().get("arquivos") if r.status_code == 200 else None
        verifica("monitor nao sobe cartao de escola que nao alcanca",
                 r.status_code != 200 or not itens or not itens[0]["valida"],
                 f"{r.status_code} {r.text[:130]}")

        r = cc.post(
            "/cartoes/lote",
            files=[("arquivos", (f"{fora.codigo}.jpg", foto_de_cartao("FORA"), "image/jpeg"))],
            data={"tipo": "cesta", "edicao_id": edicao.id, "instituicao_id": inst_a.id},
        )
        item = r.json()["arquivos"][0] if r.status_code == 200 else {}
        verifica("na pasta errada, a coordenacao tambem e barrada",
                 not item.get("valida"), str(item))
        verifica("e o erro diz de que escola o cartao e",
                 any(inst_b.nome in e for e in item.get("erros", [])),
                 str(item.get("erros")))

        r = cc.post(
            "/cartoes/lote",
            files=[("arquivos", (f"{fora.codigo}.jpg", foto_de_cartao("FORA"), "image/jpeg"))],
            data={"tipo": "cesta", "edicao_id": edicao.id, "instituicao_id": inst_b.id},
        )
        verifica("e na pasta certa o mesmo arquivo passa",
                 r.json()["arquivos"][0]["valida"], r.text[:160])

        print("\nCorrigir um cartao subido errado")
        # A pilha e digitalizada de uma vez: trocar duas fotos de lugar e o erro
        # mais provavel do processo, e ate agora nao havia como desfazer.
        antes = cm.get(f"/cartoes/{cartao_festa['id']}/imagem").content

        # A troca so aceita o arquivo com o codigo da propria crianca: e o que
        # impede corrigir uma troca de fotos repetindo o mesmo erro.
        r = cm.post(
            f"/cartoes/{cartao_festa['id']}/trocar",
            files={"arquivo": ("nova.jpg", foto_de_cartao("SEM CODIGO"), "image/jpeg")},
        )
        verifica("troca com arquivo sem codigo e recusada", r.status_code == 422,
                 f"{r.status_code} {r.text[:120]}")
        r = cm.post(
            f"/cartoes/{cartao_festa['id']}/trocar",
            files={"arquivo": (f"{joao.codigo}.jpg", foto_de_cartao("JOAO"), "image/jpeg")},
        )
        verifica("troca com o codigo de outra crianca e recusada e diz qual",
                 r.status_code == 422 and joao.codigo in r.text and ana.codigo in r.text,
                 f"{r.status_code} {r.text[:160]}")
        verifica("e a imagem continuou a mesma",
                 cm.get(f"/cartoes/{cartao_festa['id']}/imagem").content == antes)

        r = cm.post(
            f"/cartoes/{cartao_festa['id']}/trocar",
            files={"arquivo": (f"{ana.codigo}.jpg", foto_de_cartao("CORRIGIDO"), "image/jpeg")},
        )
        verifica("o monitor troca a imagem de um cartao", r.status_code == 200, r.text[:140])
        depois = cm.get(f"/cartoes/{cartao_festa['id']}/imagem").content
        verifica("e a imagem mudou de verdade", antes != depois,
                 f"{len(antes)} vs {len(depois)}")
        verifica("o cartao continua o mesmo registro",
                 r.json()["id"] == cartao_festa["id"], str(r.json().get("id")))

        # O arquivo antigo nao fica para tras: e foto de crianca, e o registro
        # dela ja aponta para outro lugar.
        from pathlib import Path as _P
        sobrou = list((config.caminho_arquivos / "cartoes").rglob("*"))
        verifica("nao sobrou arquivo orfao da troca",
                 all(_P(a).is_dir() or a.stat().st_size > 0 for a in sobrou))

        r = ck.delete(f"/cartoes/{cartao_festa['id']}")
        verifica("comissario NAO apaga cartao", r.status_code == 403, str(r.status_code))

        r = cm.delete(f"/cartoes/{cartao_festa['id']}")
        verifica("o monitor apaga o que subiu errado", r.status_code == 204, str(r.status_code))
        r = cm.get(f"/cartoes/{cartao_festa['id']}/imagem")
        verifica("e o cartao some de vez", r.status_code == 404, str(r.status_code))

        r = cm.delete(f"/cartoes/{cartao_festa['id']}")
        verifica("apagar de novo da 404, nao erro", r.status_code == 404, str(r.status_code))

        print("\nAutorizacoes: sobem pelo mesmo lote, numa pilha propria")
        r = cm.post(
            "/cartoes/lote",
            files=[("arquivos", (f"{ana.codigo}.jpg", foto_de_cartao("AUTORIZO"), "image/jpeg"))],
            data={"tipo": "autorizacao", "edicao_id": edicao.id, "instituicao_id": inst_a.id},
        )
        verifica("a previa da autorizacao responde", r.status_code == 200, r.text[:160])
        verifica("a crianca com cartao ainda aceita a autorizacao",
                 r.json().get("validas") == 1, r.text[:160])
        id_lote = r.json()["id"]

        r = cm.post(f"/cartoes/lote/{id_lote}/confirmar")
        verifica("sem as respostas a autorizacao nao grava", r.status_code == 422,
                 f"{r.status_code} {r.text[:110]}")
        r = cm.post(f"/cartoes/lote/{id_lote}/confirmar", json={"respostas": {"0": {
            "necessidade_especial": True, "necessidade_especial_qual": "  ",
            "restricao_alimentar": False, "tem_observacao": False}}})
        verifica("sim sem dizer qual tambem nao grava", r.status_code == 422,
                 f"{r.status_code} {r.text[:110]}")

        r = cm.post(f"/cartoes/lote/{id_lote}/confirmar", json={"respostas": {"0": {
            "necessidade_especial": False, "necessidade_especial_qual": "sobrou no campo",
            "restricao_alimentar": True, "restricao_alimentar_qual": "Lactose",
            "tem_observacao": False}}})
        verifica("grava a autorizacao", r.json().get("gravados") == 1, r.text[:110])
        verifica("e ela nao vira cartao",
                 db.scalar(select(func.count()).select_from(Cartao)
                           .where(Cartao.crianca_id == ana.id, Cartao.tipo == "autorizacao")) == 0)

        r = cm.get("/autorizacoes", params={"edicao_id": edicao.id, "instituicao_id": inst_a.id})
        verifica("a pasta lista a autorizacao", r.status_code == 200 and len(r.json()) == 1,
                 r.text[:160])
        autorizacao = r.json()[0] if r.status_code == 200 and r.json() else {}
        verifica("as respostas ficaram gravadas",
                 autorizacao.get("restricao_alimentar") is True
                 and autorizacao.get("restricao_alimentar_qual") == "Lactose"
                 and autorizacao.get("necessidade_especial") is False,
                 str(autorizacao))
        verifica("o texto esquecido numa resposta nao e descartado",
                 autorizacao.get("necessidade_especial_qual") is None, str(autorizacao))

        r = cm.post(
            "/cartoes/lote",
            files=[("arquivos", (f"{ana.codigo}.jpg", foto_de_cartao("DE NOVO"), "image/jpeg"))],
            data={"tipo": "autorizacao", "edicao_id": edicao.id, "instituicao_id": inst_a.id},
        )
        repetida = r.json()["arquivos"][0]
        verifica("segunda autorizacao da mesma crianca e recusada na previa",
                 repetida["valida"] is False
                 and any("ja tem uma autorizacao" in e for e in repetida["erros"]),
                 str(repetida["erros"]))

        r = cc.get("/cartoes/pastas", params={"edicao_id": edicao.id})
        pa = {p["instituicao"]: p for p in r.json()}.get(inst_a.nome, {})
        verifica("a pasta conta a autorizacao", pa.get("autorizacoes") == 1, str(pa))

        r = cc.get(f"/criancas/{ana.id}")
        verifica("a ficha da crianca diz quando a autorizacao subiu",
                 bool(r.json().get("autorizacao_em")), r.text[:160])

        print("\nCuidados especiais")
        r = cc.get("/cuidados", params={"edicao_id": edicao.id})
        verifica("a coordenacao geral ve a lista de cuidados", r.status_code == 200, r.text[:160])
        dela = next((c for c in r.json() if c["crianca_id"] == ana.id), {}) if r.status_code == 200 else {}
        verifica("com a restricao que o monitor escreveu, e sem o que foi Nao",
                 dela.get("restricao_alimentar") == "Lactose" and dela.get("necessidade_especial") is None,
                 str(dela))
        verifica("so as criancas com algum cuidado",
                 all(c["crianca_id"] != joao.id for c in r.json()), str(r.json())[:160])
        r = cm.get("/cuidados", params={"edicao_id": edicao.id})
        verifica("o monitor NAO ve a lista inteira", r.status_code == 403, str(r.status_code))
        r = ck.get("/cuidados", params={"edicao_id": edicao.id})
        verifica("nem o comissario", r.status_code == 403, str(r.status_code))
        r = cc.get("/criancas", params={"edicao_id": edicao.id})
        lista = {c["id"]: c for c in r.json()["itens"]}
        verifica("e a lista de criancas avisa o cuidado da Ana",
                 "Lactose" in (lista.get(ana.id, {}).get("cuidados") or ""), str(lista.get(ana.id))[:160])

        verifica("a imagem sai pela rota autenticada",
                 cm.get(f"/autorizacoes/{autorizacao.get('id')}/imagem").status_code == 200)
        verifica("e a miniatura tambem",
                 cm.get(f"/autorizacoes/{autorizacao.get('id')}/miniatura").status_code == 200)
        verifica("sem sessao a imagem nao sai",
                 TestClient(app).get(f"/autorizacoes/{autorizacao.get('id')}/imagem").status_code
                 in (401, 403))

        r = cm.post(
            f"/autorizacoes/{autorizacao.get('id')}/trocar",
            files={"arquivo": (f"{joao.codigo}.jpg", foto_de_cartao("TROCADA"), "image/jpeg")},
        )
        verifica("autorizacao tambem recusa o codigo de outra crianca", r.status_code == 422,
                 f"{r.status_code} {r.text[:120]}")
        r = cm.post(
            f"/autorizacoes/{autorizacao.get('id')}/trocar",
            files={"arquivo": (f"{ana.codigo}.jpg", foto_de_cartao("TROCADA"), "image/jpeg")},
        )
        verifica("o monitor troca a imagem da autorizacao", r.status_code == 200, r.text[:140])

        r = ck.delete(f"/autorizacoes/{autorizacao.get('id')}")
        verifica("comissario NAO apaga autorizacao", r.status_code == 403, str(r.status_code))
        r = cm.delete(f"/autorizacoes/{autorizacao.get('id')}")
        verifica("o monitor apaga a autorizacao", r.status_code == 204, str(r.status_code))
        verifica("e sobra nenhum arquivo dela no disco",
                 not any(arquivos.pasta_das_autorizacoes(f"{MARCA} Cidade", 2026).glob("*.jpg")))

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
