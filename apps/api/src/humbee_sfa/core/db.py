"""Database metadata, engine/session setup, and cross-cutting safeguards."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from humbee_sfa.core.settings import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class HardDeleteNotAllowedError(RuntimeError):
    """Raised when a hard-delete is attempted in ORM session."""


@event.listens_for(Session, "before_flush")
def _prevent_hard_delete(session: Session, _flush_context: object, _instances: object) -> None:
    if session.deleted:
        raise HardDeleteNotAllowedError(
            "Hard delete is forbidden. Use soft-delete fields (is_active/deactivated_at/deactivated_by)."
        )


@lru_cache(maxsize=8)
def get_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    url = database_url or settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, future=True, connect_args=connect_args)


@lru_cache(maxsize=8)
def get_sessionmaker(database_url: str | None = None) -> sessionmaker[Session]:
    engine = get_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def reset_db_caches() -> None:
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@contextmanager
def transaction(
    session: Session,
    *,
    commit_on: type[BaseException] | tuple[type[BaseException], ...] = (),
) -> Iterator[None]:
    """One transaction per state transition, owned by the service rather than the router.

    Commits on success, rolls back on anything else. `commit_on` names exception types that
    should commit and still propagate — a rejected attempt is often a state transition in its
    own right, and the attempt counter or audit row written before the rejection has to survive
    it. Pass `commit_on=ApiError` for that; the default commits only on success.
    """

    try:
        yield
        session.commit()
    except commit_on:
        session.commit()
        raise
    except Exception:
        session.rollback()
        raise


def end_read_transaction(session: Session) -> None:
    """Close the implicit transaction a preceding read opened, before a network wait.

    SQLAlchemy begins a transaction on the first statement and holds it until commit or rollback,
    so a service that reads its own state and then calls an upstream provider would keep that
    transaction — and its locks — open for the whole round trip. Nothing has been written at this
    point, so discarding is the correct close; the caller re-reads under a fresh transaction before
    it writes.
    """

    session.rollback()


def get_db_session() -> Generator[Session, None, None]:
    session_factory = get_sessionmaker()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
