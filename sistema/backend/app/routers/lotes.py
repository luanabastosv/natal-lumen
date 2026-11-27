"""Apadrinhamento em lote: um grupo que apadrinhou junto.

O caso que trouxe esta tela (27/11/2026): um grupo de oitenta pessoas juntou o
dinheiro e fez uma transferencia so. Cada pessoa e um padrinho de verdade, com
a sua crianca e o seu agradecimento, mas cadastrar oitenta padrinhos um a um,
com oitenta vezes o mesmo comprovante, e uma tarde inteira de clique.

O caminho e o da importacao de listas: le, mostra, e so grava quando a pessoa
confirma.

    1. GET  /lotes/instituicoes     quantas criancas livres cada instituicao tem
    2. GET  /lotes/vagas            as criancas livres das instituicoes escolhidas
    3. POST /lotes/ler-planilha     as pessoas do grupo, com os avisos
    4. POST /lotes                  grava tudo, ou nada
    5. GET  /lotes/{id}/agradecimentos   o ZIP do grupo, quantas vezes precisar
    6. POST /lotes/{id}/enviados         marca quem ja recebeu o agradecimento

Quem escolhe a crianca de cada pessoa e a administracao, nunca o sistema
sozinho. A tela SUGERE uma por linha, na ordem do codigo, e a pessoa troca o
que quiser antes de confirmar.

**So a administracao geral.** Um lote cria dezenas de padrinhos, pagamentos e
apadrinhamentos de uma vez, com um comprovante so: e dinheiro entrando no caixa
sem passar pelo comissario. A trava e a mesma de cidades e edicoes
(`exige_admin_geral`), conferida em todas as rotas daqui, e a tela so mostra o
caminho para quem a tem.
"""

import io
import json
import zipfile
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import config
from app.database import get_db
from app.models import (
    Apadrinhamento,
    Crianca,
    EnvioCartao,
    Edicao,
    Instituicao,
    LoteApadrinhamento,
    Padrinho,
    Pagamento,
)
from app.models.tipos import TipoApadrinhamento
from app.routers.padrinhos import (
    _crianca_para_apadrinhar,
    _mesma_pessoa,
    _montar_agradecimento,
    _repetido,
    _so_digitos,
)
from app.schemas.padrinhos import FormaDePagamento
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_admin_geral
from app.servicos import arquivos, cobrancas, drive, lotes, whatsapp
from app.servicos.comprovantes import EXTENSOES
from app.servicos.log import registrar
from app.servicos.nomes import mesmo_nome, nome_proprio
from app.servicos.upload import ler_limitado

router = APIRouter(prefix="/lotes", tags=["lotes"])

BD = Annotated[Session, Depends(get_db)]
Admin = Annotated[ContextoAcesso, Depends(exige_admin_geral)]


def _edicao(db: Session, edicao_id: int) -> Edicao:
    edicao = db.scalar(
        select(Edicao).where(Edicao.id == edicao_id).options(joinedload(Edicao.cidade))
    )
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")
    return edicao


def _ocupados(db: Session, crianca_ids) -> set[tuple[int, str]]:
    """(crianca, tipo) que ja tem dono: pago, prometido ou reservado por link."""
    return set(
        db.execute(
            select(Apadrinhamento.crianca_id, Apadrinhamento.tipo).where(
                Apadrinhamento.crianca_id.in_(crianca_ids)
            )
        ).all()
    )


# ------------------------------------------------------------- instituicoes


