"""Hash e verificacao de senhas (Argon2).

A senha em claro nunca e gravada nem registrada em log.
"""

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()

TAMANHO_MINIMO_SENHA = 8


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def conferir(senha: str, senha_hash: str | None) -> bool:
    """Confere a senha. Falsa tambem quando o usuario ainda nao definiu uma."""
    if not senha_hash:
        return False
    try:
        return _hasher.verify(senha, senha_hash)
    except Exception:
        # Hash corrompido ou em formato desconhecido: nega o acesso.
        return False


def senha_fraca(senha: str) -> str | None:
    """Devolve o motivo de recusa, ou None se a senha serve."""
    if len(senha) < TAMANHO_MINIMO_SENHA:
        return f"A senha precisa de pelo menos {TAMANHO_MINIMO_SENHA} caracteres."
    if senha.isdigit():
        return "A senha nao pode ser so numeros."
    return None
