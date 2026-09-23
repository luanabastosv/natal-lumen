"""Todos os modelos, reunidos para o Alembic enxergar o esquema completo."""

from app.models.acesso import (
    LogAtividade,
    Perfil,
    PerfilPermissao,
    Permissao,
    TokenAcesso,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.models.apadrinhamento import Apadrinhamento, Padrinho, Pagamento
from app.models.logistica import Cartao, Compra, Kit
from app.models.operacao import Cidade, Crianca, DiaEvento, Edicao, Instituicao

__all__ = [
    # operacao
    "Cidade",
    "Edicao",
    "DiaEvento",
    "Instituicao",
    "Crianca",
    # apadrinhamento
    "Padrinho",
    "Apadrinhamento",
    "Pagamento",
    # logistica
    "Cartao",
    "Kit",
    "Compra",
    # acesso
    "Usuario",
    "Perfil",
    "Permissao",
    "PerfilPermissao",
    "UsuarioEdicao",
    "UsuarioInstituicao",
    "TokenAcesso",
    "LogAtividade",
]
