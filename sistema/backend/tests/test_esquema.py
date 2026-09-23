"""Valida as restricoes do esquema com dados reais.

Cobre em especial as decisoes tomadas durante o desenho:
  - um padrinho pode apadrinhar varias criancas;
  - apadrinhamento entre cidades e permitido;
  - uma crianca tem no maximo um padrinho de cesta e um de festa.

Rodar com:  python -m tests.test_esquema
Cria tudo com nomes de teste e apaga no fim.
"""

from datetime import date

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import (
    Apadrinhamento,
    Cartao,
    Cidade,
    Crianca,
    DiaEvento,
    Edicao,
    Instituicao,
    Kit,
    Padrinho,
    Perfil,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)

MARCA = "ZZ_TESTE"
ok = 0
falhas: list[str] = []


def verifica(descricao: str, condicao: bool) -> None:
    global ok
    if condicao:
        ok += 1
        print(f"  ok   {descricao}")
    else:
        falhas.append(descricao)
        print(f"  FALHA {descricao}")


def espera_erro(db, descricao: str, acao) -> None:
    """Confirma que a base RECUSA a operacao.

    Usa SAVEPOINT (begin_nested) para desfazer so a operacao recusada: um
    rollback normal levaria embora tambem os dados de apoio do teste.
    """
    savepoint = db.begin_nested()
    try:
        acao()
        db.flush()
    except IntegrityError:
        savepoint.rollback()
        verifica(descricao, True)
        return
    savepoint.rollback()
    verifica(descricao, False)


