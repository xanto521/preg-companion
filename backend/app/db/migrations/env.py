from alembic import context

from app.config import Settings
from app.db.connection import create_sqlite_engine, sqlite_url
from app.db.models import Base

settings = Settings()

if context.is_offline_mode():
    context.configure(
        url=sqlite_url(settings.database_path),
        target_metadata=Base.metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_sqlite_engine(settings.database_path)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
                render_as_batch=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
