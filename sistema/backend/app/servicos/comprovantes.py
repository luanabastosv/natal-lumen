"""O comprovante do dinheiro que entrou — de um padrinho ou de um doador.

Dois donos, uma implementacao. `pagamentos` e `recebimentos` guardam os mesmos
tres campos (arquivo no disco, id e link da copia no Drive) e passam pelos
mesmos passos, na mesma ordem e pelos mesmos motivos:

    1. tipo do arquivo conferido antes de ler qualquer byte;
    2. leitura com teto de tamanho (servicos/upload.py);
    3. gravacao no disco, que e o ORIGINAL;
    4. copia no Drive, que e ESPELHO: falha aqui nao derruba a requisicao,
       porque o comprovante ja esta gravado e vale do mesmo jeito;
    5. remocao do arquivo anterior, se havia — trocar o comprovante duas vezes
       deixaria dois arquivos orfaos que ninguem mais alcanca. So DEPOIS do
       commit, por quem chama: apagado antes, um commit que falhasse deixaria
       o banco apontando para um arquivo que ja nao existe.

Quem chama continua sendo dono da autorizacao e do commit: este modulo nao sabe
quem pode subir comprovante de quem, e nao fecha transacao.
"""

from datetime import date

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import config
from app.servicos import arquivos, drive
from app.servicos.log import registrar
from app.servicos.upload import ler_limitado

# Comprovante e foto de tela ou PDF do banco. Nada mais entra: o arquivo fica
# guardado para conferencia e nunca e executado, mas aceitar qualquer extensao
# convida a usar a pasta como deposito.
EXTENSOES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}

NAO_ENCONTRADO = HTTPException(
    status.HTTP_404_NOT_FOUND, "Comprovante nao encontrado."
)


def guardar(
    db: Session,
    dono,
    arquivo: UploadFile,
    *,
    cidade: str,
    ano: int,
    titular: str,
    data: date,
    tabela: str,
    usuario_id: int,
) -> str | None:
    """Guarda o comprovante em `dono` (um Pagamento ou um Recebimento).

    `titular` e o nome que vai no arquivo — o padrinho, ou quem doou. `tabela`
    entra no log, para o historico dizer de qual das duas origens era a linha.

    Devolve o caminho do comprovante ANTERIOR, se havia. Quem chama apaga com
    `apagar_arquivo` depois do commit.
    """
    extensao = EXTENSOES.get(arquivo.content_type or "")
    if extensao is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "O comprovante precisa ser uma imagem (JPG ou PNG) ou um PDF.",
        )

    conteudo = ler_limitado(arquivo)

    pasta = arquivos.pasta_dos_comprovantes(cidade, ano)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = arquivos.caminho_disponivel(
        pasta, arquivos.nome_do_comprovante(titular, data, extensao)
    )
    destino.write_bytes(conteudo)

    antigo = dono.comprovante_arquivo
    dono.comprovante_arquivo = str(destino.relative_to(config.caminho_arquivos))

    registrar(
        db, "comprovante_subido", usuario_id=usuario_id,
        tabela=tabela, registro_id=dono.id,
        detalhes={"arquivo": dono.comprovante_arquivo},
    )

    # O Drive e espelho, nunca o original. Ja esta gravado em disco a esta
    # altura, entao uma falha aqui NAO derruba a requisicao: o comprovante
    # vale do mesmo jeito, e subir o arquivo de novo refaz a tentativa.
    dono.comprovante_drive_id = None
    dono.comprovante_drive_link = None

    if not drive.configurado():
        return antigo

    try:
        enviado = drive.enviar(
            conteudo,
            arquivos.nome_do_comprovante_drive(cidade, ano, titular, data, extensao),
            arquivo.content_type or "application/octet-stream",
        )
        dono.comprovante_drive_id = enviado.id
        dono.comprovante_drive_link = enviado.link
        registrar(
            db, "comprovante_no_drive", usuario_id=usuario_id,
            tabela=tabela, registro_id=dono.id,
            detalhes={"drive_id": enviado.id},
        )
    except drive.ErroDrive as erro:
        # Fica no log para alguem investigar, e a tela mostra que o link do
        # Drive nao veio.
        registrar(
            db, "comprovante_drive_falhou", usuario_id=usuario_id,
            tabela=tabela, registro_id=dono.id,
            detalhes={"erro": erro.mensagem, "detalhe": erro.detalhe[:200]},
        )

    return antigo


def entregar(dono) -> FileResponse:
    """Devolve o arquivo do comprovante. Unica porta para ele, sempre autenticada."""
    if dono is None or not dono.comprovante_arquivo:
        raise NAO_ENCONTRADO

    try:
        caminho = arquivos.dentro_da_pasta(dono.comprovante_arquivo)
    except ValueError:
        raise NAO_ENCONTRADO from None

    if not caminho.is_file():
        raise NAO_ENCONTRADO

    return FileResponse(caminho, filename=caminho.name)


def apagar_arquivo(caminho: str | None) -> None:
    """Tira um comprovante do disco: o trocado, ou o da linha apagada.

    Chamado sempre DEPOIS do commit. Se o commit falha, o arquivo continua la,
    e o banco segue apontando para algo que existe.
    """
    if not caminho:
        return
    try:
        arquivos.dentro_da_pasta(caminho).unlink(missing_ok=True)
    except ValueError:
        pass
