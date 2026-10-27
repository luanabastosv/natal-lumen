"""Testa a copia dos cartoes e das autorizacoes no Drive (servicos/espelho.py).

Sem rede: o Google e um MockTransport que anota cada pedido.

Rodar com:  python -m tests.test_espelho
"""

import json

import httpx2 as httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import delete, select

from app.config import config
from app.database import SessionLocal
from app.models import Autorizacao, Cartao, Cidade, Crianca, Edicao, Instituicao, LogAtividade
from app.servicos import arquivos, drive, espelho

MARCA = "ZZ_ESP"

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


def limpar(db) -> None:
    db.rollback()
    cids = list(db.scalars(select(Cidade.id).where(Cidade.nome.ilike(f"{MARCA}%"))).all())
    if cids:
        eds = list(db.scalars(select(Edicao.id).where(Edicao.cidade_id.in_(cids))).all())
        cris = list(db.scalars(select(Crianca.id).where(Crianca.edicao_id.in_(eds))).all())
        if cris:
            db.execute(delete(Cartao).where(Cartao.crianca_id.in_(cris)))
            db.execute(delete(Autorizacao).where(Autorizacao.crianca_id.in_(cris)))
            db.execute(delete(Crianca).where(Crianca.id.in_(cris)))
        db.execute(delete(Edicao).where(Edicao.id.in_(eds)))
        db.execute(delete(Instituicao).where(Instituicao.cidade_id.in_(cids)))
        db.execute(delete(Cidade).where(Cidade.id.in_(cids)))
    db.execute(delete(LogAtividade).where(LogAtividade.acao.like("%_drive_%"),
                                          LogAtividade.tabela.in_(["cartoes", "autorizacoes"]),
                                          LogAtividade.usuario_id.is_(None)))
    db.commit()
    for pasta in (arquivos.pasta_dos_cartoes(f"{MARCA} Cidade", 2026),
                  arquivos.pasta_das_autorizacoes(f"{MARCA} Cidade", 2026)):
        if pasta.is_dir():
            for f in pasta.glob("*.jpg"):
                f.unlink()


class Google:
    """Drive de mentira: guarda pastas e arquivos, e anota cada pedido."""

    def __init__(self) -> None:
        self.pastas: dict[str, tuple[str, str]] = {}  # id -> (pai, nome)
        self.arquivos: dict[str, dict] = {}            # id -> metadados
        self.lixeira: list[str] = []
        self.falhar_envio = False
        self.contador = 0

    def _id(self, prefixo: str) -> str:
        self.contador += 1
        return f"{prefixo}{self.contador}"

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "TOK", "expires_in": 3600})

        caminho = req.url.path
        if req.method == "GET" and caminho == "/drive/v3/files":
            q = req.url.params["q"]
            achados = [i for i, (pai, nome) in self.pastas.items()
                       if f"name = '{nome.replace(chr(39), chr(92) + chr(39))}'" in q
                       and f"'{pai}' in parents" in q]
            return httpx.Response(200, json={"files": [{"id": i} for i in achados]})
        if req.method == "POST" and caminho == "/drive/v3/files":
            corpo = json.loads(req.content)
            novo = self._id("PASTA")
            self.pastas[novo] = (corpo["parents"][0], corpo["name"])
            return httpx.Response(200, json={"id": novo})
        if req.method == "POST" and caminho == "/upload/drive/v3/files":
            if self.falhar_envio:
                return httpx.Response(500, json={})
            texto = req.content.decode("latin-1")
            meta = json.loads(texto[texto.index("{"):texto.index("}") + 1])
            novo = self._id("ARQ")
            self.arquivos[novo] = meta
            return httpx.Response(200, json={"id": novo, "webViewLink": ""})
        if req.method == "PATCH":
            self.lixeira.append(caminho.rsplit("/", 1)[-1])
            return httpx.Response(200, json={})
        return httpx.Response(400, json={})

    def caminho(self, pasta_id: str) -> list[str]:
        nomes = []
        while pasta_id in self.pastas:
            pai, nome = self.pastas[pasta_id]
            nomes.insert(0, nome)
            pasta_id = pai
        return nomes


