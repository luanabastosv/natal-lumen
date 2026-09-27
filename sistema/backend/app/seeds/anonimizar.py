"""Troca todo dado pessoal por dado falso. Para HOMOLOGACAO, nunca producao.

O ambiente de teste precisa do VOLUME e dos FORMATOS da producao — um padrinho
com vinte criancas, a planilha com cem linhas, a paginacao de verdade — sem
precisar dos nomes das criancas. Servidor de teste tem menos cuidado por
natureza: senha mais fraca, mais gente com acesso, backup relaxado. Nomes de
crianca nao tem o que fazer la.

Fluxo:

    # na producao
    pg_dump ... > producao.dump

    # na homologacao
    pg_restore ... producao.dump
    python -m app.seeds.anonimizar

O que MUDA:  nomes, WhatsApp, email, observacoes, senhas, links do Drive.
O que FICA:  codigos, idades, sexo, valores, datas, e todas as ligacoes —
             que e exatamente o que as telas exercitam.
"""

import sys
from hashlib import blake2b

from sqlalchemy import delete, select, update

from app.config import config
from app.database import SessionLocal
from app.models import Crianca, Padrinho, Pagamento, TokenAcesso, Usuario

PRIMEIROS = (
    "Ana", "Beatriz", "Carla", "Daniela", "Elisa", "Fernanda", "Gabriela",
    "Helena", "Isabela", "Julia", "Larissa", "Mariana", "Natalia", "Olivia",
    "Paula", "Rafaela", "Sofia", "Tatiana", "Valentina", "Yasmin",
    "Andre", "Bruno", "Caio", "Daniel", "Eduardo", "Felipe", "Gustavo",
    "Heitor", "Igor", "Joao", "Lucas", "Matheus", "Nicolas", "Otavio",
    "Pedro", "Rafael", "Samuel", "Thiago", "Vitor", "Wesley",
)

SOBRENOMES = (
    "Albuquerque", "Barbosa", "Cavalcante", "Duarte", "Esteves", "Ferreira",
    "Gomes", "Holanda", "Ibiapina", "Juca", "Lima", "Macedo", "Nogueira",
    "Oliveira", "Pinheiro", "Queiroz", "Rocha", "Sampaio", "Teixeira",
    "Uchoa", "Vasconcelos", "Ximenes", "Zacarias",
)


def _sorteio(semente: str, quantos: int) -> int:
    """Escolha estavel a partir de um texto.

    Usa hash, e nao `random`: rodar duas vezes tem de dar o MESMO nome falso
    para a mesma linha. Se mudasse a cada execucao, comparar um print de ontem
    com a tela de hoje viraria adivinhacao.
    """
    return int.from_bytes(blake2b(semente.encode(), digest_size=8).digest(), "big") % quantos


def nome_falso(tabela: str, id_: int) -> str:
    a = _sorteio(f"{tabela}:{id_}:primeiro", len(PRIMEIROS))
    b = _sorteio(f"{tabela}:{id_}:sobrenome", len(SOBRENOMES))
    # Anda pelo menos uma casa a partir do primeiro sobrenome: sorteando os
    # dois solto, sai "Helena Nogueira Nogueira" de vez em quando.
    c = (b + 1 + _sorteio(f"{tabela}:{id_}:segundo", len(SOBRENOMES) - 1)) % len(SOBRENOMES)
    return f"{PRIMEIROS[a]} {SOBRENOMES[b]} {SOBRENOMES[c]}"


def telefone_falso(id_: int) -> str:
    """Faixa 9xxxx reservada para documentacao, que nao toca em ninguem."""
    return f"(85) 99{_sorteio(f'zap:{id_}', 900) + 100:03d}-{_sorteio(f'zap2:{id_}', 9000) + 1000:04d}"


def main() -> None:
    # A trava que importa. Este comando destroi dado pessoal sem volta; rodar
    # por engano na producao seria irreversivel sem restaurar backup.
    if config.ambiente == "producao":
        print("RECUSADO: AMBIENTE=producao.")
        print()
        print("Este comando apaga nomes, contatos e senhas sem volta.")
        print("Ele so roda em desenvolvimento ou homologacao.")
        raise SystemExit(1)

    print(f"Ambiente: {config.ambiente}")
    print(f"Base:     {config.database_url.split('@')[-1]}")
    print()

    if "--sim" not in sys.argv:
        print("Isto vai trocar TODO nome, contato e senha desta base por dado falso.")
        print("Confirme com:  python -m app.seeds.anonimizar --sim")
        raise SystemExit(1)

    db = SessionLocal()
    try:
        contas = {}

        criancas = db.scalars(select(Crianca)).all()
        for c in criancas:
            c.nome = nome_falso("crianca", c.id)
            if c.observacoes:
                c.observacoes = "Observacao removida na anonimizacao."
        contas["criancas"] = len(criancas)

        padrinhos = db.scalars(select(Padrinho)).all()
        for p in padrinhos:
            p.nome = nome_falso("padrinho", p.id)
            if p.whatsapp:
                p.whatsapp = telefone_falso(p.id)
            if p.email:
                p.email = f"padrinho{p.id}@exemplo.invalido"
            if p.observacoes:
                p.observacoes = "Observacao removida na anonimizacao."
        contas["padrinhos"] = len(padrinhos)

        # Usuarios: nome e email trocados, senha zerada e sessoes derrubadas.
        # Ninguem entra em homologacao com a senha de producao — e o admin de
        # teste e criado depois, pelo seed, com link proprio.
        usuarios = db.scalars(select(Usuario)).all()
        for u in usuarios:
            u.nome = nome_falso("usuario", u.id)
            u.email = f"usuario{u.id}@exemplo.invalido"
            u.senha_hash = None
            u.whatsapp = None
            u.tentativas_falhas = 0
            u.bloqueado_ate = None
        contas["usuarios"] = len(usuarios)

        # Tokens de primeiro acesso e de redefinicao vao fora: sao links
        # validos que foram emitidos para pessoas reais.
        apagados = db.execute(delete(TokenAcesso)).rowcount
        contas["tokens apagados"] = apagados

        # O link do Drive apontaria para o arquivo REAL na pasta da producao.
        # O caminho em disco fica: o arquivo nao existe aqui, e a rota de
        # download responde 404, que e o comportamento correto.
        soltos = db.execute(
            update(Pagamento)
            .where(Pagamento.comprovante_drive_id.is_not(None))
            .values(comprovante_drive_id=None, comprovante_drive_link=None)
        ).rowcount
        contas["links do Drive soltos"] = soltos

        db.commit()
    finally:
        db.close()

    print("Pronto:")
    for chave, quanto in contas.items():
        print(f"  {quanto:6d}  {chave}")
    print()
    print("Agora crie um acesso de teste:")
    print('  python -m app.seeds.criar_admin "Seu Nome" "voce@exemplo.org"')


if __name__ == "__main__":
    main()