@router.get("/instituicoes")
def instituicoes_com_vagas(edicao_id: int, db: BD, ctx: Admin):
    """As instituicoes da edicao, com quantas cestas e festas ainda estao livres.

    E o que a tela mostra para escolher de onde vem o lote: "62 cestas livres"
    diz na hora se uma instituicao so basta para o grupo.
    """
    cobrancas.expirar_vencidas(db)
    edicao = _edicao(db, edicao_id)
    festa_aberta = edicao.festa_liberada_em is not None

    criancas = db.execute(
        select(Crianca.id, Crianca.instituicao_id).where(
            Crianca.edicao_id == edicao_id, Crianca.desistiu_em.is_(None)
        )
    ).all()
    ocupados = _ocupados(db, [c.id for c in criancas]) if criancas else set()

    contagem: dict[int, dict] = {}
    for c in criancas:
        item = contagem.setdefault(c.instituicao_id, {"criancas": 0, "cesta": 0, "festa": 0})
        item["criancas"] += 1
        if (c.id, TipoApadrinhamento.CESTA) not in ocupados:
            item["cesta"] += 1
        if festa_aberta and (c.id, TipoApadrinhamento.FESTA) not in ocupados:
            item["festa"] += 1

    nomes = dict(
        db.execute(
            select(Instituicao.id, Instituicao.nome).where(Instituicao.id.in_(list(contagem)))
        ).all()
    ) if contagem else {}

    return {
        "festa_liberada": festa_aberta,
        "valor_cesta": edicao.valor_cesta,
        "valor_festa": edicao.valor_festa,
        "instituicoes": sorted(
            (
                {
                    "id": iid,
                    "nome": nomes.get(iid, "?"),
                    "criancas": n["criancas"],
                    "cesta_livres": n["cesta"],
                    "festa_livres": n["festa"],
                }
                for iid, n in contagem.items()
            ),
            key=lambda i: i["nome"],
        ),
    }


