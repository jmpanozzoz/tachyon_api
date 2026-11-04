"""Multipart ownership, repeated uploads, bounded lists and ISO conversion contracts."""
from datetime import date, datetime, timezone
from io import BytesIO
from typing import Optional

import pytest
from starlette.datastructures import FormData, Headers, UploadFile as StarletteUploadFile

from tachyon_api import Tachyon
from tachyon_api.files import UploadFile, validate_file_parameter
from tachyon_api.params import File, Query
from tachyon_api.processing._extractors.file import FileExtractor
from tachyon_api.processing._extractors.query_list import QueryListExtractor
from tachyon_api.processing.compiler import ParamDescriptor
from tachyon_api.utils import TypeConverter
from tests.helpers import create_client


@pytest.mark.parametrize("name, expected", [
    ("../../etc/passwd", "passwd"), (r"C:\fakepath\secret.txt", "secret.txt"),
    ("/absolute/private.txt", "private.txt"), ("../dir\\sub/leaf\x00.txt", "leaf.txt"),
    ("..", ""), (".", ""), (None, None), ("plain.txt", "plain.txt"),
    ("C:secret.txt", "secret.txt"),
    ("C:C:secret.txt", "secret.txt"),
])
def test_upload_adaptation_preserves_handle_and_is_idempotent(name, expected):
    stream = BytesIO(b"payload")
    original = StarletteUploadFile(stream, filename=name, size=7, headers=Headers({"content-type": "text/plain"}))
    upload = UploadFile.from_starlette(original)
    assert upload.filename == expected
    assert upload.file is stream and upload.file.tell() == 0 and not stream.closed
    assert upload.headers is original.headers and upload.size == 7
    assert UploadFile.from_starlette(upload) is upload
    stream.close()


def multipart(parts):
    body = b""
    for name, filename, value in parts:
        disposition = f'Content-Disposition: form-data; name="{name}"'
        if filename is not None:
            disposition += f'; filename="{filename}"'
        body += b"--contract\r\n" + disposition.encode() + b"\r\n\r\n" + value + b"\r\n"
    return body + b"--contract--\r\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["success", "invalid", "error"])
