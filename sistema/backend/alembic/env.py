"""Ambiente do Alembic.

A URL da base vem do .env (app.config), nunca do alembic.ini — assim producao e
desenvolvimento usam o mesmo arquivo de migrations sem editar nada.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import config as config_app

# Importar app.models registra as 19 tabelas em Base.metadata, que e o que o
# autogenerate compara com a base real.
import app.models  # noqa: F401
from app.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", config_app.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Gera o SQL sem ligar a base (alembic upgrade --sql)."""
    context.configure(
        url=config_app.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrations ligando a base."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