@router.get("/vagas")
def vagas(
    db: BD,
    ctx: Admin,
    edicao_id: int,
    instituicao_ids: Annotated[str, Query(description="ids separados por virgula")],
):
    """As criancas das instituicoes escolhidas que ainda tem cesta ou festa livre.

    Em ordem de instituicao e codigo: e a ordem da sugestao da tela. Quem
    desistiu fica de fora — nao vai ao evento, nao ha o que apadrinhar.
    """
    try:
        ids = [int(i) for i in instituicao_ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Instituicoes invalidas.")
    if not ids:
        return {"criancas": []}

    cobrancas.expirar_vencidas(db)
    edicao = _edicao(db, edicao_id)
    festa_aberta = edicao.festa_liberada_em is not None

    criancas = db.scalars(
        select(Crianca)
        .where(
            Crianca.edicao_id == edicao_id,
            Crianca.instituicao_id.in_(ids),
            Crianca.desistiu_em.is_(None),
        )
        .options(joinedload(Crianca.instituicao))
    ).all()
    ocupados = _ocupados(db, [c.id for c in criancas]) if criancas else set()

    ordem = {iid: n for n, iid in enumerate(ids)}
    saida = []
    for c in criancas:
        cesta = (c.id, TipoApadrinhamento.CESTA) not in ocupados
        festa = festa_aberta and (c.id, TipoApadrinhamento.FESTA) not in ocupados
        if not (cesta or festa):
            continue
        saida.append({
            "id": c.id,
            "codigo": c.codigo,
            "nome": c.nome,
            "idade": c.idade,
            "sexo": c.sexo,
            "instituicao_id": c.instituicao_id,
            "instituicao": c.instituicao.nome,
            "cesta_livre": cesta,
            "festa_livre": festa,
        })
    saida.sort(key=lambda c: (ordem.get(c["instituicao_id"], 0), _ordem_do_codigo(c["codigo"])))
    return {"criancas": saida}


def _ordem_do_codigo(codigo: str):
    """ES2 antes de ES10: a parte numerica conta como numero."""
    digitos = "".join(ch for ch in codigo if ch.isdigit())
    letras = "".join(ch for ch in codigo if not ch.isdigit())
    return (letras, int(digitos) if digitos else 0, codigo)


# ----------------------------------------------------------------- planilha


@router.post("/ler-planilha")
def ler_planilha(
    db: BD,
    ctx: Admin,
    edicao_id: int = Form(...),
    arquivo: UploadFile = File(...),
):
    """As pessoas do grupo, como a tela vai mostrar. Nada e gravado aqui.

    Cada linha volta com os avisos, e com o padrinho que ja existe na edicao
    quando o nome bate (a mesma regra do cadastro avulso): nesse caso o lote
    usa o cadastro dele em vez de criar outro, e a tela diz isso.

    O mesmo nome duas vezes na planilha e a mesma pessoa, e ela recebe duas
    criancas — quem apadrinhou duas dentro do grupo aparece duas vezes.
    """
    _edicao(db, edicao_id)
    try:
        linhas, colunas = lotes.ler_planilha(ler_limitado(arquivo), arquivo.filename or "")
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    saida = []
    for linha in linhas:
        avisos: list[str] = []
        existente = None
        if linha.nome and not linha.erros:
            achado = _repetido(db, edicao_id, nome=linha.nome, whatsapp=linha.whatsapp, email=None)
            if achado is not None:
                p, _ = achado
                existente = {"id": p.id, "nome": p.nome, "whatsapp": p.whatsapp}
                avisos.append(f"ja cadastrado como {p.nome}: usa o cadastro dele")
            else:
                familia = _mesmo_telefone(db, edicao_id, linha.whatsapp, linha.nome)
                if familia:
                    avisos.append(f"mesmo telefone de {familia}")
        if not linha.whatsapp:
            avisos.append("sem telefone")

        vezes = sum(1 for o in linhas if o.nome and mesmo_nome(o.nome, linha.nome))
        if linha.nome and vezes > 1:
            avisos.append(f"aparece {vezes} vezes: recebe {vezes} criancas")

        saida.append({
            "linha": linha.linha,
            "nome": linha.nome,
            "whatsapp": linha.whatsapp,
            "erros": linha.erros,
            "avisos": avisos,
            "padrinho_existente": existente,
        })

    return {"colunas": colunas, "linhas": saida}


def _mesmo_telefone(db: Session, edicao_id: int, whatsapp: str | None, nome: str) -> str | None:
    """O padrinho de OUTRO nome com este telefone: familia que divide o numero."""
    telefone = _so_digitos(whatsapp)
    if len(telefone) < 10:
        return None
    for p in db.scalars(select(Padrinho).where(Padrinho.edicao_id == edicao_id)).all():
        if _so_digitos(p.whatsapp) == telefone and not _mesma_pessoa(nome, p.nome):
            return p.nome
    return None


# ------------------------------------------------------------------ gravar


class ItemLote(BaseModel):
    linha: int | None = None
    nome: str = Field(min_length=3, max_length=180)
    whatsapp: str | None = Field(default=None, max_length=30)
    # O cadastro que ja existe na edicao, quando a leitura achou um.
    padrinho_id: int | None = None
    crianca_id: int
    tipo: str


class LoteIn(BaseModel):
    edicao_id: int
    nome: str = Field(min_length=2, max_length=160)
    data: date
    forma: FormaDePagamento = "Pix"
    observacoes: str | None = Field(default=None, max_length=1000)
    chave_envio: str | None = Field(default=None, max_length=64)
    itens: list[ItemLote] = Field(min_length=1, max_length=lotes.MAXIMO_DE_LINHAS * 2)


def _quem(item: ItemLote) -> str:
    return f"Linha {item.linha}" if item.linha else item.nome


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_lote(
    db: BD,
    ctx: Admin,
    dados: str = Form(..., description="LoteIn em JSON"),
    comprovante: UploadFile = File(...),
):
    """Grava o lote inteiro: padrinhos, pagamentos, apadrinhamentos e comprovante.

    Tudo ou nada, como o apadrinhar avulso: uma crianca que alguem apadrinhou
    enquanto a tela estava aberta derruba o lote todo, e o erro diz qual — a
    tela recarrega as vagas e a pessoa troca so aquela linha.

    Um pagamento por pessoa, no valor das criancas dela, e nao um pagamento do
    grupo: e assim que o painel, o financeiro e a ficha de cada padrinho
    continuam contando como sempre. O comprovante e o mesmo para todos, e a
    observacao de cada pagamento diz que ele faz parte do lote.

    O comprovante e gravado uma vez por pagamento no disco, e nao um arquivo
    so apontado por todos: trocar ou apagar o comprovante de um padrinho tira
    o arquivo do disco (servicos/comprovantes.py), e com um arquivo
    compartilhado isso apagaria o dos outros setenta e nove. No Drive vai uma
    copia so, e todos levam o mesmo link.
    """
    try:
        lote_in = LoteIn.model_validate(json.loads(dados))
    except (ValueError, ValidationError) as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Dados do lote invalidos: {erro}")

    ja = _lote_da_chave(db, lote_in.chave_envio)
    if ja is not None:
        return _resumo(db, ja)

    extensao = EXTENSOES.get(comprovante.content_type or "")
    if extensao is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "O comprovante precisa ser uma imagem (JPG ou PNG) ou um PDF.",
        )
    conteudo = ler_limitado(comprovante)

    cobrancas.expirar_vencidas(db)
    edicao = _edicao(db, lote_in.edicao_id)

    pares = [(i.crianca_id, i.tipo) for i in lote_in.itens]
    if len(set(pares)) != len(pares):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A mesma crianca foi escolhida para duas pessoas. Confira a tabela.",
        )

    # As pessoas do lote: o mesmo nome e a mesma pessoa, com mais de uma crianca.
    grupos: list[tuple[ItemLote, list[ItemLote]]] = []
    for item in lote_in.itens:
        if item.tipo not in (TipoApadrinhamento.CESTA, TipoApadrinhamento.FESTA):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{_quem(item)}: tipo invalido.")
        for primeiro, lista in grupos:
            mesmo = (
                item.padrinho_id == primeiro.padrinho_id
                if item.padrinho_id or primeiro.padrinho_id
                else mesmo_nome(item.nome, primeiro.nome)
            )
            if mesmo:
                lista.append(item)
                break
        else:
            grupos.append((item, [item]))

    criancas = {}
    for item in lote_in.itens:
        try:
            crianca = _crianca_para_apadrinhar(db, ctx, item.crianca_id, item.tipo)
        except HTTPException as erro:
            raise HTTPException(erro.status_code, f"{_quem(item)}: {erro.detail}")
        if crianca.edicao_id != edicao.id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"{_quem(item)}: a crianca e de outra edicao."
            )
        criancas[item.crianca_id] = crianca

    lote = LoteApadrinhamento(
        edicao_id=edicao.id,
        nome=lote_in.nome.strip(),
        criado_por=ctx.usuario.id,
        chave_envio=lote_in.chave_envio,
    )
    db.add(lote)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        ja = _lote_da_chave(db, lote_in.chave_envio)
        if ja is None:
            raise
        return _resumo(db, ja)

    observacao = (
        f"Apadrinhamento em lote: {lote.nome}. O grupo pagou junto, numa "
        "transferencia so, e o comprovante e o mesmo para todos do lote."
    )
    if lote_in.observacoes:
        observacao += f" {lote_in.observacoes.strip()}"

    pagamentos: list[tuple[Pagamento, Padrinho]] = []
    criados = 0
    for primeiro, itens in grupos:
        padrinho = _padrinho_do_lote(db, ctx, edicao, primeiro)
        pagamento = Pagamento(
            padrinho_id=padrinho.id,
            valor=Decimal("0"),
            data=lote_in.data,
            forma=lote_in.forma,
            observacoes=observacao,
            registrado_por=ctx.usuario.id,
            lote_id=lote.id,
        )
        db.add(pagamento)
        db.flush()

        total = Decimal("0")
        for item in itens:
            crianca = criancas[item.crianca_id]
            valor = (
                crianca.edicao.valor_cesta
                if item.tipo == TipoApadrinhamento.CESTA
                else crianca.edicao.valor_festa
            )
            total += valor
            apadrinhamento = Apadrinhamento(
                crianca_id=crianca.id,
                padrinho_id=padrinho.id,
                tipo=item.tipo,
                valor=valor,
                comissario_id=ctx.usuario.id,
                pagamento_id=pagamento.id,
            )
            db.add(apadrinhamento)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"{_quem(item)}: {crianca.codigo} acabou de ganhar padrinho de "
                    f"{item.tipo}. Nada foi gravado: troque a crianca dessa linha.",
                )
            registrar(
                db, "apadrinhamento_criado", usuario_id=ctx.usuario.id,
                tabela="apadrinhamentos", registro_id=apadrinhamento.id,
                detalhes={
                    "crianca_id": crianca.id, "padrinho_id": padrinho.id,
                    "tipo": item.tipo, "valor": str(valor),
                    "pagamento_id": pagamento.id, "lote_id": lote.id,
                },
            )
            criados += 1

        pagamento.valor = total
        registrar(
            db, "pagamento_registrado", usuario_id=ctx.usuario.id,
            tabela="pagamentos", registro_id=pagamento.id,
            detalhes={"padrinho_id": padrinho.id, "valor": str(total), "lote_id": lote.id},
        )
        pagamentos.append((pagamento, padrinho))

    gravados = _guardar_comprovantes(db, ctx, edicao, lote, lote_in.data, pagamentos, conteudo, extensao,
                                     comprovante.content_type or "application/octet-stream")

    registrar(
        db, "lote_apadrinhamento_criado", usuario_id=ctx.usuario.id,
        tabela="lotes_apadrinhamento", registro_id=lote.id,
        detalhes={
            "nome": lote.nome, "padrinhos": len(pagamentos), "apadrinhamentos": criados,
        },
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        for caminho in gravados:
            caminho.unlink(missing_ok=True)
        raise
    return _resumo(db, lote)


def _lote_da_chave(db: Session, chave: str | None):
    if not chave:
        return None
    return db.scalar(select(LoteApadrinhamento).where(LoteApadrinhamento.chave_envio == chave))


def _padrinho_do_lote(db: Session, ctx: ContextoAcesso, edicao: Edicao, item: ItemLote) -> Padrinho:
    """O cadastro que ja existe (a leitura achou), ou um novo.

    Sem `padrinho_id`, confere de novo se o nome ja e de alguem da edicao:
    entre a leitura e o gravar, outra pessoa pode ter cadastrado o mesmo
    doador, e o lote nao pode criar a duplicata que o cadastro avulso recusa.
    """
    if item.padrinho_id:
        padrinho = db.get(Padrinho, item.padrinho_id)
        if padrinho is None or padrinho.edicao_id != edicao.id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{_quem(item)}: o cadastro de {item.nome} nao foi encontrado nesta edicao. "
                "Leia a planilha de novo.",
            )
        return padrinho

    achado = _repetido(db, edicao.id, nome=item.nome, whatsapp=item.whatsapp, email=None)
    if achado is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{_quem(item)}: ja existe um padrinho {achado[0].nome} nesta edicao. "
            "Leia a planilha de novo para o lote usar o cadastro dele.",
        )
    padrinho = Padrinho(
        edicao_id=edicao.id,
        nome=nome_proprio(item.nome),
        whatsapp=(item.whatsapp or "").strip() or None,
        criado_por=ctx.usuario.id,
    )
    db.add(padrinho)
    db.flush()
    registrar(
        db, "padrinho_criado", usuario_id=ctx.usuario.id,
        tabela="padrinhos", registro_id=padrinho.id,
        detalhes={"nome": padrinho.nome, "edicao_id": edicao.id, "lote": True},
    )
    return padrinho


