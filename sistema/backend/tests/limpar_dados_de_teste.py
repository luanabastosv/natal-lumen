"""Apaga os dados deixados pelos testes de navegador.

Os testes automatizados (pytest-like) limpam sozinhos; o teste de navegador
passa pela interface e nao consegue. Este comando desfaz o que ele cria, para
poder rodar de novo.

Rodar com:  python -m tests.limpar_dados_de_teste
"""

from sqlalchemy import delete, or_, select

from app.database import SessionLocal
from app.models import (
    Cidade,
    Crianca,
    DiaEvento,
    Edicao,
    Instituicao,
    LogAtividade,
    TokenAcesso,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)

MARCAS = ("ZZB%", "ZZ_AUTH%", "ZZ_CAD%", "ZZ_TESTE%")


def main() -> None:
    db = SessionLocal()
    try:
        cidades = db.scalars(
            select(Cidade).where(or_(*[Cidade.nome.like(m) for m in MARCAS]))
        ).all()
        cidade_ids = [c.id for c in cidades]

        edicao_ids = []
        if cidade_ids:
            edicao_ids = list(
                db.scalars(select(Edicao.id).where(Edicao.cidade_id.in_(cidade_ids))).all()
            )

        if edicao_ids:
            db.execute(delete(Crianca).where(Crianca.edicao_id.in_(edicao_ids)))
            vinculos = list(
                db.scalars(
                    select(UsuarioEdicao.id).where(UsuarioEdicao.edicao_id.in_(edicao_ids))
                ).all()
            )
            if vinculos:
                db.execute(
                    delete(UsuarioInstituicao).where(
                        UsuarioInstituicao.usuario_edicao_id.in_(vinculos)
                    )
                )
                db.execute(delete(UsuarioEdicao).where(UsuarioEdicao.id.in_(vinculos)))
            db.execute(delete(DiaEvento).where(DiaEvento.edicao_id.in_(edicao_ids)))
            db.execute(delete(Edicao).where(Edicao.id.in_(edicao_ids)))

        if cidade_ids:
            db.execute(delete(Instituicao).where(Instituicao.cidade_id.in_(cidade_ids)))
            db.execute(delete(Cidade).where(Cidade.id.in_(cidade_ids)))

        usuarios = db.scalars(
            select(Usuario).where(or_(*[Usuario.nome.like(m) for m in MARCAS]))
        ).all()
        ids = [u.id for u in usuarios]
        if ids:
            db.execute(delete(LogAtividade).where(LogAtividade.usuario_id.in_(ids)))
            db.execute(delete(TokenAcesso).where(TokenAcesso.usuario_id.in_(ids)))
            restantes = list(
                db.scalars(select(UsuarioEdicao.id).where(UsuarioEdicao.usuario_id.in_(ids))).all()
            )
            if restantes:
                db.execute(
                    delete(UsuarioInstituicao).where(
                        UsuarioInstituicao.usuario_edicao_id.in_(restantes)
                    )
                )
                db.execute(delete(UsuarioEdicao).where(UsuarioEdicao.id.in_(restantes)))
            db.execute(delete(Usuario).where(Usuario.id.in_(ids)))

        db.commit()
        print(
            f"removidos: {len(cidade_ids)} cidade(s), {len(edicao_ids)} edicao(oes), "
            f"{len(ids)} usuario(s) de teste"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
