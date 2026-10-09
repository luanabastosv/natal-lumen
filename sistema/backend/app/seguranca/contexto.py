"""Contexto de acesso: o que este usuario pode ver e fazer, em que edicoes.

E aqui que mora o isolamento de dados exigido pela LGPD. Regras:

  - admin_geral alcanca tudo, em todas as cidades e edicoes;
  - os demais so alcancam as edicoes em que tem vinculo ATIVO;
  - a permissao e por edicao (o mesmo usuario pode ser coordenacao numa e
    comissario noutra), por isso as consultas sao filtradas pelas edicoes em
    que ele tem AQUELA permissao, e nao por todas as suas edicoes;
  - comissarios e monitores ainda sao limitados as instituicoes atribuidas;
  - o comissario e limitado mais uma vez, crianca a crianca: so alcanca as
    que estao atribuidas a ele em criancas.comissario_id.
"""

from dataclasses import dataclass, field

from sqlalchemy import ColumnElement, false, or_, true
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from app.models import Crianca, Perfil, Usuario, UsuarioEdicao
from app.seeds.perfis_permissoes import (
    PERFIL_COORDENACAO,
    PERFIS_FILTRADOS_POR_CRIANCA,
    PERFIS_FILTRADOS_POR_INSTITUICAO,
)


@dataclass(frozen=True)
class Vinculo:
    """O vinculo ativo do usuario com uma edicao."""

    edicao_id: int
    perfil: str
    permissoes: frozenset[str]
    instituicoes: frozenset[int] = field(default_factory=frozenset)

    @property
    def filtrado_por_instituicao(self) -> bool:
        return self.perfil in PERFIS_FILTRADOS_POR_INSTITUICAO

    @property
    def filtrado_por_crianca(self) -> bool:
        return self.perfil in PERFIS_FILTRADOS_POR_CRIANCA


@dataclass(frozen=True)
class ContextoAcesso:
    usuario: Usuario
    vinculos: tuple[Vinculo, ...]

    @property
    def admin_geral(self) -> bool:
        return self.usuario.admin_geral

    # ------------------------------------------------------------ permissoes

    def pode(self, permissao: str) -> bool:
        """Tem a permissao em pelo menos uma edicao (ou e admin_geral)."""
        if self.admin_geral:
            return True
        return any(permissao in v.permissoes for v in self.vinculos)

    @property
    def permissoes(self) -> set[str]:
        """Uniao das permissoes, so para o frontend esconder menus.

        A decisao real acontece sempre no backend, por edicao.
        """
        if self.admin_geral:
            from app.seeds.perfis_permissoes import PERMISSOES

            return set(PERMISSOES)
        return {p for v in self.vinculos for p in v.permissoes}

    def edicoes_com(self, permissao: str) -> list[int]:
        """Edicoes em que o usuario tem esta permissao.

        Lista vazia com admin_geral falso significa: nao alcanca nada.
        Para admin_geral use `alcanca_todas_edicoes` antes de aplicar filtro.
        """
        return [v.edicao_id for v in self.vinculos if permissao in v.permissoes]

    @property
    def alcanca_todas_edicoes(self) -> bool:
        return self.admin_geral

    @property
    def edicoes(self) -> list[int]:
        return [v.edicao_id for v in self.vinculos]

    # --------------------------------------------------------------- filtros

    def filtro_criancas(self, permissao: str = "ver_criancas") -> ColumnElement[bool]:
        """Condicao SQL que limita as criancas que este usuario alcanca.

        Aplica os tres niveis: edicao; para comissario e monitor, tambem as
        instituicoes atribuidas; e, so para o comissario, a propria crianca.
        Usar em toda consulta de criancas.
        """
        if self.admin_geral:
            return true()

        condicoes = []
        for vinculo in self.vinculos:
            if permissao not in vinculo.permissoes:
                continue

            if not vinculo.filtrado_por_instituicao:
                condicoes.append(Crianca.edicao_id == vinculo.edicao_id)
                continue

            # Comissario ou monitor sem instituicao atribuida nao ve nenhuma
            # crianca daquela edicao — de proposito: o vinculo existe, mas o
            # coordenador ainda nao definiu por quais instituicoes ele responde.
            if not vinculo.instituicoes:
                continue

            alcance = (Crianca.edicao_id == vinculo.edicao_id) & (
                Crianca.instituicao_id.in_(vinculo.instituicoes)
            )

            # O comissario nao alcanca a lista inteira da instituicao: dentro
            # dela, so as criancas atribuidas a ele. A instituicao continua
            # valendo como cerca externa — atribuicao em instituicao que saiu
            # do vinculo dele para de valer na hora.
            if vinculo.filtrado_por_crianca:
                alcance = alcance & (Crianca.comissario_id == self.usuario.id)

            condicoes.append(alcance)

        return or_(*condicoes) if condicoes else false()

    def alcanca_edicao(self, edicao_id: int, permissao: str) -> bool:
        if self.admin_geral:
            return True
        return any(
            v.edicao_id == edicao_id and permissao in v.permissoes for v in self.vinculos
        )

    def e_coordenacao_geral(self, edicao_id: int) -> bool:
        """Se, nesta edicao, o usuario e a coordenacao geral do evento (ou a
        administracao geral).

        Pelo NOME do perfil, e nao por permissao: a coordenacao da captacao
        tem quase as mesmas permissoes, e ha telas (o lembrete aos padrinhos,
        a lista de cuidados especiais) que sao so de quem responde pelo evento
        inteiro.
        """
        if self.admin_geral:
            return True
        return any(v.edicao_id == edicao_id and v.perfil == PERFIL_COORDENACAO for v in self.vinculos)

    def so_proprias_criancas(self, edicao_id: int) -> bool:
        """Se, nesta edicao, o usuario so alcanca as criancas atribuidas a ele.

        E o comissario. Quem pergunta e o painel, para falar dos numeros DELE
        em vez dos da edicao — sem precisar saber qual perfil e filtrado assim.
        """
        if self.admin_geral:
            return False
        return any(
            v.edicao_id == edicao_id and v.filtrado_por_crianca for v in self.vinculos
        )

    def alcanca_instituicao(self, edicao_id: int, instituicao_id: int) -> bool:
        """Se a instituicao esta no alcance do usuario naquela edicao."""
        if self.admin_geral:
            return True
        for vinculo in self.vinculos:
            if vinculo.edicao_id != edicao_id:
                continue
            if not vinculo.filtrado_por_instituicao:
                return True
            return instituicao_id in vinculo.instituicoes
        return False


def montar_contexto(db: Session, usuario: Usuario) -> ContextoAcesso:
    """Le os vinculos ativos do usuario e monta o contexto."""
    vinculos_db = db.scalars(
        select(UsuarioEdicao)
        .where(UsuarioEdicao.usuario_id == usuario.id, UsuarioEdicao.ativo.is_(True))
        .options(
            # As permissoes vem junto: sem isto seria uma consulta por vinculo.
            selectinload(UsuarioEdicao.perfil).selectinload(Perfil.permissoes),
            selectinload(UsuarioEdicao.instituicoes),
        )
    ).all()

    vinculos = tuple(
        Vinculo(
            edicao_id=v.edicao_id,
            perfil=v.perfil.nome,
            permissoes=frozenset(p.codigo for p in v.perfil.permissoes),
            instituicoes=frozenset(
                i.instituicao_id for i in v.instituicoes if i.ativo
            ),
        )
        for v in vinculos_db
    )

    return ContextoAcesso(usuario=usuario, vinculos=vinculos)