def _guardar_comprovantes(db, ctx, edicao, lote, data, pagamentos, conteudo, extensao, mime):
    """Uma copia no disco por pagamento; uma so no Drive, com o link em todos.

    Devolve os caminhos gravados, para quem chama apagar se o commit falhar.
    """
    cidade, ano = edicao.cidade.nome, edicao.ano
    pasta = arquivos.pasta_dos_comprovantes(cidade, ano)
    pasta.mkdir(parents=True, exist_ok=True)

    gravados = []
    for pagamento, padrinho in pagamentos:
        destino = arquivos.caminho_disponivel(
            pasta, arquivos.nome_do_comprovante(padrinho.nome, data, extensao)
        )
        destino.write_bytes(conteudo)
        gravados.append(destino)
        pagamento.comprovante_arquivo = str(destino.relative_to(config.caminho_arquivos))

    if drive.configurado():
        try:
            enviado = drive.enviar(
                conteudo,
                arquivos.nome_do_comprovante_drive(cidade, ano, f"LOTE {lote.nome}", data, extensao),
                mime,
            )
            for pagamento, _ in pagamentos:
                pagamento.comprovante_drive_id = enviado.id
                pagamento.comprovante_drive_link = enviado.link
            registrar(
                db, "comprovante_no_drive", usuario_id=ctx.usuario.id,
                tabela="lotes_apadrinhamento", registro_id=lote.id,
                detalhes={"drive_id": enviado.id},
            )
        except drive.ErroDrive as erro:
            # O disco e o original: sem o Drive o comprovante vale igual.
            registrar(
                db, "comprovante_drive_falhou", usuario_id=ctx.usuario.id,
                tabela="lotes_apadrinhamento", registro_id=lote.id,
                detalhes={"erro": erro.mensagem, "detalhe": erro.detalhe[:200]},
            )
    return gravados


