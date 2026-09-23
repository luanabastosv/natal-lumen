"""Cria a primeira conta de administracao geral.

Sem isto ninguem consegue entrar: o sistema nao tem cadastro aberto, e as contas
dos voluntarios sao criadas pela coordenacao ja de dentro.

A conta nasce SEM senha. O comando imprime um link de primeiro acesso, de uso
unico, valido por 72 horas, em que a pessoa define a propria senha — a senha
nunca passa por aqui nem fica em historico de terminal.

Rodar com:
    python -m app.seeds.criar_admin "Nome da Pessoa" email@exemplo.org

Se a conta ja existir, gera um link novo em vez de duplicar.
"""

import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Usuario
from app.models.tipos import TipoToken
from app.servicos import tokens_acesso
from app.servicos.log import registrar


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(1)

    nome = sys.argv[1].strip()
    email = sys.argv[2].strip().lower()

    if "@" not in email:
        print(f"Email invalido: {email}")
        raise SystemExit(1)

    db = SessionLocal()
    try:
        usuario = db.scalar(select(Usuario).where(Usuario.email == email))

        if usuario is None:
            usuario = Usuario(nome=nome, email=email, admin_geral=True)
            db.add(usuario)
            db.flush()
            registrar(
                db, "admin_criado", usuario_id=usuario.id,
                tabela="usuarios", registro_id=usuario.id,
            )
            print(f"Conta criada: {nome} <{email}>")
        else:
            if not usuario.admin_geral:
                usuario.admin_geral = True
                print(f"Conta existente promovida a admin_geral: {email}")
            else:
                print(f"Conta ja existia: {email}")
            # Um link novo destrava quem perdeu o anterior ou ficou bloqueado.
            usuario.ativo = True
            usuario.bloqueado_ate = None
            usuario.tentativas_falhas = 0

        token = tokens_acesso.gerar(db, usuario, TipoToken.PRIMEIRO_ACESSO)
        db.commit()

        print()
        print("Link de primeiro acesso (uso unico, vale 72 horas):")
        print(f"  /acesso/definir-senha?token={token}")
        print()
        print("Em producao, o endereco completo fica:")
        print(f"  https://DOMINIO/acesso/definir-senha?token={token}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
