"""Estrelinha: o conector do Claude responde, nao ve credenciais e nao altera nada.

Precisa da usuaria `estrelinha` criada (docs/ESTRELINHA.md) e de
ESTRELINHA_DATABASE_URL e ESTRELINHA_TOKEN no .env.

Rodar com:  python -m tests.test_estrelinha
"""

import json
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import Apadrinhamento, Cidade, Crianca, DiaEvento, Edicao, Instituicao, Padrinho

MARCA = "ZZ_ESTRELA"
URL = "/estrelinha/mcp"

ok = 0
falhas: list[str] = []


def confere(d: str, c: bool, extra: str = "") -> None:
    global ok
    if c:
        ok += 1
        print(f"  ok     {d}")
    else:
        falhas.append(d)
        print(f"  FALHOU {d} {extra}")


def limpar(db) -> None:
    db.rollback()
    cids = list(db.scalars(select(Cidade.id).where(Cidade.nome.ilike(f"{MARCA}%"))).all())
    if cids:
        db.execute(delete(Edicao).where(Edicao.cidade_id.in_(cids)))
        db.execute(delete(Instituicao).where(Instituicao.cidade_id.in_(cids)))
        db.execute(delete(Cidade).where(Cidade.id.in_(cids)))
    db.commit()


def rpc(cliente, metodo, params=None, ident=1, token=None):
    corpo = {"jsonrpc": "2.0", "id": ident, "method": metodo, "params": params or {}}
    return cliente.post(f"{URL}?key={token or config.estrelinha_token}", json=corpo)


def ferramenta(cliente, nome, argumentos=None):
    r = rpc(cliente, "tools/call", {"name": nome, "arguments": argumentos or {}})
    resultado = r.json()["result"]
    return resultado["isError"], json.loads(resultado["content"][0]["text"])


def main() -> None:
    if not config.estrelinha_token or not config.estrelinha_database_url:
        raise SystemExit("Configure ESTRELINHA_TOKEN e ESTRELINHA_DATABASE_URL no .env")

    db = SessionLocal()
    limpar(db)
    cidade = Cidade(nome=f"{MARCA} Cidade", uf="CE")
    db.add(cidade)
    db.flush()
    edicao = Edicao(cidade_id=cidade.id, ano=2026, nome=f"{MARCA} 2026", valor_cesta=120, valor_festa=60)
    inst = Instituicao(cidade_id=cidade.id, nome=f"{MARCA} Escola")
    db.add_all([edicao, inst])
    db.flush()
    dia = DiaEvento(edicao_id=edicao.id, data=date(2026, 12, 5))
    db.add(dia)
    db.flush()
    criancas = [
        Crianca(edicao_id=edicao.id, instituicao_id=inst.id, dia_evento_id=dia.id,
                codigo=f"C{i}", nome=f"{MARCA} Nome Secreto {i}", idade=idade, sexo="F")
        for i, idade in enumerate([10, 10, 16])
    ]
    padrinho = Padrinho(edicao_id=edicao.id, nome=f"{MARCA} Padrinho", whatsapp="85999990000",
                        email="segredo@exemplo.com")
    db.add_all([*criancas, padrinho])
    db.flush()
    db.add(Apadrinhamento(crianca_id=criancas[0].id, padrinho_id=padrinho.id, tipo="cesta", valor=120))
    db.commit()
    ed = edicao.id

    cliente = TestClient(app)
    try:
        print("Acesso")
        confere("sem token: 401", cliente.post(URL, json={}).status_code == 401)
        confere("token errado: 401", rpc(cliente, "ping", token="errado").status_code == 401)
        confere("GET (stream) responde 405", cliente.get(f"{URL}?key={config.estrelinha_token}").status_code == 405)

        print("Protocolo MCP")
        r = rpc(cliente, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                        "clientInfo": {"name": "teste", "version": "1"}})
        ini = r.json()["result"]
        confere("initialize devolve a versao e as instrucoes",
                ini["protocolVersion"] == "2025-06-18" and "Estrelinha" in ini["instructions"])
        notif = cliente.post(f"{URL}?key={config.estrelinha_token}",
                             json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        confere("notificacao recebe 202 sem corpo", notif.status_code == 202)
        nomes = [t["name"] for t in rpc(cliente, "tools/list").json()["result"]["tools"]]
        confere("tools/list tem ver_estrutura e consultar", nomes == ["ver_estrutura", "consultar"])

        print("Respostas")
        erro, estrutura = ferramenta(cliente, "ver_estrutura")
        colunas = {(l["view"], l["coluna"]) for l in estrutura}
        confere("ver_estrutura lista as views", not erro and ("criancas", "idade") in colunas)
        confere("nome da crianca aparece", ("criancas", "nome") in colunas)
        confere("contato do padrinho aparece", ("padrinhos", "whatsapp") in colunas)
        confere("hash da senha nao aparece", ("usuarios", "senha_hash") not in colunas)
        confere("tokens de acesso nao aparecem",
                not any(v in ("tokens_acesso", "sessoes_revogadas") for v, _ in colunas))

        erro, linhas = ferramenta(cliente, "consultar", {"sql":
            f"select count(*) as n from criancas where edicao_id = {ed} and idade = 10"})
        confere("conta criancas de 10 anos", not erro and linhas == [{"n": 2}], str(linhas))
        erro, linhas = ferramenta(cliente, "consultar", {"sql": f"""
            select count(distinct a.padrinho_id) as n from apadrinhamentos a
            join criancas c on c.id = a.crianca_id where c.edicao_id = {ed} and c.idade = 10"""})
        confere("padrinhos de criancas de 10 anos", not erro and linhas == [{"n": 1}], str(linhas))
        erro, linhas = ferramenta(cliente, "consultar", {"sql": f"""
            select count(*) as n from apadrinhamentos a join criancas c on c.id = a.crianca_id
            where c.edicao_id = {ed}
              and (a.criado_em at time zone 'America/Fortaleza')::date
                  <= (now() at time zone 'America/Fortaleza')::date
              and c.codigo like 'C%';"""})
        confere("aceita ::date, %, fuso e ; no fim", not erro and linhas == [{"n": 1}], str(linhas))

        print("Ataques")
        for d, sql in [
            ("ler tabela real de usuarios", "select * from public.usuarios"),
            ("ler o hash da senha na tabela real", "select senha_hash from public.usuarios"),
            ("ler tokens de acesso", "select * from public.tokens_acesso"),
            ("insert", "insert into estrelinha.cidades (nome, uf) values ('x', 'CE')"),
            ("duas consultas", "select 1; delete from public.criancas"),
            ("delete escondido num WITH",
             "with x as (delete from public.criancas returning id) select * from x"),
            ("mudar para leitura e escrita", "select set_config('transaction_read_only', 'off', true)"),
            ("consulta lenta", "select pg_sleep(30)"),
        ]:
            erro, _ = ferramenta(cliente, "consultar", {"sql": sql})
            confere(f"barrado: {d}", erro)
        db.expire_all()
        restantes = db.scalars(select(Crianca).where(Crianca.edicao_id == ed)).all()
        confere("nenhuma crianca foi apagada", len(restantes) == 3)
    finally:
        limpar(db)
        db.close()

    print(f"\n{ok} verificacoes ok, {len(falhas)} falha(s)")
    if falhas:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
