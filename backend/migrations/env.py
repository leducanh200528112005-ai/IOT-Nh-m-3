from alembic import context
from sqlalchemy import create_engine, pool

from app.config import Settings
from app.models import Base

if context.is_offline_mode():
    context.configure(url=Settings().database_url.render_as_string(hide_password=False), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(Settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
