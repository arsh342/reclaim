"""Shared pytest fixtures.

Tests run against the live Supabase database using per-test schemas
(`test_<random>`) so they don't collide with each other or with live
data. Each test creates the schema, runs against it, then drops it on
teardown.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.api.main import app
from backend.config import get_settings
from backend.db import session as db_session


@pytest.fixture(autouse=True)
def isolated_schema(monkeypatch):
    """Create a fresh Postgres schema per test, point the app at it, drop on exit."""
    settings = get_settings()
    schema_name = f"test_{uuid.uuid4().hex[:12]}"

    admin_engine = create_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    monkeypatch.setenv("DATABASE_SCHEMA", schema_name)

    test_engine = create_engine(
        settings.database_url,
        connect_args={"options": f"-c search_path={schema_name},public"},
        pool_pre_ping=True,
    )

    with test_engine.connect() as conn:
        for stmt in _schema_statements():
            conn.execute(text(stmt))
        conn.commit()

    monkeypatch.setattr(db_session, "engine", test_engine)
    TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(db_session, "SessionLocal", TestSession)

    yield test_engine

    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
    admin_engine.dispose()
    test_engine.dispose()


def _schema_statements() -> list[str]:
    """Read backend/db/schema.sql and split into statements (no IF NOT EXISTS for policies)."""
    sql_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
    with open(sql_path) as f:
        raw = f.read()

    statements: list[str] = []
    buf: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buf).rstrip(";"))
            buf = []
    return [s for s in statements if s.strip()]


@pytest.fixture
def db(monkeypatch):
    """A clean Session bound to the per-test schema."""
    from backend.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(monkeypatch):
    """A TestClient with the per-test schema's DB session injected."""
    from backend.db import session as db_session

    def _override_get_db():
        s = db_session.SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[db_session.get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