# ---------------------------------------------------------------- consulta


def _apadrinhamentos_do_lote(db: Session, lote_id: int):
    return db.scalars(
        select(Apadrinhamento)
        .join(Pagamento, Pagamento.id == Apadrinhamento.pagamento_id)
        .join(Padrinho, Padrinho.id == Apadrinhamento.padrinho_id)
        .where(Pagamento.lote_id == lote_id)
        .options(
            joinedload(Apadrinhamento.crianca).joinedload(Crianca.instituicao),
            joinedload(Apadrinhamento.crianca).joinedload(Crianca.dia_evento),
            joinedload(Apadrinhamento.padrinho).joinedload(Padrinho.edicao).joinedload(Edicao.cidade),
            selectinload(Apadrinhamento.envios),
        )
        .order_by(Padrinho.nome, Apadrinhamento.id)
    ).all()


def _enviado_em(a: Apadrinhamento):
    """Quando o agradecimento desta crianca saiu pela ultima vez, ou None.

    A mesma regra da ficha do padrinho (routers/padrinhos.py): o envio mais
    recente manda, e depois de uma troca de crianca so conta o que saiu
    depois dela.
    """
    envios = [
        e for e in a.envios
        if e.status == "enviado" and (a.trocado_em is None or e.criado_em >= a.trocado_em)
    ]
    return max((e.criado_em for e in envios), default=None)


