"""Testa a autenticacao e a autorizacao (fase 2).

Cobre login e bloqueio, cookies da sessao, CSRF, tokens de uso unico e — o mais
importante — o isolamento de dados: quem alcanca quais criancas.

Rodar com:  python -m tests.test_autenticacao
Cria dados marcados com ZZ_AUTH e apaga tudo no fim.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import config
from app.database import SessionLocal
from app.main import app
from app.models import (
    Cidade,
    Crianca,
    DiaEvento,
    Edicao,
    Instituicao,
    LogAtividade,
    Perfil,
    TokenAcesso,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.models.tipos import TipoToken
from app.seguranca.contexto import montar_contexto
from app.seguranca.senhas import gerar_hash
from app.servicos import tokens_acesso

MARCA = "ZZ_AUTH"
SENHA = "senha-de-teste-123"

ok = 0
falhas: list[str] = []


def verifica(descricao: str, condicao: bool, extra: str = "") -> None:
    global ok
    if condicao:
        ok += 1
        print(f"  ok    {descricao}")
    else:
        falhas.append(descricao)
        print(f"  FALHA {descricao} {extra}")


def limpar(db, log_inicial: int = 0) -> None:
    """Apaga tudo que tenha a marca do teste, na ordem das dependencias.

    log_inicial: id do ultimo log antes do teste. Tudo acima dele foi criado
    aqui e sai junto — inclusive os registros sem usuario (tentativa de login
    com email inexistente), que nao dao para achar pela marca.
    """
    # Descarta o que tenha ficado pendente de um teste interrompido: senao a
    # limpeza tentaria gravar esses objetos e esbarraria nas chaves estrangeiras.
    db.rollback()

    # Sem "if log_inicial:" — com a tabela vazia ele vale 0, que e falso.
    db.execute(delete(LogAtividade).where(LogAtividade.id > log_inicial))
    usuarios = db.scalars(select(Usuario).where(Usuario.nome.like(f"{MARCA}%"))).all()
    ids = [u.id for u in usuarios]
    if ids:
        db.execute(delete(LogAtividade).where(LogAtividade.usuario_id.in_(ids)))
        db.execute(delete(TokenAcesso).where(TokenAcesso.usuario_id.in_(ids)))
    cidades = db.scalars(select(Cidade).where(Cidade.nome.like(f"{MARCA}%"))).all()
    cidade_ids = [c.id for c in cidades]
    if cidade_ids:
        edicoes = db.scalars(
            select(Edicao).where(Edicao.cidade_id.in_(cidade_ids))
        ).all()
        edicao_ids = [e.id for e in edicoes]
        if edicao_ids:
            db.execute(delete(Crianca).where(Crianca.edicao_id.in_(edicao_ids)))
            vinculos = db.scalars(
                select(UsuarioEdicao).where(UsuarioEdicao.edicao_id.in_(edicao_ids))
            ).all()
            if vinculos:
                db.execute(
                    delete(UsuarioInstituicao).where(
                        UsuarioInstituicao.usuario_edicao_id.in_([v.id for v in vinculos])
                    )
                )
                db.execute(
                    delete(UsuarioEdicao).where(UsuarioEdicao.edicao_id.in_(edicao_ids))
                )
            db.execute(delete(DiaEvento).where(DiaEvento.edicao_id.in_(edicao_ids)))
            db.execute(delete(Edicao).where(Edicao.id.in_(edicao_ids)))
        db.execute(delete(Instituicao).where(Instituicao.cidade_id.in_(cidade_ids)))
        db.execute(delete(Cidade).where(Cidade.id.in_(cidade_ids)))

    if ids:
        db.execute(delete(Usuario).where(Usuario.id.in_(ids)))
    db.commit()


def montar_cenario(db) -> dict:
    """Duas cidades, duas instituicoes por cidade, criancas e quatro usuarios."""
    fortaleza = Cidade(nome=f"{MARCA} Fortaleza", uf="CE")
    caucaia = Cidade(nome=f"{MARCA} Caucaia", uf="CE")
    db.add_all([fortaleza, caucaia])
    db.flush()

    ed_for = Edicao(
        cidade_id=fortaleza.id, ano=2026, nome=f"{MARCA} Fortaleza 2026",
        valor_cesta=120, valor_festa=60,
    )
    ed_cau = Edicao(
        cidade_id=caucaia.id, ano=2026, nome=f"{MARCA} Caucaia 2026",
        valor_cesta=120, valor_festa=60,
    )
    db.add_all([ed_for, ed_cau])
    db.flush()

    inst_a = Instituicao(cidade_id=fortaleza.id, nome=f"{MARCA} Escola A")
    inst_b = Instituicao(cidade_id=fortaleza.id, nome=f"{MARCA} Escola B")
    inst_c = Instituicao(cidade_id=caucaia.id, nome=f"{MARCA} Creche C")
    db.add_all([inst_a, inst_b, inst_c])
    db.flush()

    # 2 criancas por instituicao
    for inst, edicao in ((inst_a, ed_for), (inst_b, ed_for), (inst_c, ed_cau)):
        for n in (1, 2):
            db.add(Crianca(
                edicao_id=edicao.id, instituicao_id=inst.id,
                codigo=f"{inst.id}-{n}", nome=f"{MARCA} Crianca {inst.id}-{n}",
                idade=8, sexo="F",
            ))
    db.flush()

    perfis = {p.nome: p for p in db.scalars(select(Perfil)).all()}

    def criar_usuario(sufixo, admin=False, com_senha=True):
        u = Usuario(
            nome=f"{MARCA} {sufixo}",
            email=f"{MARCA.lower()}.{sufixo.lower()}@exemplo.org",
            senha_hash=gerar_hash(SENHA) if com_senha else None,
            admin_geral=admin,
        )
        db.add(u)
        db.flush()
        return u

    admin = criar_usuario("Admin", admin=True)
    coord = criar_usuario("Coord")
    comissario = criar_usuario("Comissario")
    monitor = criar_usuario("Monitor")
    novato = criar_usuario("Novato", com_senha=False)

    # Coordenacao alcanca a edicao inteira de Fortaleza.
    db.add(UsuarioEdicao(
        usuario_id=coord.id, edicao_id=ed_for.id, perfil_id=perfis["Coordenacao"].id
    ))
    # Comissario so responde pela Escola A.
    v_com = UsuarioEdicao(
        usuario_id=comissario.id, edicao_id=ed_for.id, perfil_id=perfis["Comissario"].id
    )
    db.add(v_com)
    # Monitor com vinculo, mas SEM instituicao atribuida ainda.
    db.add(UsuarioEdicao(
        usuario_id=monitor.id, edicao_id=ed_for.id, perfil_id=perfis["Monitor"].id
    ))
    db.flush()
    db.add(UsuarioInstituicao(usuario_edicao_id=v_com.id, instituicao_id=inst_a.id))
    db.commit()

    return {
        "admin": admin, "coord": coord, "comissario": comissario,
        "monitor": monitor, "novato": novato,
        "ed_for": ed_for, "ed_cau": ed_cau,
        "inst_a": inst_a, "inst_b": inst_b, "inst_c": inst_c,
    }


def entrar(cliente: TestClient, email: str, senha: str = SENHA):
    resposta = cliente.post("/auth/login", json={"email": email, "senha": senha})

    # Em producao a API vive em /acesso/api, entao o cookie com path=/acesso
    # e devolvido normalmente pelo navegador. No teste a app esta montada na
    # raiz, e o path nao casa — reescrevemos para "/" so para o cliente de
    # teste. O path real continua conferido nos cabecalhos Set-Cookie.
    if resposta.status_code == 200:
        for nome in (config.cookie_nome, config.cookie_csrf):
            valor = next(
                (ck.value for ck in cliente.cookies.jar if ck.name == nome), None
            )
            if valor:
                cliente.cookies.set(nome, valor, path="/")

    return resposta


def main() -> None:
    db = SessionLocal()
    log_inicial = db.scalar(select(func.max(LogAtividade.id))) or 0
    limpar(db)
    cenario = montar_cenario(db)

    try:
        print("\nLogin")
        c = TestClient(app)

        r = entrar(c, "nao-existe@exemplo.org")
        verifica("email inexistente e recusado", r.status_code == 401, str(r.status_code))
        msg_inexistente = r.json()["detail"]

        r = entrar(c, cenario["coord"].email, "senha-errada")
        verifica("senha errada e recusada", r.status_code == 401)
        verifica(
            "mensagem nao revela se o email existe",
            r.json()["detail"] == msg_inexistente,
        )

        r = entrar(c, cenario["novato"].email, "qualquer-senha")
        verifica("usuario sem senha definida nao entra", r.status_code == 401)

        # Mais 3 falhas fecham as 5 (ja houve 1 do coord acima).
        for _ in range(4):
            entrar(c, cenario["coord"].email, "senha-errada")
        r = entrar(c, cenario["coord"].email, SENHA)
        verifica(
            "bloqueia apos 5 tentativas falhas, mesmo com a senha certa",
            r.status_code == 429,
            str(r.status_code),
        )

        db.expire_all()
        coord = db.get(Usuario, cenario["coord"].id)
        verifica("bloqueado_ate foi gravado", coord.bloqueado_ate is not None)

        # Desbloqueia para os proximos testes.
        coord.bloqueado_ate = None
        coord.tentativas_falhas = 0
        db.commit()

        print("\nSessao e cookies")
        c = TestClient(app)
        r = entrar(c, cenario["coord"].email)
        verifica("login correto devolve 200", r.status_code == 200, r.text[:120])

        corpo = r.json()
        from app.seeds.perfis_permissoes import PERMISSOES

        verifica(
            "coordenacao recebe todas as permissoes",
            len(corpo["permissoes"]) == len(PERMISSOES),
            f'{len(corpo["permissoes"])} de {len(PERMISSOES)}',
        )
        verifica("resposta traz o vinculo com a edicao", len(corpo["vinculos"]) == 1)
        verifica(
            "vinculo mostra cidade, ano e perfil",
            corpo["vinculos"][0]["perfil"] == "Coordenacao"
            and corpo["vinculos"][0]["ano"] == 2026,
        )

        cookies = {ck.name: ck for ck in c.cookies.jar}
        sessao_ck = cookies.get(config.cookie_nome)
        csrf_ck = cookies.get(config.cookie_csrf)
        verifica("cookie da sessao foi gravado", sessao_ck is not None)
        verifica("cookie do csrf foi gravado", csrf_ck is not None)

        cabecalho_set = r.headers.get_list("set-cookie")
        sessao_raw = next(h for h in cabecalho_set if h.startswith(config.cookie_nome))
        csrf_raw = next(h for h in cabecalho_set if h.startswith(config.cookie_csrf))
        verifica("cookie da sessao e httpOnly", "httponly" in sessao_raw.lower())
        verifica("cookie do csrf NAO e httpOnly (o frontend le)", "httponly" not in csrf_raw.lower())
        verifica("cookie da sessao usa SameSite=Strict", "samesite=strict" in sessao_raw.lower())
        verifica("cookie da sessao usa path=/acesso", f"path={config.cookie_path}" in sessao_raw.lower())

        r = c.get("/auth/eu")
        verifica("GET /auth/eu com sessao devolve o usuario", r.status_code == 200)

        db.expire_all()
        verifica(
            "ultimo_login foi gravado",
            db.get(Usuario, cenario["coord"].id).ultimo_login is not None,
        )

        print("\nCSRF")
        csrf = csrf_ck.value
        r = c.post("/auth/logout")
        verifica("POST sem cabecalho CSRF e recusado", r.status_code == 403, str(r.status_code))

        r = c.post("/auth/logout", headers={"X-CSRF-Token": "valor-errado"})
        verifica("POST com CSRF errado e recusado", r.status_code == 403)

        r = c.get("/auth/eu")
        verifica("GET nao exige CSRF", r.status_code == 200)

        r = c.post("/auth/logout", headers={"X-CSRF-Token": csrf})
        verifica("POST com CSRF correto passa", r.status_code == 200, r.text[:120])

        apagados = " ".join(r.headers.get_list("set-cookie")).lower()
        verifica(
            "logout manda o navegador apagar o cookie da sessao",
            config.cookie_nome.lower() in apagados
            and ("max-age=0" in apagados or "expires=" in apagados),
        )
        verifica(
            "logout manda apagar tambem o cookie do csrf",
            config.cookie_csrf.lower() in apagados,
        )

        # O navegador apagaria o cookie com path=/acesso. Aqui limpamos o jar
        # inteiro, para tirar tambem a copia com path="/" que este teste criou.
        c.cookies.clear()
        r = c.get("/auth/eu")
        verifica("depois do logout a sessao acabou", r.status_code == 401)

        print("\nTokens de uso unico")
        novato = db.get(Usuario, cenario["novato"].id)
        token = tokens_acesso.gerar(db, novato, TipoToken.PRIMEIRO_ACESSO)
        db.commit()

        c2 = TestClient(app)
        r = c2.post("/auth/definir-senha", json={"token": token, "senha": "123"})
        verifica("recusa senha curta", r.status_code == 422, str(r.status_code))

        r = c2.post("/auth/definir-senha", json={"token": token, "senha": "12345678"})
        verifica("recusa senha so com numeros", r.status_code == 422)

        r = c2.post("/auth/definir-senha", json={"token": token, "senha": SENHA})
        verifica("define a senha com token valido", r.status_code == 200, r.text[:120])

        r = c2.post("/auth/definir-senha", json={"token": token, "senha": SENHA})
        verifica("o mesmo token nao serve duas vezes", r.status_code == 400)

        r = entrar(c2, novato.email)
        verifica("o usuario ja entra com a senha nova", r.status_code == 200)

        # Token expirado.
        expirado = tokens_acesso.gerar(db, novato, TipoToken.REDEFINIR_SENHA)
        db.flush()  # a sessao usa autoflush=False: sem isto o SELECT nao o acha
        registro = db.scalar(
            select(TokenAcesso)
            .where(TokenAcesso.usuario_id == novato.id, TokenAcesso.usado_em.is_(None))
        )
        registro.expira_em = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
        r = c2.post("/auth/definir-senha", json={"token": expirado, "senha": SENHA})
        verifica("token expirado e recusado", r.status_code == 400)

        c3 = TestClient(app)
        r = c3.post("/auth/esqueci-senha", json={"email": "ninguem@exemplo.org"})
        sem_conta = r.json()
        r = c3.post("/auth/esqueci-senha", json={"email": novato.email})
        com_conta = r.json()
        verifica(
            "esqueci-senha nao revela quem tem conta",
            sem_conta["mensagem"] == com_conta["mensagem"],
        )
        verifica("em desenvolvimento devolve o link", com_conta.get("link") is not None)

        print("\nIsolamento de dados (o mais importante)")
        db.expire_all()

        def criancas_visiveis(usuario_id: int) -> set[str]:
            ctx = montar_contexto(db, db.get(Usuario, usuario_id))
            achadas = db.scalars(select(Crianca).where(ctx.filtro_criancas())).all()
            return {f.nome for f in achadas if f.nome.startswith(MARCA)}

        todas = {f"{MARCA} Crianca {cenario['inst_a'].id}-1", f"{MARCA} Crianca {cenario['inst_a'].id}-2",
                 f"{MARCA} Crianca {cenario['inst_b'].id}-1", f"{MARCA} Crianca {cenario['inst_b'].id}-2",
                 f"{MARCA} Crianca {cenario['inst_c'].id}-1", f"{MARCA} Crianca {cenario['inst_c'].id}-2"}
        so_escola_a = {n for n in todas if f" {cenario['inst_a'].id}-" in n}
        fortaleza_toda = {n for n in todas if f" {cenario['inst_c'].id}-" not in n}

        verifica("admin_geral alcanca as criancas das duas cidades",
                 criancas_visiveis(cenario["admin"].id) == todas)
        verifica("coordenacao alcanca a edicao dela inteira, e nao a outra cidade",
                 criancas_visiveis(cenario["coord"].id) == fortaleza_toda)
        verifica("comissario so alcanca as criancas da instituicao atribuida",
                 criancas_visiveis(cenario["comissario"].id) == so_escola_a)
        verifica("monitor sem instituicao atribuida nao alcanca nenhuma crianca",
                 criancas_visiveis(cenario["monitor"].id) == set())

        print("\nPermissoes")
        ctx_com = montar_contexto(db, db.get(Usuario, cenario["comissario"].id))
        ctx_mon = montar_contexto(db, db.get(Usuario, cenario["monitor"].id))
        ctx_adm = montar_contexto(db, db.get(Usuario, cenario["admin"].id))

        verifica("comissario pode registrar pagamentos", ctx_com.pode("registrar_pagamentos"))
        verifica("comissario NAO pode subir cartoes", not ctx_com.pode("subir_cartoes"))
        verifica("comissario NAO pode gerenciar usuarios", not ctx_com.pode("gerenciar_usuarios"))
        verifica("monitor pode subir cartoes", ctx_mon.pode("subir_cartoes"))
        verifica("monitor NAO pode ver padrinhos", not ctx_mon.pode("ver_padrinhos"))
        verifica("admin_geral pode tudo", all(
            ctx_adm.pode(p) for p in ("gerenciar_usuarios", "subir_cartoes", "gerenciar_compras")
        ))
        verifica("admin_geral alcanca todas as edicoes", ctx_adm.alcanca_todas_edicoes)
        verifica("comissario nao alcanca a edicao da outra cidade",
                 not ctx_com.alcanca_edicao(cenario["ed_cau"].id, "ver_criancas"))
        verifica("comissario nao alcanca a instituicao que nao e dele",
                 not ctx_com.alcanca_instituicao(cenario["ed_for"].id, cenario["inst_b"].id))

        print("\nLog de atividades")
        logs = db.scalars(
            select(LogAtividade).where(
                LogAtividade.usuario_id == cenario["coord"].id
            )
        ).all()
        acoes = {l.acao for l in logs}
        verifica("login com sucesso foi registrado", "login" in acoes)
        verifica("login falhado foi registrado", "login_falhou" in acoes)
        verifica("bloqueio foi registrado", "conta_bloqueada" in acoes)
        verifica("logout foi registrado", "logout" in acoes)

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
