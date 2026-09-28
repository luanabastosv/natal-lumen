"""Todos os modelos, reunidos para o Alembic enxergar o esquema completo."""

from app.models.acesso import (
    LogAtividade,
    Perfil,
    PerfilPermissao,
    Permissao,
    SessaoRevogada,
    TokenAcesso,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.models.apadrinhamento import (
    Apadrinhamento,
    EnvioCartao,
    Padrinho,
    Pagamento,
)
from app.models.financeiro import Compra, Recebimento
from app.models.logistica import Cartao, Kit
from app.models.operacao import (
    Cidade,
    Crianca,
    DiaEvento,
    Edicao,
    Grupo,
    Instituicao,
    InstituicaoDia,
)

__all__ = [
    # operacao
    "Cidade",
    "Edicao",
    "DiaEvento",
    "Instituicao",
    "InstituicaoDia",
    "Grupo",
    "Crianca",
    # apadrinhamento
    "Padrinho",
    "Apadrinhamento",
    "EnvioCartao",
    "Pagamento",
    # logistica
    "Cartao",
    "Kit",
    # financeiro
    "Compra",
    "Recebimento",
    # acesso
    "Usuario",
    "Perfil",
    "Permissao",
    "PerfilPermissao",
    "UsuarioEdicao",
    "UsuarioInstituicao",
    "TokenAcesso",
    "SessaoRevogada",
    "LogAtividade",
]
