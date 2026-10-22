from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime

import httpx
import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

os.environ["HUMBEE_SFA_PROFILE"] = "test"
os.environ["HUMBEE_SFA_DATABASE_URL"] = "postgresql+psycopg://unset@localhost/unset"
os.environ["HUMBEE_SFA_OTP_SMS_USERNAME"] = ""
os.environ["HUMBEE_SFA_OTP_SMS_API_KEY"] = ""
os.environ["HUMBEE_API_KEY"] = "test-api-key"
os.environ["HUMBEE_SFA_JWT_SECRET"] = "test-jwt-secret-with-at-least-32-bytes"
os.environ["HUMBEE_SFA_PHONE_HMAC_SECRET"] = "test-phone-hmac-secret"
os.environ["HUMBEE_SFA_PHONE_ENC_KEY"] = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="

from tests.fakes.humbee import FakeHumbee

from humbee_sfa.core.db import Base, get_db_session
from humbee_sfa.core.settings import get_settings, reset_settings_cache
from humbee_sfa.integration.humbee import client as humbee_client
from humbee_sfa.main import app

NOW = datetime(2026, 10, 19, 4, 30, tzinfo=UTC)


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str, None, None]:
    with PostgresContainer("postgis/postgis:16-3.4-alpine") as postgres:
        url = postgres.get_connection_url()
        url = url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
        yield url.replace("postgresql://", "postgresql+psycopg://", 1)


@pytest.fixture(scope="session")
def postgres_engine(postgres_url: str) -> Generator[Engine, None, None]:
    os.environ["HUMBEE_SFA_DATABASE_URL"] = postgres_url
    reset_settings_cache()
    engine = create_engine(postgres_url, future=True)
    with engine.begin() as connection:
        for extension in ("postgis", "btree_gist", "ltree"):
            connection.execute(text(f"CREATE EXTENSION IF NOT EXISTS {extension}"))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(postgres_engine: Engine) -> Generator[Session, None, None]:
    connection = postgres_engine.connect()
    outer = connection.begin()
    session = sessionmaker(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )()
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture()
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db_session] = lambda: db_session
    try:
        with TestClient(app, client=("127.0.0.1", 50000)) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def travel() -> Generator[time_machine.Coordinates, None, None]:
    with time_machine.travel(NOW, tick=True) as traveller:
        yield traveller


@pytest.fixture(autouse=True)
def humbee(monkeypatch: pytest.MonkeyPatch) -> Generator[FakeHumbee, None, None]:
    fake = FakeHumbee()
    humbee_client.reset_humbee_client()
    client = humbee_client.get_humbee_client(get_settings())
    client._http = httpx.Client(transport=httpx.MockTransport(fake.handle))
    monkeypatch.setattr(humbee_client, "_sleep_with_jitter", lambda attempt: None)
    yield fake
    humbee_client.reset_humbee_client()
    assert fake.unrouted == [], f"FakeHumbee received unrouted calls: {fake.unrouted}"
