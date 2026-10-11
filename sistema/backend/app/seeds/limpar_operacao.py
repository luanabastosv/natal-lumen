"""Apaga o que foi lancado TESTANDO numa edicao, para ela comecar do zero.

Feito para o lancamento de 13/10/2026: o servidor que era de teste virou o de
producao, e carregava padrinhos, pagamentos, cartoes, compras e kits lancados
so para ver as telas funcionando. O cadastro fica — cidade, edicao,
instituicoes, criancas, usuarios — e o resto volta a zero.

    python -m app.seeds.limpar_operacao --edicao 1               explica e sai
    python -m app.seeds.limpar_operacao --edicao 1 --sim "Fortaleza 2026"

O `--sim` exige o NOME da edicao, escrito igual: apagar a operacao de uma
edicao em uso nao tem volta, e um id digitado errado nao pode bastar.

Apaga, nesta ordem: apadrinhamentos, pagamentos (e os comprovantes no disco),
padrinhos, envios de agradecimento, cartoes (e as imagens), compras, kits.
Os arquivos do disco saem DEPOIS do commit — se o banco falhar, nada some.
As copias no Drive nao sao tocadas: a conta do sistema so cria, nunca apaga.
"""

import argparse

from sqlalchemy import delete, func, select

from app.database import SessionLocal
from app.models import (
    Apadrinhamento,
    Cartao,
    Compra,
    Crianca,
    Edicao,
    EnvioCartao,
    Kit,
    Padrinho,
    Pagamento,
)
from app.servicos import comprovantes, imagens
from app.servicos.log import registrar


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--edicao", type=int, required=True)
    args.add_argument("--sim", metavar="NOME_DA_EDICAO")
    opcoes = args.parse_args()

    db = SessionLocal()
    edicao = db.get(Edicao, opcoes.edicao)
    if edicao is None:
        raise SystemExit(f"Edicao {opcoes.edicao} nao existe.")

    padrinhos = select(Padrinho.id).where(Padrinho.edicao_id == edicao.id)
    criancas = select(Crianca.id).where(Crianca.edicao_id == edicao.id)
    alvos = [
        ("apadrinhamentos", Apadrinhamento, Apadrinhamento.padrinho_id.in_(padrinhos)),
        ("pagamentos", Pagamento, Pagamento.padrinho_id.in_(padrinhos)),
        ("envios de agradecimento", EnvioCartao,
         EnvioCartao.apadrinhamento_id.in_(
             select(Apadrinhamento.id).where(Apadrinhamento.padrinho_id.in_(padrinhos))
         )),
        ("padrinhos", Padrinho, Padrinho.edicao_id == edicao.id),
        ("cartoes", Cartao, Cartao.crianca_id.in_(criancas)),
        ("compras", Compra, Compra.edicao_id == edicao.id),
        ("kits", Kit, Kit.crianca_id.in_(criancas)),
    ]

    print(f"Edicao: {edicao.nome} (id {edicao.id})")
    contagem = {}
    for nome, modelo, condicao in alvos:
        contagem[nome] = db.scalar(select(func.count()).select_from(modelo).where(condicao))
        print(f"  {nome:26} {contagem[nome]}")

    if opcoes.sim != edicao.nome:
        print(f'\nNada foi apagado. Para apagar: --sim "{edicao.nome}"')
        return

    # Os caminhos saem antes, enquanto as linhas existem.
    arquivos_pagamento = db.scalars(
        select(Pagamento.comprovante_arquivo).where(
            Pagamento.padrinho_id.in_(padrinhos), Pagamento.comprovante_arquivo.is_not(None)
        )
    ).all()
    arquivos_cartao = db.scalars(select(Cartao.arquivo).where(Cartao.crianca_id.in_(criancas))).all()

    # Envios antes dos apadrinhamentos: a condicao deles depende dos
    # apadrinhamentos ainda existirem.
    ordem = ["envios de agradecimento", "apadrinhamentos", "pagamentos", "padrinhos",
             "cartoes", "compras", "kits"]
    por_nome = {nome: (modelo, condicao) for nome, modelo, condicao in alvos}
    for nome in ordem:
        modelo, condicao = por_nome[nome]
        db.execute(delete(modelo).where(condicao).execution_options(synchronize_session=False))

    registrar(
        db, "operacao_da_edicao_limpa", tabela="edicoes", registro_id=edicao.id,
        detalhes={"apagados": contagem},
    )
    db.commit()

    for caminho in arquivos_pagamento:
        comprovantes.apagar_arquivo(caminho)
    for caminho in arquivos_cartao:
        imagens.apagar_do_disco(caminho)

    print(f"\nApagado. {len(arquivos_pagamento)} comprovante(s) e "
          f"{len(arquivos_cartao)} imagem(ns) de cartao sairam do disco.")


if __name__ == "__main__":
    main()
