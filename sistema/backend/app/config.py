"""Configuracao lida do .env (nada de valores sensiveis no codigo)."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Tres ambientes, nesta ordem de rigor:
#   desenvolvimento  seu computador. HTTP em localhost, CORS para o Vite,
#                    /docs aberta, link de redefinir senha volta na resposta.
#   homologacao      servidor de teste. HTTPS de verdade, CORS desligado,
#                    /docs aberta (e util para testar), dados anonimizados.
#   producao         o que vale. HTTPS, sem CORS, sem /docs, sem atalho nenhum.
AMBIENTES = ("desenvolvimento", "homologacao", "producao")

BASE_DIR = Path(__file__).resolve().parent.parent


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Base de dados ---
    database_url: str

    # --- Arquivos enviados ---
    # Fica fora das pastas publicas do frontend: nada aqui e servido diretamente,
    # so por rota autenticada que confere permissao e edicao.
    arquivos_dir: Path = Path("../arquivos")

    # --- Sessao e seguranca ---
    jwt_secret: str
    jwt_algoritmo: str = "HS256"
    # Sessao curta de proposito. Quem esta usando o sistema nao percebe: o
    # token e renovado sozinho quando falta pouco (ver renovar_faltando_minutos).
    sessao_horas: int = 4
    renovar_faltando_minutos: int = 60
    token_primeiro_acesso_horas: int = 72
    max_tentativas_falhas: int = 5
    bloqueio_minutos: int = 15

    cookie_nome: str = "nl_sessao"
    # Cookie legivel pelo frontend, com o token CSRF (o da sessao e httpOnly).
    cookie_csrf: str = "nl_csrf"
    cookie_path: str = "/acesso"

    # --- Uploads ---
    # A aplicacao le o arquivo inteiro na memoria (foto do cartao, planilha
    # para a importacao). Sem teto, um arquivo gigante derruba o servidor —
    # e nao da para confiar so no limite do nginx.
    max_upload_mb: int = 15

    # --- WhatsApp Cloud API (Meta) ---
    # Vazio = desligado: o sistema segue oferecendo o download manual do
    # cartao e a rota de envio responde dizendo o que falta configurar.
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    # Nome do template APROVADO na Meta. Mensagem iniciada pelo negocio so
    # sai por template aprovado — texto livre a Meta recusa.
    whatsapp_template: str = "cartao_agradecimento"
    whatsapp_idioma: str = "pt_BR"
    # A Meta aposenta versoes da Graph API: da para subir sem mexer no codigo.
    whatsapp_versao_api: str = "v21.0"
    whatsapp_timeout_s: float = 30.0

    # --- Google Drive (comprovantes de pagamento) ---
    # Caminho do JSON da conta de servico, ou o JSON inteiro colado aqui.
    drive_credenciais: str = ""
    # Id da pasta DENTRO de um Drive Compartilhado. Pasta do "Meu Drive" nao
    # serve: la o arquivo fica sendo propriedade da conta de servico, que nao
    # tem cota, e o upload morre com storageQuotaExceeded.
    drive_pasta_id: str = ""
    drive_timeout_s: float = 60.0

    # --- Publicacao ---
    ambiente: str = "desenvolvimento"
    root_path: str = "/acesso/api"

    @property
    def whatsapp_ligado(self) -> bool:
        """So envia se as duas credenciais estiverem preenchidas."""
        return bool(self.whatsapp_token and self.whatsapp_phone_number_id)

    @property
    def drive_ligado(self) -> bool:
        """So sobe para o Drive com credencial E pasta de destino."""
        return bool(self.drive_credenciais and self.drive_pasta_id)

    @field_validator("ambiente")
    @classmethod
    def _ambiente_conhecido(cls, valor: str) -> str:
        """Recusa valor desconhecido em vez de cair no modo mais frouxo.

        Sem isto, um `AMBIENTE=prod` ou `AMBIENTE=produção` (com cedilha) nao
        casaria com nada, `em_producao` daria False, e o servidor subiria com
        cookie sem Secure e /docs aberta — em silencio, parecendo bem.
        """
        limpo = valor.strip().lower()
        if limpo not in AMBIENTES:
            raise ValueError(
                f"AMBIENTE={valor!r} nao existe. Use um de: {', '.join(AMBIENTES)}."
            )
        return limpo

    @property
    def em_producao(self) -> bool:
        return self.ambiente == "producao"

    @property
    def em_servidor(self) -> bool:
        """Homologacao e producao: os dois atendem por HTTPS, num dominio."""
        return self.ambiente in ("homologacao", "producao")

    @property
    def mostra_link_de_senha(self) -> bool:
        """So no seu computador.

        Em desenvolvimento nao ha servidor de email, entao o link de definir
        senha volta na propria resposta. Num servidor isso seria tomada de
        conta por quem souber um email — inclusive em homologacao, que tem
        dominio publico.
        """
        return self.ambiente == "desenvolvimento"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cookie_secure(self) -> bool:
        """Secure exige HTTPS, o que quebraria o desenvolvimento em localhost."""
        return self.em_servidor

    @property
    def origens_permitidas(self) -> list[str]:
        """No servidor o frontend vem do mesmo dominio: nao precisa de CORS."""
        if self.em_servidor:
            return []
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def caminho_arquivos(self) -> Path:
        """arquivos_dir resolvido a partir da pasta do backend."""
        caminho = self.arquivos_dir
        if not caminho.is_absolute():
            caminho = (BASE_DIR / caminho).resolve()
        return caminho


@lru_cache
def obter_config() -> Config:
    """Cache para o .env ser lido uma unica vez."""
    return Config()  # type: ignore[call-arg]


config = obter_config()
