"""Configuracao lida do .env (nada de valores sensiveis no codigo)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

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
    # A aplicacao le o arquivo inteiro na memoria (foto para o OCR, planilha
    # para a importacao). Sem teto, um arquivo gigante derruba o servidor —
    # e nao da para confiar so no limite do nginx.
    max_upload_mb: int = 15

    # --- OCR dos cartoes ---
    # Carregar o EasyOCR leva ~30s. Em producao vale a pena fazer isso no
    # arranque, para o primeiro monitor do dia nao esperar. Em desenvolvimento
    # fica sob demanda, senao cada reload do uvicorn custaria meio minuto.
    carregar_ocr_ao_iniciar: bool | None = None

    # --- Publicacao ---
    ambiente: str = "desenvolvimento"
    root_path: str = "/acesso/api"

    @property
    def em_producao(self) -> bool:
        return self.ambiente == "producao"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def aquecer_ocr(self) -> bool:
        if self.carregar_ocr_ao_iniciar is not None:
            return self.carregar_ocr_ao_iniciar
        return self.em_producao

    @property
    def cookie_secure(self) -> bool:
        """Secure exige HTTPS, o que quebraria o desenvolvimento em localhost."""
        return self.em_producao

    @property
    def origens_permitidas(self) -> list[str]:
        """Em producao o frontend e servido do mesmo dominio: nao precisa de CORS."""
        if self.em_producao:
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