def main() -> None:
    db = SessionLocal()
    try:
        # --- duas cidades, para testar o caso entre cidades ---
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

        dia = DiaEvento(edicao_id=ed_for.id, data=date(2026, 12, 20), descricao="Sabado")
        inst_for = Instituicao(cidade_id=fortaleza.id, nome=f"{MARCA} Escola A")
        inst_cau = Instituicao(cidade_id=caucaia.id, nome=f"{MARCA} Creche B")
        db.add_all([dia, inst_for, inst_cau])
        db.flush()

        ana = Crianca(
            edicao_id=ed_for.id, instituicao_id=inst_for.id, dia_evento_id=dia.id,
            codigo="001", nome="Ana Clara Avila", idade=8, sexo="F",
        )
        bruno = Crianca(
            edicao_id=ed_for.id, instituicao_id=inst_for.id,
            codigo="002", nome="Bruno Lima", idade=10, sexo="M",
        )
        # Crianca de OUTRA cidade, para o apadrinhamento cruzado.
        carla = Crianca(
            edicao_id=ed_cau.id, instituicao_id=inst_cau.id,
            codigo="001", nome="Carla Souza", idade=7, sexo="F",
        )
        db.add_all([ana, bruno, carla])
        db.flush()

        print("\nOperacao")
        verifica("primeiro_nome devolve so o primeiro nome", ana.primeiro_nome == "Ana")
        verifica(
            "codigo 001 repetido em outra edicao/instituicao e aceito",
            ana.codigo == carla.codigo and ana.id != carla.id,
        )

        # --- padrinho de Fortaleza ---
        padrinho = Padrinho(edicao_id=ed_for.id, nome=f"{MARCA} Jose Doador")
        db.add(padrinho)
        db.flush()

        print("\nApadrinhamento")
        db.add_all([
            Apadrinhamento(crianca_id=ana.id, padrinho_id=padrinho.id, tipo="cesta", valor=120),
            Apadrinhamento(crianca_id=ana.id, padrinho_id=padrinho.id, tipo="festa", valor=60),
        ])
        db.flush()
        verifica("crianca aceita um padrinho de cesta e um de festa", True)

        # O ponto levantado pela Luana: o mesmo padrinho em varias criancas.
        db.add(Apadrinhamento(crianca_id=bruno.id, padrinho_id=padrinho.id, tipo="cesta", valor=120))
        db.flush()
        verifica("o mesmo padrinho apadrinha uma segunda crianca", True)

        # Apadrinhamento entre cidades: padrinho de Fortaleza, crianca de Caucaia.
        db.add(Apadrinhamento(crianca_id=carla.id, padrinho_id=padrinho.id, tipo="festa", valor=60))
        db.flush()
        verifica("padrinho de Fortaleza apadrinha crianca de Caucaia", True)

        total = len([a for a in db.query(Apadrinhamento).filter_by(padrinho_id=padrinho.id)])
        verifica("padrinho acumula 4 apadrinhamentos", total == 4)

        espera_erro(
            db, "recusa dois padrinhos de cesta para a mesma crianca",
            lambda: db.add(
                Apadrinhamento(crianca_id=ana.id, padrinho_id=padrinho.id, tipo="cesta", valor=120)
            ),
        )
        espera_erro(
            db, "recusa tipo de apadrinhamento invalido",
            lambda: db.add(
                Apadrinhamento(crianca_id=bruno.id, padrinho_id=padrinho.id, tipo="brinquedo", valor=10)
            ),
        )

        print("\nRestricoes de dados")
        espera_erro(
            db, "recusa sexo fora de M/F",
            lambda: db.add(Crianca(
                edicao_id=ed_for.id, instituicao_id=inst_for.id,
                codigo="003", nome="X", idade=5, sexo="Z",
            )),
        )
        espera_erro(
            db, "recusa idade negativa",
            lambda: db.add(Crianca(
                edicao_id=ed_for.id, instituicao_id=inst_for.id,
                codigo="004", nome="Y", idade=-1, sexo="M",
            )),
        )
        espera_erro(
            db, "recusa codigo repetido na mesma edicao e instituicao",
            lambda: db.add(Crianca(
                edicao_id=ed_for.id, instituicao_id=inst_for.id,
                codigo="001", nome="Repetida", idade=9, sexo="F",
            )),
        )
        espera_erro(
            db, "recusa segunda edicao da mesma cidade no mesmo ano",
            lambda: db.add(Edicao(
                cidade_id=fortaleza.id, ano=2026, nome="Duplicada",
                valor_cesta=120, valor_festa=60,
            )),
        )

        print("\nCartoes e kits")
        db.add(Cartao(crianca_id=ana.id, tipo="cesta", arquivo="cartoes/x/2026/A.jpg"))
        db.flush()
        cartao = db.query(Cartao).filter_by(crianca_id=ana.id).one()
        verifica("cartao nasce com status digitalizado", cartao.status == "digitalizado")
        espera_erro(
            db, "recusa dois cartoes do mesmo tipo para a mesma crianca",
            lambda: db.add(Cartao(crianca_id=ana.id, tipo="cesta", arquivo="outro.jpg")),
        )

        db.add(Kit(crianca_id=ana.id))
        db.flush()
        verifica("kit nasce pendente", db.query(Kit).filter_by(crianca_id=ana.id).one().status == "pendente")
        espera_erro(
            db, "recusa dois kits para a mesma crianca",
            lambda: db.add(Kit(crianca_id=ana.id)),
        )

        print("\nAcesso")
        perfil_comissario = db.query(Perfil).filter_by(nome="Comissario").one()
        verifica("seed criou o perfil Comissario com 6 permissoes", len(perfil_comissario.permissoes) == 6)

        user = Usuario(nome=f"{MARCA} Maria", email=f"{MARCA.lower()}@exemplo.org")
        db.add(user)
        db.flush()
        verifica("usuario nasce sem senha (primeiro acesso pendente)", not user.tem_senha)

        vinculo = UsuarioEdicao(usuario_id=user.id, edicao_id=ed_for.id, perfil_id=perfil_comissario.id)
        db.add(vinculo)
        db.flush()
        db.add(UsuarioInstituicao(usuario_edicao_id=vinculo.id, instituicao_id=inst_for.id))
        db.flush()
        verifica("atribuicao de instituicao ligada ao vinculo de edicao", len(vinculo.instituicoes) == 1)

        espera_erro(
            db, "recusa dois vinculos do mesmo usuario na mesma edicao",
            lambda: db.add(UsuarioEdicao(
                usuario_id=user.id, edicao_id=ed_for.id, perfil_id=perfil_comissario.id
            )),
        )
        espera_erro(
            db, "recusa email de usuario repetido",
            lambda: db.add(Usuario(nome="Outra", email=f"{MARCA.lower()}@exemplo.org")),
        )

        # Remover o vinculo leva as atribuicoes de instituicao com ele.
        db.delete(vinculo)
        db.flush()
        restantes = db.query(UsuarioInstituicao).filter_by(usuario_edicao_id=vinculo.id).count()
        verifica("apagar o vinculo apaga as instituicoes atribuidas", restantes == 0)

        db.rollback()  # nada do teste fica gravado
    finally:
        db.close()

    print(f"\n{ok} verificacoes ok, {len(falhas)} falha(s)")
    if falhas:
        for f in falhas:
            print("  -", f)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
