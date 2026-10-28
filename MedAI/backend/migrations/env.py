from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text

import app.models  # noqa: F401  (registers all tables)
from app.core.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return config.attributes.get("database_url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _url()
    is_sqlite = url.startswith("sqlite")
    # Deliberately NOT app.db.session.build_engine: the app enables SQLite foreign keys on every
    # connection, and SQLite "batch" migrations rebuild a table by DROP + RENAME. With foreign keys
    # on, dropping e.g. `users` fires ON DELETE CASCADE and silently deletes every dependent row.
    connectable = create_engine(url, connect_args={"check_same_thread": False} if is_sqlite else {})
    with connectable.connect() as connection:
        if is_sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")  # must run outside a transaction
            connection.commit()
        # render_as_batch lets ALTER TABLE migrations work on SQLite as well as PostgreSQL.
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        if is_sqlite:
            violations = connection.execute(text("PRAGMA foreign_key_check")).fetchall()
            if violations:
                raise RuntimeError(f"Foreign-key violations after migration: {violations[:5]}")
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
