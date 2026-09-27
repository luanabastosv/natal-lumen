"""Envio pelo WhatsApp Cloud API, da Meta.

Duas chamadas, nesta ordem:

  1. POST /{phone_number_id}/media     sobe o PNG  -> devolve um media_id
  2. POST /{phone_number_id}/messages  manda o template com aquele media_id

Por que template e nao texto livre: quando quem inicia a conversa e o negocio
— e e sempre o nosso caso, o padrinho nao escreveu primeiro — a Meta so
entrega mensagem em um modelo aprovado por ela antes. Texto livre so dentro
das 24h depois de o padrinho responder.

O media_id vale 30 dias no servidor da Meta, mas nao reaproveitamos: o cartao
e remontado a cada envio, entao uma correcao no nome da crianca aparece no
envio seguinte sem ninguem ter de limpar cache.
"""

from dataclasses import dataclass

import httpx2 as httpx

from app.config import config

GRAFO = "https://graph.facebook.com"


class ErroWhatsapp(Exception):
    """Falha de envio com mensagem ja em portugues, para subir ate a tela."""

    def __init__(self, mensagem: str, *, detalhe: str = "", codigo: int | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhe = detalhe
        self.codigo = codigo


@dataclass
class Enviado:
    mensagem_id: str
    telefone: str


def configurado() -> bool:
    return config.whatsapp_ligado


def telefone_e164(numero: str | None) -> str | None:
    """"(27) 99999-8888" -> "5527999998888". None se nao parece telefone.

    A Meta quer so digitos, com codigo do pais. O cadastro aqui e brasileiro e
    quase sempre vem sem o 55 — acrescentamos. Numero que ja veio com 55 (ou
    de outro pais, com 12+ digitos) passa intacto.
    """
    so_digitos = "".join(c for c in (numero or "") if c.isdigit())

    # 10 = fixo com DDD, 11 = celular com DDD. Menos que isso nao e telefone.
    if len(so_digitos) < 10:
        return None
    if len(so_digitos) <= 11:
        return f"55{so_digitos}"
    return so_digitos


def _url(caminho: str) -> str:
    return f"{GRAFO}/{config.whatsapp_versao_api}/{config.whatsapp_phone_number_id}/{caminho}"


def _cabecalhos() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.whatsapp_token}"}


def _erro_da_meta(resposta: httpx.Response) -> ErroWhatsapp:
    """Traduz o erro estruturado da Meta em algo que o operador entenda."""
    try:
        corpo = resposta.json().get("error", {})
    except ValueError:
        corpo = {}

    codigo = corpo.get("code")
    mensagem = corpo.get("message") or f"Erro {resposta.status_code} no WhatsApp."
    detalhe = corpo.get("error_data", {}).get("details", "") or corpo.get("error_user_msg", "")

    # Os tres tropecos de sempre, ditos em portugues claro.
    if resposta.status_code in (401, 403):
        mensagem = "A Meta recusou as credenciais: confira o WHATSAPP_TOKEN."
    elif codigo == 132001:
        mensagem = (
            f"A Meta nao encontrou o template '{config.whatsapp_template}' "
            f"em {config.whatsapp_idioma}. Ele precisa estar APROVADO."
        )
    elif codigo == 131026:
        mensagem = "Este numero nao tem WhatsApp, ou nao pode receber mensagens."
    elif codigo == 131047:
        mensagem = "Fora da janela de 24h — so sai por template aprovado."

    return ErroWhatsapp(mensagem, detalhe=str(detalhe), codigo=codigo)


def _cliente() -> httpx.Client:
    """Isolado para o teste trocar o transporte sem tocar na rede."""
    return httpx.Client(timeout=config.whatsapp_timeout_s)


def subir_imagem(png: bytes, nome_arquivo: str, *, cliente: httpx.Client | None = None) -> str:
    """Sobe o PNG e devolve o media_id."""
    proprio = cliente is None
    cliente = cliente or _cliente()
    try:
        resposta = cliente.post(
            _url("media"),
            headers=_cabecalhos(),
            data={"messaging_product": "whatsapp", "type": "image/png"},
            files={"file": (nome_arquivo, png, "image/png")},
        )
        if resposta.status_code >= 400:
            raise _erro_da_meta(resposta)

        media_id = resposta.json().get("id")
        if not media_id:
            raise ErroWhatsapp("A Meta aceitou a imagem mas nao devolveu o id dela.")
        return media_id
    finally:
        if proprio:
            cliente.close()


def enviar_cartao(
    *,
    telefone: str,
    png: bytes,
    nome_arquivo: str,
    padrinho_nome: str,
    crianca_nome: str,
    cliente: httpx.Client | None = None,
) -> Enviado:
    """Sobe a arte e manda o template de agradecimento.

    O template precisa ter cabecalho de IMAGEM e dois {{1}} {{2}} no corpo,
    nesta ordem: nome do padrinho, nome da crianca.
    """
    if not configurado():
        raise ErroWhatsapp(
            "O envio pelo WhatsApp nao esta configurado "
            "(faltam WHATSAPP_TOKEN e WHATSAPP_PHONE_NUMBER_ID)."
        )

    if not telefone:
        raise ErroWhatsapp("Este padrinho nao tem WhatsApp cadastrado.")

    proprio = cliente is None
    cliente = cliente or _cliente()
    try:
        media_id = subir_imagem(png, nome_arquivo, cliente=cliente)

        corpo = {
            "messaging_product": "whatsapp",
            "to": telefone,
            "type": "template",
            "template": {
                "name": config.whatsapp_template,
                "language": {"code": config.whatsapp_idioma},
                "components": [
                    {
                        "type": "header",
                        "parameters": [{"type": "image", "image": {"id": media_id}}],
                    },
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": padrinho_nome},
                            {"type": "text", "text": crianca_nome},
                        ],
                    },
                ],
            },
        }

        resposta = cliente.post(_url("messages"), headers=_cabecalhos(), json=corpo)
        if resposta.status_code >= 400:
            raise _erro_da_meta(resposta)

        dados = resposta.json()
        mensagens = dados.get("messages") or []
        if not mensagens:
            raise ErroWhatsapp("A Meta respondeu sem o id da mensagem.")

        return Enviado(mensagem_id=mensagens[0].get("id", ""), telefone=telefone)
    finally:
        if proprio:
            cliente.close()
