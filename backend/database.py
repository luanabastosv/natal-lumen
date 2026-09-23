"""Conexao com a base de dados e modelos (SQLAlchemy)."""

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

# Deixado em variavel de ambiente para trocar SQLite por PostgreSQL sem mexer no codigo.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cartoes.db")

# check_same_thread e exclusivo do SQLite: o FastAPI atende pedidos em varias threads.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Instituicao(Base):
    __tablename__ = "instituicoes"

    id = Column(Integer, primary_key=True)
    nome = Column(String(160), unique=True, nullable=False)

    cartoes = relationship("Cartao", back_populates="instituicao")


class Cartao(Base):
    __tablename__ = "cartoes"

    id = Column(Integer, primary_key=True)
    nome = Column(String(160), nullable=False)
    instituicao_id = Column(Integer, ForeignKey("instituicoes.id"), nullable=False)
    caminho_arquivo = Column(String(500), nullable=False)
    criado_em = Column(DateTime, default=datetime.now, nullable=False)

    instituicao = relationship("Instituicao", back_populates="cartoes")


def criar_tabelas():
    """Cria as tabelas que ainda nao existem."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependencia do FastAPI: uma sessao por pedido."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
