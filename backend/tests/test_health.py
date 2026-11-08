"""Health endpoint database checks."""

from fastapi.testclient import TestClient

from app.main import app


class _FailingSessionMaker:
    def __call__(self):
        raise RuntimeError("database unavailable")


def test_health_returns_503_when_database_check_fails(monkeypatch):
    monkeypatch.setattr(
        "app.api.health.get_session_maker", lambda: _FailingSessionMaker()
    )
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_health_does_not_leak_database_error(monkeypatch):
    class _LeakySessionMaker:
        def __call__(self):
            raise RuntimeError("postgresql://user:secret@host/db is down")

    monkeypatch.setattr(
        "app.api.health.get_session_maker", lambda: _LeakySessionMaker()
    )
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert "secret" not in response.text
    assert "postgresql" not in response.text
