"""Seed das permissoes e dos perfis.

Os perfis e permissoes vivem na base justamente para poderem ser alterados sem
mudar codigo. Este seed cria o estado inicial e e idempotente: rodar de novo nao
duplica nada.

Rodar com:  python -m app.seeds.perfis_permissoes
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Perfil, Permissao

# codigo -> descricao
# gerenciar_cadastros nao estava na lista original da especificacao: foi
# acrescentada porque instituicoes e dias do evento precisavam de dono. Vai
# so para a Coordenacao, entao na pratica nada mudou de alcance.
PERMISSOES: dict[str, str] = {
    "ver_painel": "Ver o painel inicial e os indicadores da edicao",
    "ver_criancas": "Ver a lista e os dados das criancas",
    "editar_criancas": "Criar, editar e excluir criancas",
    "importar_listas": "Importar listas de criancas enviadas pelas instituicoes",
    "ver_padrinhos": "Ver a lista e os dados dos padrinhos",
    "editar_padrinhos": "Criar e editar padrinhos e apadrinhamentos",
    "registrar_pagamentos": "Registrar e conferir pagamentos dos padrinhos",
    "subir_cartoes": "Digitalizar e subir os cartoes das criancas",
    "enviar_cartoes": "Marcar cartoes como enviados aos padrinhos",
    "gerenciar_kits": "Montar e registrar a entrega dos kits",
    "gerenciar_compras": "Registrar as compras da edicao",
    "fazer_checkin": "Fazer o check-in das criancas no dia do evento",
    "gerenciar_usuarios": "Criar usuarios e definir vinculos, perfis e instituicoes",
    "gerenciar_cadastros": "Cadastrar instituicoes e os dias do evento da edicao",
}

# nome do perfil -> (descricao, permissoes)
# Copiado ao pe da letra da especificacao. A coordenacao recebe todas as
# permissoes, sempre limitadas as suas edicoes.
# Nota: ver_painel so aparece na coordenacao — a especificacao nao a atribui
# aos outros perfis. Se o painel tiver de abrir para todos, e acrescentar
# "ver_painel" aqui (ou na base, sem mexer no codigo).
PERFIS: dict[str, tuple[str, tuple[str, ...]]] = {
    "Coordenacao": (
        "Coordenacao da cidade: todas as permissoes, limitadas as suas edicoes",
        tuple(PERMISSOES),
    ),
    "Comissario": (
        "Capta padrinhos, registra pagamentos e envia os cartoes",
        (
            "ver_criancas",
            "ver_padrinhos",
            "editar_padrinhos",
            "registrar_pagamentos",
            "enviar_cartoes",
            "fazer_checkin",
        ),
    ),
    "Monitor": (
        "Recolhe e digitaliza os cartoes das criancas",
        (
            "ver_criancas",
            "subir_cartoes",
            "fazer_checkin",
        ),
    ),
    "Estrutura": (
        "Compra e monta os kits e faz a entrega",
        (
            "ver_criancas",
            "gerenciar_kits",
            "gerenciar_compras",
            "fazer_checkin",
        ),
    ),
}

# Perfis filtrados pelas instituicoes atribuidas em usuario_instituicao.
# Coordenacao e Estrutura veem a edicao inteira.
PERFIS_FILTRADOS_POR_INSTITUICAO = ("Comissario", "Monitor")


def semear(db: Session) -> tuple[int, int]:
    """Cria o que falta. Devolve (permissoes criadas, perfis criados)."""
    permissoes_criadas = 0
    for codigo, descricao in PERMISSOES.items():
        permissao = db.scalar(select(Permissao).where(Permissao.codigo == codigo))
        if permissao is None:
            db.add(Permissao(codigo=codigo, descricao=descricao))
            permissoes_criadas += 1
        else:
            # Mantem a descricao em dia sem tocar nos vinculos existentes.
            permissao.descricao = descricao

    db.flush()

    por_codigo = {p.codigo: p for p in db.scalars(select(Permissao)).all()}

    perfis_criados = 0
    for nome, (descricao, codigos) in PERFIS.items():
        perfil = db.scalar(select(Perfil).where(Perfil.nome == nome))
        if perfil is None:
            perfil = Perfil(nome=nome, descricao=descricao)
            db.add(perfil)
            perfis_criados += 1
        else:
            perfil.descricao = descricao

        # Acrescenta as que faltam; nao remove ajustes feitos na base a mao.
        atuais = {p.codigo for p in perfil.permissoes}
        for codigo in codigos:
            if codigo not in atuais:
                perfil.permissoes.append(por_codigo[codigo])

    db.commit()
    return permissoes_criadas, perfis_criados


def main() -> None:
    db = SessionLocal()
    try:
        permissoes_criadas, perfis_criados = semear(db)
        print(f"permissoes: {permissoes_criadas} criada(s), {len(PERMISSOES)} no total")
        print(f"perfis    : {perfis_criados} criado(s), {len(PERFIS)} no total")
        print()
        for perfil in db.scalars(select(Perfil).order_by(Perfil.nome)).all():
            codigos = sorted(p.codigo for p in perfil.permissoes)
            print(f"{perfil.nome:14} {len(codigos):2} permissoes")
            print(f"               {', '.join(codigos)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
