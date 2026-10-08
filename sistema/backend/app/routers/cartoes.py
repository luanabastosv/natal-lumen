"""Cartoes de agradecimento: digitalizacao em lote e envio aos padrinhos.

A pilha de autorizacoes sobe pelo mesmo envio em lote, com `tipo=autorizacao`:
o caminho do papel e o mesmo — digitalizar, nomear pelo codigo, conferir —, e
so o lugar onde a linha e gravada muda. O resto delas mora em
routers/autorizacoes.py.

Cada crianca escreve dois cartoes, um para cada padrinho. O destinatario nao
fica gravado no cartao: e encontrado por crianca + tipo -> apadrinhamento ->
padrinho. Assim o cartao pode ser digitalizado antes de haver padrinho.

A crianca de cada foto e identificada pelo CODIGO no nome do arquivo, e nao
pelo nome escrito no cartao — ver servicos/nomes_de_arquivo.py.
"""

import base64
import json
import shutil
import time
import uuid
from datetime import UTC, datetime
from typing import Annotated

import cv2
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import config
from app.database import get_db
from app.models import (
    Apadrinhamento,
    Autorizacao,
    Cartao,
    Crianca,
    Edicao,
    Instituicao,
    Padrinho,
)
from app.models.tipos import StatusCartao
from app.schemas.cartoes import (
    ArquivoDoLote,
    CartaoOut,
    ConfirmarLote,
    MarcarEnviados,
    PaginaCartoes,
    PastaInstituicao,
    PreviaLote,
    ResultadoLote,
)
from app.servicos.apadrinhamento import CONFIRMADO
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos import arquivos, imagens, nomes_de_arquivo, scanner
from app.servicos.upload import ler_limitado
from app.servicos.log import registrar

router = APIRouter(prefix="/cartoes", tags=["cartoes"])

BD = Annotated[Session, Depends(get_db)]
Subir = Annotated[ContextoAcesso, Depends(exige_permissao("subir_cartoes"))]
Enviar = Annotated[ContextoAcesso, Depends(exige_permissao("enviar_cartoes"))]
Ver = Annotated[ContextoAcesso, Depends(exige_permissao("ver_criancas"))]

PASTA_TEMP = config.caminho_arquivos / "cartoes_temp"

AUTORIZACAO = "autorizacao"

# Teto por envio: cada arquivo e lido inteiro na memoria para endireitar.
MAX_POR_LOTE = 120


# Previa que ninguem confirma deixa as imagens na pasta temporaria. Sem
# varredura elas ficam para sempre — e sao fotos de cartao de crianca ocupando
# disco sem nenhuma linha no banco apontando para elas.
HORAS_ATE_VARRER = 12


def _limpar_lotes_velhos() -> None:
    """Apaga previas abandonadas. Roda barato, a cada previa nova."""
    if not PASTA_TEMP.is_dir():
        return
    limite = time.time() - HORAS_ATE_VARRER * 3600
    for caminho in PASTA_TEMP.iterdir():
        try:
            if caminho.stat().st_mtime > limite:
                continue
            if caminho.is_dir():
                shutil.rmtree(caminho, ignore_errors=True)
            else:
                # .json do manifesto, e tambem os .jpg soltos que sobraram do
                # fluxo antigo de cartao avulso: nada mais aponta para eles.
                caminho.unlink(missing_ok=True)
        except OSError:
            continue


