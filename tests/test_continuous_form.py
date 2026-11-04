"""Multipart file values must not enter typed text form conversion."""

import pytest

from tachyon_api import Tachyon, Form
from tests.helpers import create_client


@pytest.mark.parametrize("annotation", [str, bool, int, list[str], list[bool], list[int]])
@pytest.mark.asyncio
async def test_uploaded_file_rejected_for_text_form_parameter(annotation):
    app = Tachyon()
    calls = []

    async def endpoint(value=Form(...)):
        calls.append(value)
        return {"value": value}
    endpoint.__annotations__["value"] = annotation
    app.post("/")(endpoint)

    async with create_client(app) as client:
        response = await client.post("/", files=[("value", ("input.txt", b"true", "text/plain"))])
    assert response.status_code == 422
    assert calls == []


@pytest.mark.parametrize("annotation", [str, bool, list[str], list[bool]])
@pytest.mark.asyncio
async def test_repeated_text_form_does_not_hide_earlier_upload(annotation):
    app = Tachyon()

    async def endpoint(value=Form(...)):
        return {"value": value}
    endpoint.__annotations__["value"] = annotation
    app.post("/")(endpoint)

    async with create_client(app) as client:
        response = await client.post("/", files=[("value", ("input.txt", b"true", "text/plain")), ("value", (None, "true"))])
    assert response.status_code == 422
