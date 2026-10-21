"""Use the same environment configuration as the application."""

from alembic import context

from tactix.persistence.database import build_engine
from tactix.persistence.models import Base

if context.is_offline_mode():
    from tactix.config import Settings

    context.configure(
        url=Settings().database_url, target_metadata=Base.metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = build_engine()
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