def _miniatura(imagem, largura: int = 220) -> str:
    """JPEG pequeno em base64, so para conferir na previa."""
    altura = max(1, int(imagem.shape[0] * largura / imagem.shape[1]))
    pequena = cv2.resize(imagem, (largura, altura), interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".jpg", pequena, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return base64.b64encode(buffer.tobytes()).decode() if ok else ""


def _padrinho_do_cartao(db: Session, cartao: Cartao) -> Padrinho | None:
    """Quem recebe este cartao: crianca + tipo -> apadrinhamento -> padrinho.

    So apadrinhamento confirmado: o cartao agradece quem DOOU, e mandar
    agradecimento a quem ainda nao pagou e cobrar ao contrario. Enquanto a
    promessa nao vira pagamento, este cartao nao tem para quem ir.
    """
    return db.scalar(
        select(Padrinho)
        .join(Apadrinhamento, Apadrinhamento.padrinho_id == Padrinho.id)
        .where(
            Apadrinhamento.crianca_id == cartao.crianca_id,
            Apadrinhamento.tipo == cartao.tipo,
            CONFIRMADO,
        )
    )


def _saida(db: Session, cartao: Cartao) -> CartaoOut:
    padrinho = _padrinho_do_cartao(db, cartao)
    return CartaoOut(
        id=cartao.id,
        crianca_id=cartao.crianca_id,
        crianca_codigo=cartao.crianca.codigo,
        crianca_nome=cartao.crianca.nome,
        instituicao=cartao.crianca.instituicao.nome,
        tipo=cartao.tipo,
        arquivo=cartao.arquivo,
        texto_ocr=cartao.texto_ocr,
        status=cartao.status,
        criado_em=cartao.criado_em,
        enviado_em=cartao.enviado_em,
        padrinho_id=padrinho.id if padrinho else None,
        padrinho_nome=padrinho.nome if padrinho else None,
        padrinho_whatsapp=padrinho.whatsapp if padrinho else None,
    )


def _filtro(ctx: ContextoAcesso, permissao: str):
    """Cartoes das criancas que o usuario alcanca."""
    return Cartao.crianca_id.in_(select(Crianca.id).where(ctx.filtro_criancas(permissao)))


def _buscar_crianca(db: Session, ctx: ContextoAcesso, crianca_id: int, permissao: str) -> Crianca:
    crianca = db.scalar(
        select(Crianca)
        .where(Crianca.id == crianca_id, ctx.filtro_criancas(permissao))
        .options(
            joinedload(Crianca.instituicao),
            joinedload(Crianca.edicao).joinedload(Edicao.cidade),
        )
    )
    if crianca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crianca nao encontrada.")
    return crianca


@router.get("", response_model=PaginaCartoes)
def listar(
    db: BD,
    ctx: Ver,
    crianca_id: int | None = None,
    # A tela e de pastas: quase toda chamada vem com uma instituicao. A edicao
    # entra junto porque sem ela quem trabalha em duas veria as duas
    # misturadas na mesma pasta — o cartao e da crianca, e a crianca e de um
    # ano so.
    instituicao_id: int | None = None,
    edicao_id: int | None = None,
    tipo: str | None = None,
    situacao: str | None = Query(default=None, pattern="^(digitalizado|enviado)$"),
    sem_padrinho: bool = False,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
):
    condicao = _filtro(ctx, "ver_criancas")

    if crianca_id is not None:
        condicao = condicao & (Cartao.crianca_id == crianca_id)
    if instituicao_id is not None or edicao_id is not None:
        de_criancas = select(Crianca.id)
        if instituicao_id is not None:
            de_criancas = de_criancas.where(Crianca.instituicao_id == instituicao_id)
        if edicao_id is not None:
            de_criancas = de_criancas.where(Crianca.edicao_id == edicao_id)
        condicao = condicao & Cartao.crianca_id.in_(de_criancas)
    if tipo is not None:
        condicao = condicao & (Cartao.tipo == tipo)
    if situacao is not None:
        condicao = condicao & (Cartao.status == situacao)

    if sem_padrinho:
        # Cartao ja digitalizado que ainda nao tem para quem ir — e o so
        # prometido entra aqui: ate o pagamento ser registrado, o cartao dele
        # tambem esta parado.
        tem_padrinho = select(Apadrinhamento.id).where(
            Apadrinhamento.crianca_id == Cartao.crianca_id,
            Apadrinhamento.tipo == Cartao.tipo,
            CONFIRMADO,
        )
        condicao = condicao & ~tem_padrinho.exists()

    total = db.scalar(select(func.count()).select_from(Cartao).where(condicao)) or 0

    itens = db.scalars(
        select(Cartao)
        .where(condicao)
        .options(joinedload(Cartao.crianca).joinedload(Crianca.instituicao))
        .order_by(Cartao.criado_em.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()

    return PaginaCartoes(
        total=total, pagina=pagina, por_pagina=por_pagina,
        itens=[_saida(db, c) for c in itens],
    )


@router.get("/pastas", response_model=list[PastaInstituicao])
def pastas(db: BD, ctx: Ver, edicao_id: int):
    """As pastas da tela de cartoes: uma por instituicao, com o que ha dentro.

    Passa pelo MESMO filtro da lista (`_filtro`), entao um monitor recebe so as
    pastas das instituicoes atribuidas a ele. A pasta nao cria fronteira de
    acesso nenhuma — quem alcanca o que ja e decidido em `filtro_criancas`, e
    aqui isso so vira navegacao.

    Esta tela e controle de CARTAO: quantos ha, de que tipo, quantos ja sairam.
    Quem e o padrinho de cada crianca e assunto da tela de padrinhos — aqui a
    pergunta e sobre a pilha de papel.

    Lista a instituicao que tem CRIANCA na edicao, mesmo sem nenhum cartao
    ainda: a pasta vazia e justamente onde o trabalho comeca, e e por ela que
    se sobe a primeira pilha. Uma pasta que so aparecesse depois do primeiro
    cartao nao teria como receber o primeiro cartao.
    """
    alcance = ctx.filtro_criancas("ver_criancas") & (Crianca.edicao_id == edicao_id)

    linhas = db.execute(
        select(
            Instituicao.id,
            Instituicao.nome,
            Instituicao.sigla,
            # Distinct porque o outerjoin repete a crianca uma vez por cartao:
            # sem isso, quem ja tem os dois cartoes contaria como duas criancas.
            func.count(func.distinct(Crianca.id)).label("criancas"),
            func.count(case((Cartao.tipo == "cesta", 1))).label("cesta"),
            func.count(case((Cartao.tipo == "festa", 1))).label("festa"),
            # Distinct pelo mesmo motivo: a autorizacao e uma por crianca, mas
            # a linha dela se repete a cada cartao da mesma crianca.
            func.count(func.distinct(Autorizacao.id)).label("autorizacoes"),
        )
        .select_from(Crianca)
        .join(Instituicao, Instituicao.id == Crianca.instituicao_id)
        .outerjoin(Cartao, Cartao.crianca_id == Crianca.id)
        .outerjoin(Autorizacao, Autorizacao.crianca_id == Crianca.id)
        .where(alcance)
        .group_by(Instituicao.id, Instituicao.nome, Instituicao.sigla)
        .order_by(Instituicao.nome)
    ).all()

    return [
        PastaInstituicao(
            instituicao_id=l.id,
            instituicao=l.nome,
            sigla=l.sigla,
            criancas=l.criancas,
            cesta=l.cesta,
            festa=l.festa,
            autorizacoes=l.autorizacoes,
        )
        for l in linhas
    ]


@router.post("/lote", response_model=PreviaLote)
async def lote_previa(
    db: BD,
    ctx: Subir,
    arquivos_enviados: list[UploadFile] = File(..., alias="arquivos"),
    tipo: str = Form(..., pattern="^(cesta|festa|autorizacao)$"),
    edicao_id: int = Form(...),
    # A pasta de onde o envio partiu. O envio acontece DENTRO de uma
    # instituicao, entao um cartao de outra escola na pilha e engano — e o
    # engano tem de aparecer na previa, nao virar cartao gravado no lugar
    # errado. Opcional para nao quebrar quem chama sem pasta.
    instituicao_id: int | None = Form(default=None),
):
    """Le a pilha de cartoes ja digitalizados e devolve a previa.

    Nao grava nada na base: as imagens ficam numa pasta temporaria e a previa
    num JSON ao lado, do mesmo jeito que a importacao de planilha.

    A crianca e encontrada pelo CODIGO no nome do arquivo — nao pelo nome
    escrito no cartao. Codigo e unico na edicao, nao tem acento e nao depende
    da letra de uma crianca de oito anos.
    """
    if not ctx.alcanca_edicao(edicao_id, "subir_cartoes"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Voce nao sobe cartao nesta edicao.")

    if len(arquivos_enviados) > MAX_POR_LOTE:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Envie no maximo {MAX_POR_LOTE} cartoes por vez.",
        )

    # Os codigos que este usuario alcanca nesta edicao. A busca nunca inventa
    # um codigo: ou casa com um destes, ou e erro na previa.
    criancas = db.scalars(
        select(Crianca)
        .where(Crianca.edicao_id == edicao_id, ctx.filtro_criancas("subir_cartoes"))
        .options(joinedload(Crianca.instituicao))
    ).all()
    por_codigo = {c.codigo: c for c in criancas}

    ids = [c.id for c in criancas] or [0]
    if tipo == AUTORIZACAO:
        consulta = select(Autorizacao.crianca_id).where(Autorizacao.crianca_id.in_(ids))
    else:
        consulta = select(Cartao.crianca_id).where(
            Cartao.crianca_id.in_(ids), Cartao.tipo == tipo
        )
    ja_tem = set(db.scalars(consulta).all())

    _limpar_lotes_velhos()

    id_lote = uuid.uuid4().hex
    pasta_lote = PASTA_TEMP / id_lote
    pasta_lote.mkdir(parents=True, exist_ok=True)

    saida: list[ArquivoDoLote] = []
    manifesto: list[dict] = []

    for indice, enviado in enumerate(arquivos_enviados):
        nome = enviado.filename or f"arquivo_{indice}"
        item = ArquivoDoLote(indice=indice, arquivo=nome, erros=[], avisos=[])

        acerto = nomes_de_arquivo.casar(nome, list(por_codigo))
        if acerto.erro:
            item.erros.append(acerto.erro)
        if acerto.aviso:
            item.avisos.append(acerto.aviso)

        crianca = por_codigo.get(acerto.codigo) if acerto.codigo else None
        if crianca is not None:
            item.codigo = crianca.codigo
            item.crianca_id = crianca.id
            item.crianca_nome = crianca.nome
            item.instituicao = crianca.instituicao.nome
            # As duas recusas dizem o QUE houve e o QUE FAZER. Antes diziam so
            # o que houve, e quem subia ficava olhando um arquivo barrado sem
            # saber se o defeito era do arquivo, do cadastro ou dele.
            if crianca.id in ja_tem:
                o_que = "uma autorizacao" if tipo == AUTORIZACAO else f"um cartao de {tipo}"
                item.erros.append(
                    f"{crianca.primeiro_nome} ja tem {o_que} aqui. "
                    "Para trocar a foto, use Substituir imagem na propria lista."
                )
            # O casamento do codigo continua olhando a edicao inteira, e nao so
            # a pasta: assim o erro sabe DIZER de quem e o cartao. Barrar depois
            # de reconhecer e melhor que nao reconhecer — "codigo nao
            # encontrado" mandaria procurar defeito no cadastro da crianca.
            elif instituicao_id is not None and crianca.instituicao_id != instituicao_id:
                item.erros.append(
                    f"Esta imagem nao e desta instituicao: o codigo {crianca.codigo} "
                    f"e de {crianca.instituicao.nome}. Abra a pasta dela para subir."
                )

        try:
            conteudo = await ler_limitado(enviado)
            imagem = scanner.carregar_imagem(conteudo)
        except HTTPException as erro:
            item.erros.append(str(erro.detail))
            imagem = None
        except Exception:
            item.erros.append("Nao foi possivel ler esta imagem.")
            imagem = None

        if imagem is not None and not item.erros:
            # Endireita a foto torta. E OpenCV, custa ~1 ms, e cai de volta na
            # foto original quando nao acha as bordas — nunca perde o cartao.
            endireitada, aviso = scanner.digitalizar(imagem)
            if aviso:
                item.avisos.append("Bordas nao detectadas: a foto foi guardada como veio.")

            caminho = pasta_lote / f"{indice}.jpg"
            if not cv2.imwrite(str(caminho), endireitada):
                item.erros.append("Falha ao guardar a imagem.")
            else:
                item.valida = True
                item.miniatura = _miniatura(endireitada)
                manifesto.append(
                    {"indice": indice, "arquivo": nome, "crianca_id": item.crianca_id}
                )

        saida.append(item)

    (PASTA_TEMP / f"{id_lote}.json").write_text(
        json.dumps({"tipo": tipo, "edicao_id": edicao_id, "itens": manifesto}),
        encoding="utf-8",
    )

    validas = sum(1 for i in saida if i.valida)
    return PreviaLote(
        id=id_lote,
        tipo=tipo,
        total=len(saida),
        validas=validas,
        com_erro=len(saida) - validas,
        arquivos=saida,
    )


@router.post("/lote/{id_lote}/confirmar", response_model=ResultadoLote)
def lote_confirmar(id_lote: str, db: BD, ctx: Subir, dados_in: ConfirmarLote | None = None):
    """Grava os cartoes que passaram na previa.

    Na pilha de autorizacoes, cada foto vem com as respostas que o monitor
    marcou ao conferi-la, pelo indice no lote. Falta de resposta recusa o lote
    inteiro ANTES de gravar qualquer coisa: gravar metade deixaria a pessoa sem
    saber quais ainda precisam ser marcadas.
    """
    if not id_lote.isalnum():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Identificador invalido.")

    caminho_manifesto = PASTA_TEMP / f"{id_lote}.json"
    if not caminho_manifesto.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Lote nao encontrado. Envie os arquivos de novo."
        )

    dados = json.loads(caminho_manifesto.read_text(encoding="utf-8"))
    tipo = dados["tipo"]
    pasta_lote = PASTA_TEMP / id_lote

    respostas = dados_in.respostas if dados_in else {}
    if tipo == AUTORIZACAO:
        sem_resposta = [
            item["arquivo"] for item in dados["itens"] if item["indice"] not in respostas
        ]
        if sem_resposta:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Falta marcar as respostas de {len(sem_resposta)} autorizacao(oes): "
                + ", ".join(sem_resposta[:5]),
            )

    gravados = 0
    ignorados = 0

    for item in dados["itens"]:
        origem = pasta_lote / f"{item['indice']}.jpg"
        if not origem.is_file() or item["crianca_id"] is None:
            ignorados += 1
            continue

        crianca = db.scalar(
            select(Crianca)
            .where(Crianca.id == item["crianca_id"], ctx.filtro_criancas("subir_cartoes"))
            .options(
                joinedload(Crianca.instituicao),
                joinedload(Crianca.edicao).joinedload(Edicao.cidade),
            )
        )
        if crianca is None:
            ignorados += 1
            continue

        edicao = crianca.edicao
        if tipo == AUTORIZACAO:
            pasta = arquivos.pasta_das_autorizacoes(edicao.cidade.nome, edicao.ano)
        else:
            pasta = arquivos.pasta_dos_cartoes(edicao.cidade.nome, edicao.ano)
        pasta.mkdir(parents=True, exist_ok=True)
        destino = arquivos.caminho_disponivel(
            pasta, arquivos.nome_do_cartao(crianca.instituicao.nome, crianca.nome, tipo)
        )
        relativo = str(destino.relative_to(config.caminho_arquivos))

        if tipo == AUTORIZACAO:
            registro = Autorizacao(
                crianca_id=crianca.id,
                arquivo=relativo,
                monitor_id=ctx.usuario.id,
                **respostas[item["indice"]].model_dump(),
            )
        else:
            registro = Cartao(
                crianca_id=crianca.id, tipo=tipo, arquivo=relativo, monitor_id=ctx.usuario.id
            )
        # SAVEPOINT, e nao rollback: um rollback inteiro levaria junto o que
        # este mesmo lote ja tinha gravado antes desta linha.
        try:
            with db.begin_nested():
                db.add(registro)
        except IntegrityError:
            # Alguem subiu o desta crianca entre a previa e o confirmar.
            ignorados += 1
            continue

        # So move depois de a base aceitar: assim nao fica imagem orfa.
        origem.replace(destino)
        gravados += 1

    registrar(
        db, "cartoes_em_lote", usuario_id=ctx.usuario.id,
        tabela="autorizacoes" if tipo == AUTORIZACAO else "cartoes",
        detalhes={"tipo": tipo, "gravados": gravados, "ignorados": ignorados},
    )
    db.commit()

    shutil.rmtree(pasta_lote, ignore_errors=True)
    caminho_manifesto.unlink(missing_ok=True)

    return ResultadoLote(gravados=gravados, ignorados=ignorados)


@router.get("/lote/{id_lote}/{indice}/imagem")
def imagem_do_lote(id_lote: str, indice: int, ctx: Subir):
    """Imagem de uma foto que ainda esta na previa, em tamanho de conferencia.

    A miniatura da previa tem 220px: da para ver que ha um cartao ali, nao para
    ler o que a crianca escreveu. A conferencia um a um abre a foto inteira, e
    ela ainda nao tem linha no banco — mora na pasta temporaria do lote.
    """
    if not id_lote.isalnum():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Identificador invalido.")

    caminho = PASTA_TEMP / id_lote / f"{indice}.jpg"
    if not caminho.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Imagem nao encontrada.")

    return FileResponse(caminho, media_type="image/jpeg")


@router.get("/{cartao_id}/imagem")
def imagem_do_cartao(cartao_id: int, db: BD, ctx: Ver):
    """Devolve a imagem. Unica porta para os arquivos, sempre autenticada."""
    cartao = db.scalar(
        select(Cartao).where(Cartao.id == cartao_id, _filtro(ctx, "ver_criancas"))
    )
    if cartao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cartao nao encontrado.")

    return imagens.servir(cartao.arquivo)


@router.get("/{cartao_id}/miniatura")
def miniatura_do_cartao(cartao_id: int, db: BD, ctx: Ver):
    """A mesma imagem, pequena, para a visao de arquivo (ver imagens.py)."""
    cartao = db.scalar(
        select(Cartao).where(Cartao.id == cartao_id, _filtro(ctx, "ver_criancas"))
    )
    if cartao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cartao nao encontrado.")

    return imagens.servir_miniatura(cartao.arquivo)


@router.delete("/{cartao_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_cartao(cartao_id: int, db: BD, ctx: Subir):
    """Apaga um cartao subido por engano.

    Exige `subir_cartoes`, a mesma permissao de quem sobe: quem pode pôr pode
    tirar o que pôs errado. O monitor digitaliza uma pilha inteira de uma vez —
    trocar duas fotos de lugar e o erro mais provavel do processo, e ate agora
    nao havia como desfazer sem mexer no banco.

    O arquivo sai do disco junto. Guardar a imagem de um cartao que nao deveria
    existir e guardar o erro: ela e foto de crianca, e o registro dela ja se
    foi.
    """
    cartao = db.scalar(
        select(Cartao).where(Cartao.id == cartao_id, _filtro(ctx, "subir_cartoes"))
    )
    if cartao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cartao nao encontrado.")

    imagens.apagar_do_disco(cartao.arquivo)

    registrar(
        db, "cartao_apagado", usuario_id=ctx.usuario.id,
        tabela="cartoes", registro_id=cartao.id,
        detalhes={"crianca_id": cartao.crianca_id, "tipo": cartao.tipo},
    )
    db.delete(cartao)
    db.commit()


@router.post("/{cartao_id}/trocar", response_model=CartaoOut)
async def trocar_imagem(
    cartao_id: int,
    db: BD,
    ctx: Subir,
    arquivo: UploadFile = File(...),
):
    """Troca a imagem de um cartao que ja existe, sem mexer no resto.

    Serve ao caso mais comum do erro: a foto saiu tremida, ou foi a do cartao
    errado. Apagar e subir de novo faria a mesma coisa em dois passos — e
    perderia o registro de quando aquele cartao entrou.

    A imagem nova passa pelo mesmo endireitamento da pilha: sem isso, a
    corrigida sairia torta enquanto as outras sairam retas.
    """
    cartao = db.scalar(
        select(Cartao)
        .where(Cartao.id == cartao_id, _filtro(ctx, "subir_cartoes"))
        .options(
            joinedload(Cartao.crianca).joinedload(Crianca.instituicao),
            joinedload(Cartao.crianca).joinedload(Crianca.edicao).joinedload(Edicao.cidade),
        )
    )
    if cartao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cartao nao encontrado.")

    imagens.conferir_nome_da_troca(db, arquivo.filename, cartao.crianca)

    conteudo = await ler_limitado(arquivo)
    imagem = scanner.carregar_imagem(conteudo)
    endireitada, _aviso = scanner.digitalizar(imagem)

    crianca = cartao.crianca
    pasta = arquivos.pasta_dos_cartoes(crianca.edicao.cidade.nome, crianca.edicao.ano)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = arquivos.caminho_disponivel(
        pasta, arquivos.nome_do_cartao(crianca.instituicao.nome, crianca.nome, cartao.tipo)
    )

    if not cv2.imwrite(str(destino), endireitada):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Nao foi possivel guardar a imagem."
        )

    # A antiga so sai DEPOIS de a nova estar no disco: se a gravacao falhar, o
    # cartao continua com a imagem que tinha, em vez de ficar sem nenhuma.
    antiga = cartao.arquivo
    cartao.arquivo = str(destino.relative_to(config.caminho_arquivos))
    cartao.monitor_id = ctx.usuario.id
    imagens.apagar_do_disco(antiga)

    registrar(
        db, "cartao_trocado", usuario_id=ctx.usuario.id,
        tabela="cartoes", registro_id=cartao.id,
        detalhes={"crianca_id": cartao.crianca_id, "tipo": cartao.tipo},
    )
    db.commit()
    db.refresh(cartao)
    return _saida(db, cartao)


@router.post("/enviados", response_model=list[CartaoOut])
def marcar_enviados(dados: MarcarEnviados, db: BD, ctx: Enviar):
    """Marca os cartoes como enviados aos padrinhos."""
    cartoes = db.scalars(
        select(Cartao)
        .where(Cartao.id.in_(dados.cartoes), _filtro(ctx, "ver_criancas"))
        .options(joinedload(Cartao.crianca).joinedload(Crianca.instituicao))
    ).all()

    if len(cartoes) != len(set(dados.cartoes)):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Ha cartoes que voce nao alcanca ou que nao existem."
        )

    sem_padrinho = [c.id for c in cartoes if _padrinho_do_cartao(db, c) is None]
    if sem_padrinho:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{len(sem_padrinho)} cartao(oes) ainda nao tem padrinho para receber.",
        )

    agora = datetime.now(UTC)
    for cartao in cartoes:
        cartao.status = StatusCartao.ENVIADO.value
        cartao.enviado_por = ctx.usuario.id
        cartao.enviado_em = agora

    registrar(
        db, "cartoes_enviados", usuario_id=ctx.usuario.id,
        tabela="cartoes",
        detalhes={"cartoes": [c.id for c in cartoes]},
    )
    db.commit()

    return [_saida(db, c) for c in cartoes]
