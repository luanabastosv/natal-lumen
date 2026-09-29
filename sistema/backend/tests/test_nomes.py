"""Testa a grafia dos nomes de pessoa (servicos/nomes.py).

Nao toca no banco: a regra e so texto, e cada caso aqui saiu de uma lista de
instituicao de verdade.

Rodar com:  python -m tests.test_nomes
"""

from app.servicos.nomes import nome_proprio

ok = 0
falhas: list[str] = []


def verifica(d: str, c: bool, extra: str = "") -> None:
    global ok
    if c:
        ok += 1
        print(f"  ok    {d}")
    else:
        falhas.append(d)
        print(f"  FALHA {d} {extra}")


def igual(d: str, entrada, esperado: str) -> None:
    obtido = nome_proprio(entrada)
    verifica(d, obtido == esperado, f"(esperava {esperado!r}, veio {obtido!r})")


def main() -> None:
    print("\nO caps lock das listas das instituicoes")
    igual("a lista inteira em caixa alta desce",
          "MARIA ELISE SOUSA SILVA", "Maria Elise Sousa Silva")
    igual("os ligadores ficam em minuscula",
          "MELISSA KIMBERLLY DE SOUZA ANJO", "Melissa Kimberlly de Souza Anjo")
    igual("e todos eles, nao so o 'de'",
          "ANA DAS DORES DOS SANTOS E SILVA", "Ana das Dores dos Santos e Silva")
    igual("o acento sobrevive a troca de caixa",
          "LUÍS INÁCIO DA CONCEIÇÃO", "Luís Inácio da Conceição")

    print("\nO que chega torto do outro lado")
    igual("tudo em minuscula sobe", "joão pedro alves", "João Pedro Alves")
    igual("caixa embaralhada se refaz", "mARIA cLARA", "Maria Clara")
    igual("espacos repetidos e das pontas somem", "  ANA   CLARA  ", "Ana Clara")
    igual("nome ja certo nao muda", "Maria da Silva", "Maria da Silva")

    print("\nNomes que nao sao so palavras soltas")
    igual("o hifen separa dois nomes", "ANA-MARIA DE SOUZA", "Ana-Maria de Souza")
    igual("o apostrofo tambem", "MARIA D'ÁVILA", "Maria D'Ávila")
    igual("inclusive no meio da palavra", "SANT'ANA", "Sant'Ana")
    igual("a inicial abreviada continua inicial", "maria a. souza", "Maria A. Souza")

    print("\nAs pontas")
    igual("nome vazio nao vira nada", "", "")
    igual("sem nome nenhum tambem nao", None, "")
    igual("so espacos nao viram nome", "   ", "")
    igual("uma palavra so", "ÁGATA", "Ágata")
    # "da Silva" pareceria erro de digitacao numa lista.
    igual("ligador na frente e maiusculo", "DA SILVA", "Da Silva")

    print("\nPassar de novo nao muda nada")
    uma_vez = nome_proprio("MARIA DAS GRAÇAS D'ÁVILA-SOUZA")
    verifica("a regra e idempotente", nome_proprio(uma_vez) == uma_vez, uma_vez)

    print(f"\n{ok} verificacoes ok, {len(falhas)} falha(s)")
    if falhas:
        for f in falhas:
            print("  -", f)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
