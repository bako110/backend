from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, create_engine
from alembic import context

# Import de ton Base SQLAlchemy pour récupérer la MetaData
from app.db.session import Base
# Import de la classe User si besoin (optionnel)
from app.auth.models import User  

target_metadata = Base.metadata

# Chargement config Alembic
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    # Transformer URL async en URL sync (enlever +asyncpg)
    url_sync = url.replace("postgresql+asyncpg://", "postgresql://")

    context.configure(
        url=url_sync,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    url_sync = url.replace("postgresql+asyncpg://", "postgresql://")

    connectable = create_engine(
        url_sync,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