def _resumo(db: Session, lote: LoteApadrinhamento, com_linhas: bool = True) -> dict:
    itens = _apadrinhamentos_do_lote(db, lote.id)
    saida = {
        "id": lote.id,
        "nome": lote.nome,
        "criado_em": lote.criado_em,
        "padrinhos": len({a.padrinho_id for a in itens}),
        "apadrinhamentos": len(itens),
        "total": sum((a.valor for a in itens), Decimal("0")),
    }
    if com_linhas:
        saida["linhas"] = [
            {
                "apadrinhamento_id": a.id,
                "padrinho_id": a.padrinho_id,
                "padrinho": a.padrinho.nome,
                "whatsapp": a.padrinho.whatsapp,
                "crianca_codigo": a.crianca.codigo,
                "crianca": a.crianca.nome,
                "instituicao": a.crianca.instituicao.nome,
                "tipo": a.tipo,
                "desistiu": a.crianca.desistiu_em is not None,
                "enviado_em": _enviado_em(a),
            }
            for a in itens
        ]
    return saida


@router.get("")
def listar_lotes(edicao_id: int, db: BD, ctx: Admin):
    """Os lotes da edicao, do mais novo para o mais antigo."""
    itens = db.scalars(
        select(LoteApadrinhamento)
        .where(LoteApadrinhamento.edicao_id == edicao_id)
        .order_by(LoteApadrinhamento.criado_em.desc())
    ).all()
    return [_resumo(db, l, com_linhas=False) for l in itens]