async def test_repeated_uploads_sanitized_and_closed_once(monkeypatch, mode):
    import starlette.formparsers as parsers
    from starlette.exceptions import HTTPException
    opened = []

    class CountedFile(BytesIO):
        def __init__(self):
            super().__init__()
            self.close_count = 0

        def close(self):
            self.close_count += 1
            super().close()

    def new_file(*args, **kwargs):
        stream = CountedFile()
        opened.append(stream)
        return stream

    monkeypatch.setattr(parsers, "SpooledTemporaryFile", new_file)
    app = Tachyon()
    seen = []

    @app.post("/gallery")
    async def gallery(images: list[UploadFile] = File(..., alias="parts")):
        seen.extend(images)
        assert all(isinstance(image, UploadFile) and not image.file.closed for image in images)
        if mode == "error":
            raise HTTPException(400, "rejected")
        return {"names": [image.filename for image in images], "data": [(await image.read()).decode() for image in images]}

    parts = [("parts", "../../first\x00.txt", b"one"), ("parts", r"C:\private\second.txt", b"two")]
    if mode == "invalid":
        parts.append(("parts", None, b"text"))
    async with create_client(app) as client:
        response = await client.post("/gallery", content=multipart(parts), headers={"content-type": "multipart/form-data; boundary=contract"})
        spec = (await client.get("/openapi.json")).json()
    assert response.status_code == {"success": 200, "invalid": 422, "error": 400}[mode]
    assert len(opened) == 2 and all(stream.closed and stream.close_count == 1 for stream in opened)
    if mode == "success":
        assert response.json() == {"names": ["first.txt", "second.txt"], "data": ["one", "two"]}
        assert [upload.file for upload in seen] == opened
    schema = spec["paths"]["/gallery"]["post"]["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert schema["properties"]["parts"] == {"type": "array", "items": {"type": "string", "format": "binary"}}


@pytest.mark.parametrize("is_list", [False, True])
def test_present_invalid_upload_does_not_use_default(is_list):
    descriptor = ParamDescriptor("upload", 7, default=None, is_list=is_list)
    value, error = FileExtractor().extract(descriptor, FormData([("upload", "text")]))
    assert value is None and error.status_code == 422


def test_scalar_rejects_duplicate_uploads_and_empty_list_default_is_fresh():
    streams = [UploadFile(BytesIO(), filename="x") for _ in range(2)]
    descriptor = ParamDescriptor("upload", 7, default=None)
    assert FileExtractor().extract(descriptor, FormData([("upload", stream) for stream in streams]))[1].status_code == 422
    descriptor = ParamDescriptor("upload", 7, default=[], is_list=True)
    value, error = FileExtractor().extract(descriptor, FormData())
    assert value == [] and value is not descriptor.default and error is None
    for stream in streams:
        stream.file.close()


@pytest.mark.parametrize("annotation, default", [(str, ...), (list[str], ...), (list[Optional[UploadFile]], ...), (UploadFile, "bad"), (list[UploadFile], ["bad"])])
def test_invalid_file_configuration_fails_registration(annotation, default):
    def endpoint(upload=File(default)):
        return {}
    endpoint.__annotations__["upload"] = annotation
    with pytest.raises(TypeError, match="File"):
        Tachyon().post("/")(endpoint)


@pytest.mark.parametrize("annotation, default", [(UploadFile, None), (Optional[list[UploadFile]], None), (list[UploadFile], []), (StarletteUploadFile, ...)])
def test_supported_file_configuration(annotation, default):
    validate_file_parameter(annotation, default)


@pytest.mark.parametrize("target, raw, expected", [
    (date, "2026-11-04", date(2026, 11, 4)),
    (datetime, "2026-11-04T12:30:45.123456+03:00", datetime.fromisoformat("2026-11-04T12:30:45.123456+03:00")),
    (datetime, "2026-11-04 12:30:45", datetime(2026, 11, 4, 12, 30, 45)),
    (int, "123456789012345678901234567890", 123456789012345678901234567890),
    (float, "1e100", 1e100),
])
def test_shared_iso_conversion_and_numeric_behavior(target, raw, expected):
    assert TypeConverter.convert_value(raw, target, "value") == expected


@pytest.mark.parametrize("target", [date, datetime])
def test_invalid_iso_conversion_has_http_and_path_errors(target):
    assert TypeConverter.convert_value("bad", target, "value").status_code == 422
    assert TypeConverter.convert_value("bad", target, "value", True).status_code == 404


def test_oversized_csv_rejected_before_split():
    class UnsplitString(str):
        def split(self, *args, **kwargs):
            raise AssertionError("oversized input must not be split")
    class Query:
        def getlist(self, name):
            return [UnsplitString("," * 1000000)]
    descriptor = ParamDescriptor("values", 3, is_list=True, item_type=int)
    assert QueryListExtractor().extract(descriptor, Query())[1].status_code == 422


@pytest.mark.asyncio
async def test_iso_types_in_real_path_and_query():
    app = Tachyon()
    @app.get("/dates/{day}")
    async def endpoint(day: date, at: datetime = Query(...)):
        return {"day": day.isoformat(), "at": at.isoformat()}
    async with create_client(app) as client:
        response = await client.get("/dates/2026-11-04", params={"at": "2026-11-04T12:30:45+03:00"})
    assert response.status_code == 200
    assert response.json() == {"day": "2026-11-04", "at": "2026-11-04T12:30:45+03:00"}


@pytest.mark.parametrize("raw", ["2026-11-04T12:30:45Z", "2026-11-04 12:30:45.1+00:00"])
def test_datetime_utc_and_fraction_formats_are_version_independent(raw):
    expected = datetime(2026, 11, 4, 12, 30, 45, 100000 if ".1" in raw else 0, tzinfo=timezone.utc)
    assert TypeConverter.convert_value(raw, datetime, "value") == expected


@pytest.mark.parametrize("target, raw", [
    (date, "20261104"), (date, "2026-W45-3"),
    (datetime, "20261104T123045"), (datetime, "2026-11-04"),
    (datetime, "2026-11-04T12:30"), (datetime, "2026-11-04x12:30:45"),
    (datetime, "2026-11-04T12:30:45,1"),
    (datetime, "2026-11-04T12:30:45.1234567"),
    (datetime, "2026-11-04T12:30:45+00:60"),
    (datetime, "2026-11-04T12:30:45+24:00"),
])
def test_noncontract_iso_formats_rejected_on_all_supported_interpreters(target, raw):
    assert TypeConverter.convert_value(raw, target, "value").status_code == 422
