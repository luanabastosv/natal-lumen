"""Copia dos cartoes e das autorizacoes no Drive Compartilhado do evento.

Para a equipe abrir o desenho de uma crianca no Drive sem entrar no sistema,
e para o dia em que o sistema cair. As pastas ficam dentro da pasta
configurada (DRIVE_PASTA_ID), que so a coordenacao alcanca:

    Cartões - {edicao}/{instituicao}/Cesta/ESCOLA_X_MARIA_SILVA_CESTA.jpg
    Cartões - {edicao}/{instituicao}/Festa/...
    Autorizações - {edicao}/{instituicao}/ESCOLA_X_MARIA_SILVA_AUTORIZACAO.jpg

Mesma regra dos comprovantes: o disco e o ORIGINAL, o Drive e espelho. Falha
aqui nunca desfaz o que subiu — fica no log, o `drive_id` continua nulo, e a
copia da noite (espelhar_no_drive.py) manda de novo.

Roda DEPOIS da resposta (BackgroundTasks), e nao dentro dela: uma pilha de 120
cartoes sao 120 envios ao Google, e o monitor nao pode ficar minutos olhando a
tela esperando o Drive.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models import Autorizacao, Cartao, Crianca, Edicao
from app.servicos import arquivos, drive
from app.servicos.log import registrar

PASTA_CARTOES = "Cartões - {edicao}"
PASTA_AUTORIZACOES = "Autorizações - {edicao}"
# Edicao de teste (ZZ) nunca vai para o Drive da equipe.
PREFIXO_TESTE = "ZZ"

def _de_teste(edicao: Edicao) -> bool:
    return edicao.nome.upper().startswith(PREFIXO_TESTE)


def _pastas(registro: Cartao | Autorizacao) -> tuple[str, ...]:
    crianca = registro.crianca
    if isinstance(registro, Cartao):
        return (
            PASTA_CARTOES.format(edicao=crianca.edicao.nome),
            crianca.instituicao.nome,
            registro.tipo.capitalize(),
        )
    return (
        PASTA_AUTORIZACOES.format(edicao=crianca.edicao.nome),
        crianca.instituicao.nome,
    )


def espelhar(db: Session, registro: Cartao | Autorizacao) -> bool:
    """Manda a imagem para o Drive e grava o id. Nao faz commit.

    Devolve se foi. Sem Drive configurado, edicao de teste ou arquivo sumido do
    disco, nao vai e nao reclama: nada disso se resolve tentando de novo.
    """
    crianca = registro.crianca
    if not drive.configurado() or _de_teste(crianca.edicao):
        return False

    tabela = "cartoes" if isinstance(registro, Cartao) else "autorizacoes"
    try:
        caminho = arquivos.dentro_da_pasta(registro.arquivo)
        conteudo = caminho.read_bytes()
    except (OSError, ValueError):
        return False

    try:
        pasta_id = drive.garantir_caminho(*_pastas(registro))
        enviado = drive.enviar(conteudo, caminho.name, "image/jpeg", pasta_id)
    except drive.ErroDrive as erro:
        registrar(
            db, f"{tabela}_drive_falhou", tabela=tabela, registro_id=registro.id,
            detalhes={"erro": erro.mensagem, "detalhe": erro.detalhe[:200]},
        )
        return False

    registro.drive_id = enviado.id
    return True


def tirar(db: Session, drive_id: str | None, *, tabela: str, registro_id: int) -> None:
    """Manda para a lixeira do Drive a copia de uma imagem que saiu do sistema.

    A copia de um cartao apagado por engano ficaria na pasta com o nome da
    crianca errada. Nao faz commit.
    """
    if not drive_id or not drive.configurado():
        return
    try:
        drive.para_a_lixeira(drive_id)
    except drive.ErroDrive as erro:
        registrar(
            db, f"{tabela}_drive_lixeira_falhou", tabela=tabela, registro_id=registro_id,
            detalhes={"drive_id": drive_id, "erro": erro.mensagem},
        )


def _buscar(db: Session, modelo, registro_id: int):
    return db.scalar(
        select(modelo)
        .where(modelo.id == registro_id)
        .options(
            joinedload(modelo.crianca).joinedload(Crianca.instituicao),
            joinedload(modelo.crianca).joinedload(Crianca.edicao),
        )
    )


def em_segundo_plano(
    modelo: type[Cartao] | type[Autorizacao],
    ids: list[int],
    antigos: list[str | None] | None = None,
) -> None:
    """Para o BackgroundTasks: sessao propria, porque a do pedido ja fechou.

    `antigos` sao os ids no Drive das imagens trocadas: saem para a lixeira so
    depois de a nova ter ido, para a pasta nunca ficar sem a imagem da crianca.
    Commit por imagem: uma falha no meio nao perde o id das que ja foram.
    """
    if not drive.configurado():
        return

    tabela = modelo.__tablename__
    db = SessionLocal()
    try:
        for indice, registro_id in enumerate(ids):
            registro = _buscar(db, modelo, registro_id)
            if registro is None:
                continue
            espelhar(db, registro)
            if antigos and antigos[indice]:
                tirar(db, antigos[indice], tabela=tabela, registro_id=registro_id)
            db.commit()
    finally:
        db.close()


def tirar_em_segundo_plano(tabela: str, registro_id: int, drive_id: str | None) -> None:
    """A lixeira do apagar, depois da resposta. Sessao propria, so para o log."""
    if not drive_id or not drive.configurado():
        return
    db = SessionLocal()
    try:
        tirar(db, drive_id, tabela=tabela, registro_id=registro_id)
        db.commit()
    finally:
        db.close()


def pendentes(db: Session) -> tuple[int, int]:
    """Manda tudo o que ainda nao tem copia no Drive. Devolve (foram, falharam).

    Pega o que falhou durante o dia e o que subiu antes de o espelho existir.
    """
    foram = falharam = 0
    for modelo in (Cartao, Autorizacao):
        ids = db.scalars(
            select(modelo.id)
            .join(Crianca, Crianca.id == modelo.crianca_id)
            .join(Edicao, Edicao.id == Crianca.edicao_id)
            .where(modelo.drive_id.is_(None), ~Edicao.nome.ilike(f"{PREFIXO_TESTE}%"))
            .order_by(modelo.id)
        ).all()
        for registro_id in ids:
            registro = _buscar(db, modelo, registro_id)
            if espelhar(db, registro):
                foram += 1
            else:
                falharam += 1
            db.commit()
    return foram, falharam
