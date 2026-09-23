"""Insere instituicoes de exemplo. Rodar com: python seed.py"""

from database import Instituicao, SessionLocal, criar_tabelas

INSTITUICOES = [
    "Escola Municipal Sao Jose",
    "Creche Lar da Crianca",
    "Instituto Semear",
    "Abrigo Nossa Senhora",
    "Centro Comunitario Bom Pastor",
]


def main():
    criar_tabelas()
    db = SessionLocal()
    try:
        criadas = 0
        for nome in INSTITUICOES:
            # nome e unico: nao duplica se o script rodar mais de uma vez.
            if db.query(Instituicao).filter_by(nome=nome).first():
                continue
            db.add(Instituicao(nome=nome))
            criadas += 1

        db.commit()
        total = db.query(Instituicao).count()
        print(f"{criadas} instituicao(oes) inserida(s). Total na base: {total}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
