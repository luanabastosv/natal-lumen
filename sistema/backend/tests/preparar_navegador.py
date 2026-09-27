"""Prepara dados isolados para o teste de navegador.

O teste passa pela interface e edita registros de verdade. Rodar isso contra os
dados reais ja corrompeu nomes uma vez — por isso ele ganha a propria cidade,
edicao, instituicao e conta, todas com o prefixo ZZ, que a limpeza remove.

Rodar com:  python -m tests.preparar_navegador
"""

from datetime import date

from sqlalchemy import select

from app.config import config
from app.database import SessionLocal
from app.models import (
    Cidade,
    Crianca,
    DiaEvento,
    Edicao,
    Instituicao,
    Perfil,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.seguranca.senhas import gerar_hash

EMAIL = "zz_nav.admin@exemplo.org"
SENHA = "senha-de-teste-123"

NOMES = [
    "Ana Clara Souza", "Pedro Henrique Lima", "Maria Eduarda Santos",
    "Lucas Oliveira", "Beatriz Costa", "Gabriel Ferreira",
    "Sofia Almeida", "Miguel Rodrigues",
]


def main() -> None:
    if config.em_producao:
        print("Recusado: AMBIENTE=producao.")
        raise SystemExit(1)

    db = SessionLocal()
    try:
        perfis = {p.nome: p for p in db.scalars(select(Perfil)).all()}

        u = db.scalar(select(Usuario).where(Usuario.email == EMAIL))
        if u is None:
            u = Usuario(nome="ZZ_NAV Admin", email=EMAIL, admin_geral=True)
            db.add(u)
        u.senha_hash = gerar_hash(SENHA)
        u.ativo, u.bloqueado_ate, u.tentativas_falhas = True, None, 0
        db.flush()

        cidade = Cidade(nome="ZZ_NAV Cidade", uf="CE")
        db.add(cidade); db.flush()
        edicao = Edicao(cidade_id=cidade.id, ano=2026, nome="ZZ_NAV Edicao 2026",
                        valor_cesta=120, valor_festa=60)
        db.add(edicao); db.flush()
        db.add_all([
            DiaEvento(edicao_id=edicao.id, data=date(2026, 12, 20), descricao="Sabado"),
            DiaEvento(edicao_id=edicao.id, data=date(2026, 12, 21), descricao="Domingo"),
        ])
        inst_a = Instituicao(cidade_id=cidade.id, nome="ZZ_NAV Escola A")
        inst_b = Instituicao(cidade_id=cidade.id, nome="ZZ_NAV Creche B")
        db.add_all([inst_a, inst_b]); db.flush()

        criancas = []
        for i, nome in enumerate(NOMES):
            inst = inst_a if i < 5 else inst_b
            crianca = Crianca(
                edicao_id=edicao.id, instituicao_id=inst.id,
                codigo=f"NAV{i:02d}", nome=f"ZZ {nome}",
                idade=4 + (i % 5), sexo="F" if i % 2 == 0 else "M",
            )
            criancas.append(crianca)
            db.add(crianca)

        db.add(UsuarioEdicao(usuario_id=u.id, edicao_id=edicao.id,
                             perfil_id=perfis["Coordenacao"].id))

        # Um TIME de duas comissarias na Escola A: e o caso que a coluna do
        # responsavel existe para resolver. A terceira atende a Creche B, para
        # o seletor de uma escola nao oferecer quem nao atende a outra.
        db.flush()
        for sufixo, instituicoes in (
            ("Bia", [inst_a.id]),
            ("Carla", [inst_a.id]),
            ("Davi", [inst_b.id]),
        ):
            com = db.scalar(
                select(Usuario).where(Usuario.email == f"zz_nav.{sufixo.lower()}@exemplo.org")
            )
            if com is None:
                com = Usuario(
                    nome=f"ZZ_NAV {sufixo}",
                    email=f"zz_nav.{sufixo.lower()}@exemplo.org",
                    senha_hash=gerar_hash(SENHA),
                )
                db.add(com); db.flush()
            vinculo = UsuarioEdicao(usuario_id=com.id, edicao_id=edicao.id,
                                    perfil_id=perfis["Comissario"].id)
            db.add(vinculo); db.flush()
            for instituicao_id in instituicoes:
                db.add(UsuarioInstituicao(
                    usuario_edicao_id=vinculo.id, instituicao_id=instituicao_id
                ))
            if instituicoes == [inst_a.id] and sufixo == "Bia":
                # Metade da Escola A no nome da Bia: a coluna abre com dado.
                for crianca in criancas[:3]:
                    crianca.comissario_id = com.id

        db.commit()

        print(f"pronto: edicao {edicao.id}, {len(NOMES)} criancas em 2 instituicoes")
        print("time da Escola A: ZZ_NAV Bia e ZZ_NAV Carla; Creche B: ZZ_NAV Davi")
        print(f"conta: {EMAIL} / {SENHA}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
