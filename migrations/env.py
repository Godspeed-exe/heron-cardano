from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool # type: ignore
from alembic import context # type: ignore
from dotenv import load_dotenv

from heron_app.db.database import Base
from heron_app.db.models import wallet, transaction, transaction_output, transaction_output_asset, minting_policies

load_dotenv()

config = context.config
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))

fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()