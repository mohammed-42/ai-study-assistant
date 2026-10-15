"""Tests for subjects CRUD API."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.models.profile import Profile
from app.models.subject import Subject


@pytest.fixture
def client(db_session, test_user):
    """Create test client with auth overridden."""
    mock_user = MagicMock()
    mock_user.id = test_user.id
    mock_user.email = test_user.email

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_check():
    """Test health endpoint — no auth needed."""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_subjects(db_session, test_subject, test_user, client):
    """Test listing subjects."""
    response = client.get("/api/subjects/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Mathematics"


@pytest.mark.asyncio
async def test_create_subject(db_session, test_user, client):
    """Test creating a subject."""
    response = client.post("/api/subjects/", json={
        "name": "Physics",
        "description": "Mechanics and Thermodynamics"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Physics"
    assert data["description"] == "Mechanics and Thermodynamics"


@pytest.mark.asyncio
async def test_get_subject(db_session, test_subject, client):
    """Test getting a single subject."""
    response = client.get(f"/api/subjects/{test_subject.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Mathematics"


@pytest.mark.asyncio
async def test_update_subject(db_session, test_subject, client):
    """Test updating a subject."""
    response = client.patch(f"/api/subjects/{test_subject.id}", json={
        "name": "Advanced Mathematics"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Advanced Mathematics"


@pytest.mark.asyncio
async def test_delete_subject(db_session, test_subject, client):
    """Test deleting a subject."""
    response = client.delete(f"/api/subjects/{test_subject.id}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_subject_ownership_isolation(db_session, test_user, test_subject, client):
    """Test that users can only access their own subjects."""
    other_user = Profile(sub="other-sub-002", email="other@example.com", full_name="Other User")
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    other_subject = Subject(owner_id=other_user.id, name="Chemistry")
    db_session.add(other_subject)
    await db_session.commit()

    response = client.get(f"/api/subjects/{other_subject.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_request():
    """Test that unauthenticated requests are rejected."""
    client = TestClient(app)
    response = client.get("/api/subjects/")
    assert response.status_code == 401
