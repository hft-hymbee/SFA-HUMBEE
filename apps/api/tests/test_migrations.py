from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, make_url, text

from humbee_sfa.core.db import Base

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def test_migrations_reproduce_the_orm_schema(postgres_url: str) -> None:
    server = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text("DROP DATABASE IF EXISTS migrations_check"))
        connection.execute(text("CREATE DATABASE migrations_check"))
    server.dispose()

    engine = create_engine(make_url(postgres_url).set(database="migrations_check"))
    try:
        with engine.begin() as connection:
            config = Config(str(ALEMBIC_INI))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

            context = MigrationContext.configure(
                connection,
                opts={
                    "compare_type": True,
                    "include_name": lambda name, type_, _: type_ != "table" or name in Base.metadata.tables,
                },
            )
            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()
