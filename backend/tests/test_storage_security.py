"""Tests for private storage cleanup and signed page-image URLs."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.profile import Profile
from app.services.storage import delete_user_objects


@pytest.fixture
def client(db_session, test_user):
    mock_user = MagicMock()
    mock_user.id = test_user.id
    mock_user.email = test_user.email

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_signed_page_image_url(db_session, test_user, test_subject, client, monkeypatch):
    doc = Document(
        owner_id=test_user.id,
        subject_id=test_subject.id,
        name="Scan.jpg",
        doc_type="image",
        status=DocumentStatus.READY,
        storage_key=f"user/{test_user.id}/doc/scan.jpg",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    page = DocumentPage(
        document_id=doc.id,
        page_number=1,
        text="Handwritten text",
        source="ocr",
        page_image_key=f"user/{test_user.id}/{doc.id}/0_scan.jpg",
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)

    monkeypatch.setattr(
        "app.api.pages.create_signed_url",
        lambda key, expires_in: f"https://signed.example/{key}?expires={expires_in}",
    )

    response = client.get(
        f"/api/documents/{doc.id}/pages/{page.id}/image-url",
        params={"expires_in": 300},
    )

    assert response.status_code == 200
    assert response.json()["expires_in"] == 300
    assert response.json()["url"].startswith("https://signed.example/")


@pytest.mark.asyncio
async def test_signed_url_rejects_foreign_page_key(db_session, test_user, test_subject, client):
    doc = Document(
        owner_id=test_user.id,
        subject_id=test_subject.id,
        name="Scan.jpg",
        doc_type="image",
        status=DocumentStatus.READY,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    page = DocumentPage(
        document_id=doc.id,
        page_number=1,
        text="Handwritten text",
        source="ocr",
        page_image_key=f"user/{uuid.uuid4()}/{doc.id}/0_scan.jpg",
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)

    response = client.get(f"/api/documents/{doc.id}/pages/{page.id}/image-url")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_document_removes_storage_objects(
    db_session, test_user, test_subject, client, monkeypatch
):
    doc = Document(
        owner_id=test_user.id,
        subject_id=test_subject.id,
        name="Delete.pdf",
        doc_type="pdf",
        status=DocumentStatus.READY,
        storage_key=f"user/{test_user.id}/{uuid.uuid4()}/notes.pdf",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    called = {}

    def fake_delete(owner_id, document_id, storage_key=None):
        called["owner_id"] = owner_id
        called["document_id"] = document_id
        called["storage_key"] = storage_key
        return 1

    monkeypatch.setattr("app.api.documents.delete_document_objects", fake_delete)

    response = client.delete(f"/api/documents/{doc.id}")

    assert response.status_code == 204
    assert called == {
        "owner_id": test_user.id,
        "document_id": doc.id,
        "storage_key": doc.storage_key,
    }


@pytest.mark.asyncio
async def test_delete_document_removes_rendered_page_images(
    db_session, test_user, test_subject, client, monkeypatch
):
    doc_id = uuid.uuid4()
    folder = f"user/{test_user.id}/{doc_id}"
    doc = Document(
        id=doc_id,
        owner_id=test_user.id,
        subject_id=test_subject.id,
        name="Scanned.pdf",
        doc_type="pdf",
        status=DocumentStatus.READY,
        storage_key=f"{folder}/scanned.pdf",
    )
    db_session.add(doc)
    await db_session.commit()

    page = DocumentPage(
        document_id=doc.id,
        page_number=1,
        text="OCR text",
        source="ocr",
        page_image_key=f"{folder}/page_1.jpg",
    )
    db_session.add(page)
    await db_session.commit()

    storage = MagicMock()
    bucket = storage.storage.from_.return_value
    bucket.list.return_value = [{"name": "scanned.pdf"}, {"name": "page_1.jpg"}]

    monkeypatch.setattr("app.services.storage.storage_is_configured", lambda: True)
    monkeypatch.setattr("app.services.storage.get_storage_client", lambda: storage)

    response = client.delete(f"/api/documents/{doc.id}")

    assert response.status_code == 204
    bucket.remove.assert_called_once_with(
        [f"{folder}/scanned.pdf", f"{folder}/page_1.jpg"]
    )


def test_delete_user_objects_removes_nested_user_files(monkeypatch):
    owner_id = uuid.uuid4()
    root = f"user/{owner_id}"
    folder = f"{root}/document-id"
    storage = MagicMock()
    bucket = storage.storage.from_.return_value
    bucket.list.side_effect = lambda path: {
        root: [{"name": "document-id", "id": None}],
        folder: [
            {"name": "notes.pdf", "id": "file-1"},
            {"name": "page_1.jpg", "id": "file-2"},
        ],
    }[path]

    monkeypatch.setattr("app.services.storage.storage_is_configured", lambda: True)
    monkeypatch.setattr("app.services.storage.get_storage_client", lambda: storage)

    assert delete_user_objects(owner_id) == 2
    bucket.remove.assert_called_once_with(
        [f"{folder}/notes.pdf", f"{folder}/page_1.jpg"]
    )
