"""A senha pedida de novo antes de uma acao que nao tem volta.

Apagar uma edicao (ou uma cidade, que leva as edicoes junto) apaga um ano
inteiro de trabalho: criancas, padrinhos, pagamentos, cartoes. A sessao
aberta nao basta — o computador pode estar desbloqueado na mesa de outra
pessoa. Quem apaga digita a propria senha de novo, e a conferencia e aqui,
no servidor: a janela da tela so pergunta.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.seguranca.contexto import ContextoAcesso
from app.seguranca.senhas import conferir
from app.servicos.log import registrar


def exigir_senha(db: Session, ctx: ContextoAcesso, senha: str | None, acao: str) -> None:
    """Recusa (403) se a senha nao for a de quem esta pedindo.

    A tentativa errada fica no log com a acao que se tentava, para quem for
    auditar achar a sequencia.
    """
    if conferir(senha or "", ctx.usuario.senha_hash):
        return
    registrar(
        db, "reconfirmacao_recusada", usuario_id=ctx.usuario.id,
        detalhes={"acao": acao},
    )
    db.commit()
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "Senha incorreta. Para apagar, digite a sua senha de acesso ao sistema.",
    )
