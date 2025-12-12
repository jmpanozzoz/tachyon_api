"""
Tests for File Handling (UploadFile, Form, File).

TDD: These tests are written BEFORE the implementation.

Features to test:
- UploadFile class for file uploads
- Form() parameter for form data
- File() parameter for file uploads
- Multipart form-data parsing
"""

import pytest
from httpx import AsyncClient, ASGITransport
import io

from tachyon_api import Tachyon
from tachyon_api.params import Form, File
from tachyon_api.files import UploadFile


# --- Test Form() parameter ---

@pytest.mark.asyncio
async def test_form_required_parameter():
    """
    Test that a required Form parameter is extracted correctly.
    """
    app = Tachyon()

    @app.post("/login")
    async def login(username: str = Form(...), password: str = Form(...)):
        return {"username": username, "authenticated": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/login",
            data={"username": "john", "password": "secret123"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "john"
    assert data["authenticated"] is True


@pytest.mark.asyncio
async def test_form_missing_required_returns_422():
    """
    Test that missing required form field returns 422.
    """
    app = Tachyon()

    @app.post("/login")
    async def login(username: str = Form(...)):
        return {"username": username}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/login", data={})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_form_optional_with_default():
    """
    Test that optional form field uses default value when not provided.
    """
    app = Tachyon()

    @app.post("/settings")
    async def settings(theme: str = Form("light"), lang: str = Form("en")):
        return {"theme": theme, "lang": lang}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Without form data
        response = await client.post("/settings", data={})
        assert response.status_code == 200
        assert response.json()["theme"] == "light"

        # With partial form data
        response = await client.post("/settings", data={"theme": "dark"})
        assert response.status_code == 200
        assert response.json()["theme"] == "dark"
        assert response.json()["lang"] == "en"


# --- Test File() and UploadFile ---

@pytest.mark.asyncio
async def test_file_upload_basic():
    """
    Test basic file upload with UploadFile.
    """
    app = Tachyon()

    @app.post("/upload")
    async def upload(file: UploadFile = File(...)):
        content = await file.read()
        return {
            "filename": file.filename,
            "size": len(content),
            "content_type": file.content_type,
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        files = {"file": ("test.txt", b"Hello, World!", "text/plain")}
        response = await client.post("/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["size"] == 13
    assert data["content_type"] == "text/plain"


@pytest.mark.asyncio
async def test_file_upload_read_content():
    """
    Test reading file content from UploadFile.
    """
    app = Tachyon()

    @app.post("/read-file")
    async def read_file(file: UploadFile = File(...)):
        content = await file.read()
        return {"content": content.decode("utf-8")}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        files = {"file": ("hello.txt", b"Hello from file!", "text/plain")}
        response = await client.post("/read-file", files=files)

    assert response.status_code == 200
    assert response.json()["content"] == "Hello from file!"


@pytest.mark.asyncio
async def test_multiple_file_uploads():
    """
    Test uploading multiple files.
    """
    app = Tachyon()

    @app.post("/multi-upload")
    async def multi_upload(
        file1: UploadFile = File(...),
        file2: UploadFile = File(...),
    ):
        return {
            "file1": file1.filename,
            "file2": file2.filename,
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        files = [
            ("file1", ("first.txt", b"First file", "text/plain")),
            ("file2", ("second.txt", b"Second file", "text/plain")),
        ]
        response = await client.post("/multi-upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["file1"] == "first.txt"
    assert data["file2"] == "second.txt"


@pytest.mark.asyncio
async def test_file_with_form_data():
    """
    Test combining file upload with form data.
    """
    app = Tachyon()

    @app.post("/profile")
    async def update_profile(
        name: str = Form(...),
        bio: str = Form(""),
        avatar: UploadFile = File(...),
    ):
        content = await avatar.read()
        return {
            "name": name,
            "bio": bio,
            "avatar_filename": avatar.filename,
            "avatar_size": len(content),
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/profile",
            data={"name": "John Doe", "bio": "Developer"},
            files={"avatar": ("photo.jpg", b"fake image data", "image/jpeg")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "John Doe"
    assert data["bio"] == "Developer"
    assert data["avatar_filename"] == "photo.jpg"


@pytest.mark.asyncio
async def test_optional_file_upload():
    """
    Test optional file upload (not required).
    """
    app = Tachyon()

    @app.post("/optional-upload")
    async def optional_upload(
        name: str = Form(...),
        file: UploadFile = File(None),
    ):
        if file is not None:
            return {"name": name, "has_file": True, "filename": file.filename}
        return {"name": name, "has_file": False}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Without file
        response = await client.post("/optional-upload", data={"name": "Test"})
        assert response.status_code == 200
        assert response.json()["has_file"] is False

        # With file
        response = await client.post(
            "/optional-upload",
            data={"name": "Test"},
            files={"file": ("doc.pdf", b"PDF content", "application/pdf")},
        )
        assert response.status_code == 200
        assert response.json()["has_file"] is True


@pytest.mark.asyncio
async def test_upload_file_seek_and_read():
    """
    Test UploadFile seek() and multiple read() operations.
    """
    app = Tachyon()

    @app.post("/seek-test")
    async def seek_test(file: UploadFile = File(...)):
        # Read first time
        content1 = await file.read()
        # Seek back to start
        await file.seek(0)
        # Read again
        content2 = await file.read()
        return {
            "first_read": len(content1),
            "second_read": len(content2),
            "equal": content1 == content2,
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        files = {"file": ("data.bin", b"some binary data", "application/octet-stream")}
        response = await client.post("/seek-test", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["first_read"] == data["second_read"]
    assert data["equal"] is True