@router.get("/{lote_id}")
def detalhe_lote(lote_id: int, db: BD, ctx: Admin):
    lote = db.get(LoteApadrinhamento, lote_id)
    if lote is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote nao encontrado.")
    return _resumo(db, lote)


@router.get("/{lote_id}/agradecimentos")
def agradecimentos_do_lote(lote_id: int, db: BD, ctx: Admin):
    """Os agradecimentos do grupo, num ZIP so, um por pessoa e crianca.

    O nome do arquivo comeca pelo nome completo do padrinho (ver
    servicos/lotes.nome_no_zip): o ZIP vai para o grupo inteiro, e cada um
    procura o seu. Crianca que desistiu depois fica de fora, como no ZIP do
    padrinho avulso: nao ha agradecimento a mandar por quem nao vai.
    """
    lote = db.get(LoteApadrinhamento, lote_id)
    if lote is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote nao encontrado.")

    vistos: set[tuple[int, int]] = set()
    nomes_usados: set[str] = set()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zip_:
        for a in _apadrinhamentos_do_lote(db, lote.id):
            if a.crianca.desistiu_em is not None or (a.padrinho_id, a.crianca_id) in vistos:
                continue
            vistos.add((a.padrinho_id, a.crianca_id))
            png, _ = _montar_agradecimento(a)
            nome = lotes.nome_no_zip(a.padrinho.nome, a.crianca.codigo, a.crianca.nome)
            base, n = nome[:-4], 2
            while nome in nomes_usados:
                nome, n = f"{base}_{n}.png", n + 1
            nomes_usados.add(nome)
            zip_.writestr(nome, png)

    if not vistos:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este lote nao tem agradecimento a baixar.")

    nome_zip = f"AGRADECIMENTOS_LOTE_{arquivos.limpar_texto(lote.nome) or lote.id}.zip"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nome_zip}"'},
    )


class EnviadosIn(BaseModel):
    apadrinhamento_ids: list[int] = Field(min_length=1, max_length=50)


@router.post("/{lote_id}/enviados")
def marcar_enviados(lote_id: int, dados: EnviadosIn, db: BD, ctx: Admin):
    """Registra que o agradecimento destas criancas foi mandado ao padrinho.

    O envio pela Cloud API esta desligado desde 08/10/2026: quem manda e a
    pessoa, pela propria conversa do WhatsApp, com a imagem anexada. A tela
    abre a conversa e marca aqui, para a lista do lote dizer quem ja recebeu
    e quem falta — sem isso, com quarenta padrinhos, alguem fica sem ou
    recebe duas vezes.

    Vai para a mesma tabela dos envios pela API (sem `mensagem_id`, que e o
    que a Meta devolve): assim a ficha de cada padrinho tambem mostra o
    agradecimento como enviado, sem uma segunda fonte para a mesma pergunta.
    """
    lote = db.get(LoteApadrinhamento, lote_id)
    if lote is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote nao encontrado.")

    do_lote = {a.id: a for a in _apadrinhamentos_do_lote(db, lote.id)}
    for aid in dados.apadrinhamento_ids:
        a = do_lote.get(aid)
        if a is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Esse apadrinhamento nao e deste lote.")
        telefone = whatsapp.telefone_e164(a.padrinho.whatsapp) or (a.padrinho.whatsapp or "")[:20]
        envio = EnvioCartao(
            apadrinhamento_id=a.id,
            telefone=telefone or "-",
            status="enviado",
            enviado_por=ctx.usuario.id,
        )
        db.add(envio)
        db.flush()
        registrar(
            db, "agradecimento_enviado_a_mao", usuario_id=ctx.usuario.id,
            tabela="apadrinhamentos", registro_id=a.id,
            detalhes={"lote_id": lote.id, "envio_id": envio.id},
        )
    db.commit()
    db.expire_all()
    return _resumo(db, lote)
