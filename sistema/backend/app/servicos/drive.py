"""Comprovante de pagamento no Drive Compartilhado do evento.

Duas chamadas, nesta ordem:

  1. POST oauth2.googleapis.com/token
     troca um JWT que nos mesmos assinamos por um access_token de 1 hora
  2. POST www.googleapis.com/upload/drive/v3/files?uploadType=multipart
     cria o arquivo dentro da pasta e devolve o id e o link

Por que conta de servico e nao OAuth de uma pessoa: isto roda num servidor,
sem navegador para a tela de consentimento, e um refresh token de conta
pessoal expira quando o app nao esta publicado — o upload pararia sozinho, sem
aviso, dias depois.

Por que DRIVE COMPARTILHADO e nao uma pasta do "Meu Drive": numa pasta comum o
arquivo criado fica sendo propriedade da conta de servico, e conta de servico
nao tem cota de armazenamento nenhuma. O upload morre com
`storageQuotaExceeded` mesmo com a pasta compartilhada e permissao de escrita.
No Drive Compartilhado quem possui o arquivo e o proprio Drive, e o problema
nao existe. Dai o `supportsAllDrives=true` em toda chamada.

O Drive e ESPELHO, nunca o original: o comprovante e gravado em disco
primeiro, e so depois copiado para ca. Se esta parte falhar, o pagamento e o
arquivo continuam de pe e o envio pode ser refeito subindo o comprovante de
novo.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx2 as httpx
import jwt

from app.config import config

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
# A mesma colecao, sem o prefixo de upload: serve para procurar e criar pasta.
ARQUIVOS_URL = "https://www.googleapis.com/drive/v3/files"
ESCOPO = "https://www.googleapis.com/auth/drive.file"

# Um access_token vale 1h. Renova com folga, para nao correr o risco de usar um
# que expira no meio do upload.
FOLGA_S = 300


class ErroDrive(Exception):
    """Falha de envio com mensagem ja em portugues, para subir ate a tela."""

    def __init__(self, mensagem: str, *, detalhe: str = ""):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhe = detalhe


@dataclass
class Enviado:
    id: str
    link: str


def configurado() -> bool:
    return config.drive_ligado


def _cliente() -> httpx.Client:
    """Isolado numa funcao para o teste trocar o transporte sem rede."""
    return httpx.Client(timeout=config.drive_timeout_s)


def _credenciais() -> dict:
    """Le o JSON da conta de servico — do arquivo ou colado direto na config."""
    bruto = config.drive_credenciais.strip()
    if not bruto:
        raise ErroDrive("O envio para o Drive nao esta configurado neste servidor.")

    if not bruto.startswith("{"):
        caminho = Path(bruto)
        if not caminho.is_file():
            raise ErroDrive(
                "O arquivo de credenciais do Drive nao foi encontrado.",
                detalhe=str(caminho),
            )
        bruto = caminho.read_text()

    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise ErroDrive("As credenciais do Drive nao sao um JSON valido.", detalhe=str(erro))

    faltando = [c for c in ("client_email", "private_key") if not dados.get(c)]
    if faltando:
        raise ErroDrive(
            "As credenciais do Drive estao incompletas.",
            detalhe=f"faltam: {', '.join(faltando)}",
        )
    return dados


# Guardado entre chamadas: pedir um token novo a cada comprovante seria uma ida
# extra ao Google por upload, sem ganho nenhum.
_token: str = ""
_token_expira: float = 0.0


def esquecer_token() -> None:
    """Descarta o access_token guardado. Trocar credencial exige isto."""
    global _token, _token_expira
    _token, _token_expira = "", 0.0


def _access_token() -> str:
    global _token, _token_expira

    agora = time.time()
    if _token and agora < _token_expira - FOLGA_S:
        return _token

    cred = _credenciais()
    afirmacao = jwt.encode(
        {
            "iss": cred["client_email"],
            "scope": ESCOPO,
            "aud": TOKEN_URL,
            "iat": int(agora),
            "exp": int(agora) + 3600,
        },
        cred["private_key"],
        algorithm="RS256",
    )

    try:
        with _cliente() as cliente:
            resposta = cliente.post(
                TOKEN_URL,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": afirmacao,
                },
            )
    except httpx.HTTPError as erro:
        raise ErroDrive("Nao foi possivel falar com o Google.", detalhe=str(erro))

    if resposta.status_code != 200:
        raise ErroDrive(
            "O Google recusou as credenciais do Drive.",
            detalhe=resposta.text[:300],
        )

    corpo = resposta.json()
    _token = corpo["access_token"]
    _token_expira = agora + int(corpo.get("expires_in", 3600))
    return _token


def garantir_subpasta(nome: str) -> str:
    """Devolve o id de uma subpasta da pasta configurada, criando-a se preciso.

    Serve ao backup, que NAO deve cair no mesmo lugar dos comprovantes: um
    comprovante e um recibo de uma pessoa; o dump do banco tem o nome e a idade
    de todas as criancas, o contato dos padrinhos e os hashes de senha. Em
    pasta separada da para restringir quem ve uma coisa sem restringir a outra.

    O escopo `drive.file` so enxerga o que a propria conta de servico criou —
    o que basta aqui: ou ela achou a pasta que ela mesma criou, ou cria agora.
    """
    if not configurado():
        raise ErroDrive("O envio para o Drive nao esta configurado neste servidor.")

    token = _access_token()
    consulta = (
        f"name = '{nome}' and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{config.drive_pasta_id}' in parents and trashed = false"
    )

    with _cliente() as cliente:
        achou = cliente.get(
            ARQUIVOS_URL,
            params={
                "q": consulta,
                "fields": "files(id)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if achou.status_code == 200 and achou.json().get("files"):
            return achou.json()["files"][0]["id"]

        criada = cliente.post(
            ARQUIVOS_URL,
            params={"supportsAllDrives": "true", "fields": "id"},
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": nome,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [config.drive_pasta_id],
            },
        )

    if criada.status_code not in (200, 201):
        raise ErroDrive(_traduzir(criada), detalhe=criada.text[:300])
    return criada.json()["id"]


def enviar(
    conteudo: bytes,
    nome_arquivo: str,
    tipo_mime: str,
    pasta_id: str | None = None,
    converter_para: str | None = None,
) -> Enviado:
    """Cria o arquivo na pasta indicada (ou na configurada) e devolve id e link.

    `converter_para` pede ao Google que transforme o arquivo num documento
    dele na chegada — a planilha diaria sobe como .xlsx e vira Planilha Google,
    que abre no navegador e no celular sem baixar nada.
    """
    if not configurado():
        raise ErroDrive("O envio para o Drive nao esta configurado neste servidor.")

    token = _access_token()

    metadados = {"name": nome_arquivo, "parents": [pasta_id or config.drive_pasta_id]}
    if converter_para:
        metadados["mimeType"] = converter_para

    try:
        with _cliente() as cliente:
            resposta = cliente.post(
                UPLOAD_URL,
                params={
                    "uploadType": "multipart",
                    # Sem isto a API se recusa a enxergar Drives Compartilhados.
                    "supportsAllDrives": "true",
                    "fields": "id,webViewLink",
                },
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "metadata": (None, json.dumps(metadados), "application/json"),
                    "file": (nome_arquivo, conteudo, tipo_mime),
                },
            )
    except httpx.HTTPError as erro:
        raise ErroDrive("Nao foi possivel enviar o comprovante ao Drive.", detalhe=str(erro))

    if resposta.status_code not in (200, 201):
        raise ErroDrive(_traduzir(resposta), detalhe=resposta.text[:300])

    corpo = resposta.json()
    return Enviado(id=corpo["id"], link=corpo.get("webViewLink", ""))


def _traduzir(resposta) -> str:
    """Os erros que a gente de fato vai ver, em portugues."""
    try:
        motivo = resposta.json()["error"]["errors"][0].get("reason", "")
    except Exception:
        motivo = ""

    if motivo == "storageQuotaExceeded":
        return (
            "O Google recusou: a pasta de destino nao e um Drive Compartilhado. "
            "Numa pasta do Meu Drive o arquivo fica sendo da conta de servico, "
            "que nao tem cota."
        )
    if resposta.status_code == 404:
        return "A pasta do Drive nao foi encontrada, ou a conta de servico nao alcanca ela."
    if resposta.status_code == 403:
        return "A conta de servico nao tem permissao de escrita nessa pasta do Drive."
    return f"O Drive recusou o envio (HTTP {resposta.status_code})."
