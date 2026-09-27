"""Os grupos da comunidade a que os comissarios pertencem.

Nao ha tela de cadastro: o grupo nasce escrito a mao no formulario do usuario,
no momento em que a coordenacao atribui a funcao de comissario. Digitado a mao,
o mesmo grupo chega escrito de tres jeitos — "Elyon", "elyon", "Élyon" — e a
lista de sugestoes, que existe para evitar exatamente isso, seria a primeira a
encher de duplicatas.

Por isso cada grupo guarda tambem o nome normalizado (sem acento, sem
maiusculas, sem espaco sobrando) e e por ele que a base cobra unicidade dentro
da cidade. O nome que aparece na tela continua sendo o que a primeira pessoa
escreveu: quem digitar "elyon" depois vai parar no grupo Elyon, com a grafia
dele.
"""

import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Grupo

TAMANHO_MAXIMO = 120


def normalizar(nome: str) -> str:
    """A forma comparavel do nome: sem acento, sem caixa e sem espaco duplo."""
    sem_acento = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.split()).lower()


def achar_ou_criar(db: Session, cidade_id: int, nome: str) -> Grupo | None:
    """O grupo desta cidade com este nome, criando-o se for a primeira vez.

    Devolve None para nome vazio — comissario ainda sem grupo nomeado.

    Nao commita: quem chama esta no meio de uma transacao maior (o cadastro do
    usuario ou a edicao do vinculo) e commita no fim.
    """
    nome = " ".join(nome.split())[:TAMANHO_MAXIMO]
    if not nome:
        return None

    chave = normalizar(nome)
    grupo = db.scalar(
        select(Grupo).where(
            Grupo.cidade_id == cidade_id, Grupo.nome_normalizado == chave
        )
    )
    if grupo is not None:
        return grupo

    grupo = Grupo(cidade_id=cidade_id, nome=nome, nome_normalizado=chave)
    db.add(grupo)
    db.flush()
    return grupo
