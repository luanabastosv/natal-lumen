"""Conexao com a base de dados e a classe Base dos modelos."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import config

engine = create_engine(config.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base de todos os modelos. As tabelas sao criadas por migration do Alembic."""


def get_db() -> Generator[Session, None, None]:
    """Dependencia do FastAPI: uma sessao por pedido."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
