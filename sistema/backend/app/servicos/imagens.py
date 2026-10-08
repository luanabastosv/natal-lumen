"""As imagens digitalizadas que saem por rota: cartoes e autorizacoes.

As duas pilhas sao fotos de papel guardadas em ARQUIVOS_DIR, e as duas saem
do mesmo jeito — inteiras para olhar, pequenas para a grade. Mora aqui para a
tela de cartoes e a de autorizacoes nao terem cada uma a sua copia.
"""

import cv2
from fastapi import HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Crianca
from app.servicos import arquivos, nomes_de_arquivo


def apagar_do_disco(caminho_relativo: str) -> None:
    """Tira o arquivo do disco, sem reclamar se ele ja nao estiver la.

    Falta de arquivo nao pode impedir o registro de sair: um registro
    apontando para um arquivo que sumiu e exatamente o caso que a pessoa esta
    tentando limpar.
    """
    try:
        caminho = arquivos.dentro_da_pasta(caminho_relativo)
    except ValueError:
        return
    caminho.unlink(missing_ok=True)


def _no_disco(caminho_relativo: str):
    try:
        caminho = arquivos.dentro_da_pasta(caminho_relativo)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo nao encontrado.")

    if not caminho.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo nao encontrado.")
    return caminho


def servir(caminho_relativo: str) -> FileResponse:
    """A imagem inteira."""
    return FileResponse(_no_disco(caminho_relativo), media_type="image/jpeg")


def servir_miniatura(caminho_relativo: str) -> Response:
    """A mesma imagem, pequena. Para a visao de arquivo, que mostra muitas.

    Existe porque o original tem ~290 KB: uma escola com sessenta cartoes
    baixaria 17 MB so para desenhar a grade, e boa parte disso num celular no
    meio do recolhimento. A miniatura fica em ~15 KB.

    Gerada na hora, sem guardar em disco: redimensionar um JPEG desse tamanho
    custa poucos milissegundos, e um cache em disco seria mais um lugar para
    ficar desatualizado. Quem evita o trabalho repetido e o `Cache-Control`: o
    navegador guarda por uma hora, e a imagem nao muda.
    """
    imagem = cv2.imread(str(_no_disco(caminho_relativo)))
    if imagem is None:
        # Arquivo ilegivel: melhor 404 do que 500. A grade mostra o buraco e a
        # pessoa abre o original para ver o que houve.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Imagem ilegivel.")

    altura = max(1, int(imagem.shape[0] * 320 / imagem.shape[1]))
    pequena = cv2.resize(imagem, (320, altura), interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".jpg", pequena, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Imagem ilegivel.")

    return Response(
        content=buffer.tobytes(),
        media_type="image/jpeg",
        # `private`: e imagem de crianca, nao pode ficar em cache compartilhado
        # de proxy nenhum no caminho.
        headers={"Cache-Control": "private, max-age=3600"},
    )


def conferir_nome_da_troca(db: Session, nome_arquivo: str | None, crianca: Crianca) -> None:
    """Recusa a troca quando o arquivo nao tem o codigo DESTA crianca.

    Na pilha o codigo do nome do arquivo diz de quem e a foto; na troca ja se
    sabe de quem e — e por isso mesmo o nome tem de concordar. Trocar duas
    fotos de lugar e o erro mais provavel do processo, e a troca existe para
    corrigi-lo, nao para repeti-lo com a foto de outra crianca.

    O casamento olha os codigos da edicao inteira, e nao so o desta crianca:
    assim "SL12.jpg" e reconhecido como da SL12 e recusado na troca da SL1, em
    vez de passar porque "SL1" esta dentro do nome.
    """
    codigos = list(
        db.scalars(select(Crianca.codigo).where(Crianca.edicao_id == crianca.edicao_id)).all()
    )
    acerto = nomes_de_arquivo.casar(nome_arquivo or "", codigos)
    if acerto.codigo == crianca.codigo:
        return

    if acerto.codigo:
        motivo = f"Este arquivo e do codigo {acerto.codigo}, e esta imagem e de {crianca.codigo}."
    else:
        motivo = "O nome do arquivo nao tem o codigo da crianca."
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        f"{motivo} Para trocar a imagem de {crianca.primeiro_nome}, o arquivo tem de "
        f"se chamar {crianca.codigo}.",
    )
