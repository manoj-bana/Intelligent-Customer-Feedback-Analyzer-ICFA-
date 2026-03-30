"""
conftest.py – pytest configuration for ICFA test suite.

Uses a StaticPool in-memory SQLite database so that all sessions share the
same single connection (critical for SQLite :memory: databases).
"""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.models import Base

# ── Create a single shared in-memory engine ──
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(bind=_test_engine)

Base.metadata.create_all(bind=_test_engine)

# ── Patch backend modules before any test ──
import backend.database.db as db_module
db_module.engine = _test_engine
db_module.SessionLocal = _TestSessionLocal

import backend.auth as auth_module
auth_module.SessionLocal = _TestSessionLocal

import backend.routes.ingest as ingest_module
ingest_module.SessionLocal = _TestSessionLocal

@pytest.fixture(autouse=True)
def reset_state_between_tests():
    """Truncate DB tables before each test."""
    with _test_engine.connect() as conn:
        for table in ["users", "feedback", "churn_predictions", "datasets"]:
            try:
                conn.execute(text(f"DELETE FROM {table}"))
            except Exception:
                pass
        conn.commit()

    yield


@pytest.fixture
def client():
    """FastAPI TestClient for integration tests."""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def registered_user(client):
    """Register a test user and return credentials."""
    creds = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "Test@1234",
        "security_question": "Pet name?",
        "security_answer": "fluffy"
    }
    client.post("/auth/register", json=creds)
    return creds