def main() -> None:
    db = SessionLocal()
    limpar(db)

    cidade = Cidade(nome=f"{MARCA} Cidade", uf="CE"); db.add(cidade); db.flush()
    edicao = Edicao(cidade_id=cidade.id, ano=2026, nome=f"{MARCA} Natal 2026",
                    valor_cesta=120, valor_festa=60); db.add(edicao); db.flush()
    escola = Instituicao(cidade_id=cidade.id, nome="Escola D'Agua"); db.add(escola); db.flush()
    ana = Crianca(edicao_id=edicao.id, instituicao_id=escola.id, codigo="001",
                  nome="Ana Clara", idade=8, sexo="F")
    db.add(ana); db.flush()

    def imagem(tipo: str, pasta) -> str:
        pasta.mkdir(parents=True, exist_ok=True)
        destino = arquivos.caminho_disponivel(pasta, arquivos.nome_do_cartao(escola.nome, ana.nome, tipo))
        destino.write_bytes(b"\xff\xd8\xff jpeg de mentira")
        return str(destino.relative_to(config.caminho_arquivos))

    cesta = Cartao(crianca_id=ana.id, tipo="cesta",
                   arquivo=imagem("cesta", arquivos.pasta_dos_cartoes(cidade.nome, 2026)))
    festa = Cartao(crianca_id=ana.id, tipo="festa",
                   arquivo=imagem("festa", arquivos.pasta_dos_cartoes(cidade.nome, 2026)))
    autorizacao = Autorizacao(crianca_id=ana.id,
                              arquivo=imagem("autorizacao", arquivos.pasta_das_autorizacoes(cidade.nome, 2026)))
    db.add_all([cesta, festa, autorizacao]); db.commit()

    salvo = (config.drive_credenciais, config.drive_pasta_id, drive._cliente, espelho.PREFIXO_TESTE)
    try:
        print("\nSem Drive configurado")
        config.drive_credenciais = ""
        config.drive_pasta_id = ""
        espelho.em_segundo_plano(Cartao, [cesta.id])
        db.refresh(cesta)
        verifica("nada acontece, e o cartao segue sem copia", cesta.drive_id is None)

        chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()).decode()
        config.drive_credenciais = json.dumps({"client_email": "nl@x.iam.gserviceaccount.com",
                                               "private_key": pem})
        config.drive_pasta_id = "RAIZ"
        drive.esquecer_token()
        drive.esquecer_pastas()
        google = Google()
        drive._cliente = lambda: httpx.Client(transport=httpx.MockTransport(google))

        print("\nEdicao de teste (ZZ)")
        espelho.em_segundo_plano(Cartao, [cesta.id])
        db.refresh(cesta)
        verifica("edicao ZZ nunca vai para o Drive da equipe",
                 cesta.drive_id is None and not google.arquivos)

        # Daqui em diante, a edicao do teste conta como de verdade.
        espelho.PREFIXO_TESTE = "NENHUMA_EDICAO_COMECA_ASSIM"

        print("\nCartoes por instituicao e por tipo")
        espelho.em_segundo_plano(Cartao, [cesta.id, festa.id])
        db.refresh(cesta); db.refresh(festa)
        verifica("os dois cartoes ganham copia", bool(cesta.drive_id and festa.drive_id))
        pasta_cesta = google.arquivos[cesta.drive_id]["parents"][0]
        pasta_festa = google.arquivos[festa.drive_id]["parents"][0]
        verifica("cesta em Cartoes / instituicao / Cesta",
                 google.caminho(pasta_cesta) == [f"Cartões - {edicao.nome}", "Escola D'Agua", "Cesta"],
                 str(google.caminho(pasta_cesta)))
        verifica("festa em Cartoes / instituicao / Festa",
                 google.caminho(pasta_festa) == [f"Cartões - {edicao.nome}", "Escola D'Agua", "Festa"],
                 str(google.caminho(pasta_festa)))
        verifica("tudo dentro da pasta configurada",
                 google.pastas[list(google.pastas)[0]][0] == "RAIZ")
        verifica("o nome do arquivo e o mesmo do disco",
                 google.arquivos[cesta.drive_id]["name"] == cesta.arquivo.rsplit("/", 1)[-1],
                 google.arquivos[cesta.drive_id]["name"])
        verifica("a pasta da instituicao nao foi criada duas vezes",
                 sum(1 for _, n in google.pastas.values() if n == "Escola D'Agua") == 1)

        print("\nAutorizacoes por instituicao")
        espelho.em_segundo_plano(Autorizacao, [autorizacao.id])
        db.refresh(autorizacao)
        pasta_aut = google.arquivos[autorizacao.drive_id]["parents"][0]
        verifica("autorizacao em Autorizacoes / instituicao",
                 google.caminho(pasta_aut) == [f"Autorizações - {edicao.nome}", "Escola D'Agua"],
                 str(google.caminho(pasta_aut)))

        print("\nA pasta sobrevive a um reinicio do servidor")
        drive.esquecer_pastas()
        antes = len(google.pastas)
        espelho.em_segundo_plano(Cartao, [cesta.id])
        verifica("acha as pastas que ja existem em vez de criar outras", len(google.pastas) == antes)

        print("\nTroca de imagem")
        antigo = cesta.drive_id
        espelho.em_segundo_plano(Cartao, [cesta.id], [antigo])
        db.refresh(cesta)
        verifica("a nova ganha outra copia", cesta.drive_id not in (None, antigo))
        verifica("e a antiga vai para a lixeira", antigo in google.lixeira, str(google.lixeira))

        print("\nApagar")
        espelho.tirar_em_segundo_plano("autorizacoes", autorizacao.id, autorizacao.drive_id)
        verifica("a copia da autorizacao apagada vai para a lixeira",
                 autorizacao.drive_id in google.lixeira)

        print("\nGoogle falhando")
        google.falhar_envio = True
        festa.drive_id = None; db.commit()
        espelho.em_segundo_plano(Cartao, [festa.id])
        db.refresh(festa)
        verifica("o cartao continua de pe, sem copia", festa.drive_id is None)
        falhou = db.scalar(select(LogAtividade).where(
            LogAtividade.acao == "cartoes_drive_falhou", LogAtividade.registro_id == festa.id))
        verifica("e a falha fica no log", falhou is not None)
    finally:
        (config.drive_credenciais, config.drive_pasta_id, drive._cliente,
         espelho.PREFIXO_TESTE) = salvo
        drive.esquecer_token()
        drive.esquecer_pastas()
        limpar(db)
        db.close()

    print(f"\n{ok} verificacoes ok, {len(falhas)} falha(s)")
    if falhas:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
