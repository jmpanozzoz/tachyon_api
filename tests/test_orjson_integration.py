"""
Tests for orjson integration with msgspec in Tachyon API framework.
"""

import pytest
import json
import datetime
import uuid
from typing import List, Dict, Optional

from tachyon_api.schemas.models import Struct, encode_json, decode_json

# Complex test data to verify correct serialization of various types
TEST_UUID = uuid.uuid4()
TEST_DATETIME = datetime.datetime.now()
TEST_DATE = datetime.date.today()


class ComplexModel(Struct):
    """A test model with complex types to verify orjson serialization."""

    id: int
    name: str
    uuid_field: uuid.UUID
    date_field: datetime.date
    datetime_field: datetime.datetime
    tags: List[str]
    metadata: Dict[str, str]
    optional_field: Optional[float] = None


@pytest.fixture
def complex_data():
    """Create test data with complex types."""
    return {
        "id": 1,
        "name": "Test Object",
        "uuid_field": TEST_UUID,
        "date_field": TEST_DATE,
        "datetime_field": TEST_DATETIME,
        "tags": ["tag1", "tag2", "tag3"],
        "metadata": {"key1": "value1", "key2": "value2"},
    }


def test_orjson_encode_decode_roundtrip(complex_data):
    """Test that we can encode and decode complex data with orjson."""
    # Create a model from the test data
    model = ComplexModel(**complex_data)

    # Encode the model to JSON using our orjson-powered encoder
    json_data = encode_json(model)

    # Verify we got bytes (orjson returns bytes, not str)
    assert isinstance(json_data, bytes)

    # Decode the JSON back to a dict
    decoded_data = decode_json(json_data)

    # Verify the round trip worked correctly
    assert decoded_data["id"] == complex_data["id"]
    assert decoded_data["name"] == complex_data["name"]
    assert decoded_data["uuid_field"] == str(complex_data["uuid_field"])
    assert "date_field" in decoded_data
    assert "datetime_field" in decoded_data
    assert decoded_data["tags"] == complex_data["tags"]
    assert decoded_data["metadata"] == complex_data["metadata"]
    assert (
        "optional_field" not in decoded_data or decoded_data["optional_field"] is None
    )


def test_orjson_struct_serialization():
    """Test that Struct objects can be correctly serialized using orjson."""
    # Create a complex model
    model = ComplexModel(
        id=42,
        name="Test Object",
        uuid_field=TEST_UUID,
        date_field=TEST_DATE,
        datetime_field=TEST_DATETIME,
        tags=["python", "orjson", "fast"],
        metadata={"purpose": "testing"},
        optional_field=3.14159,
    )

    # Encode to JSON
    json_bytes = encode_json(model)

    # Verify the output is as expected
    decoded = json.loads(json_bytes)
    assert decoded["id"] == 42
    assert decoded["name"] == "Test Object"
    assert decoded["uuid_field"] == str(TEST_UUID)
    assert "date_field" in decoded
    assert "datetime_field" in decoded
    assert decoded["tags"] == ["python", "orjson", "fast"]
    assert decoded["metadata"] == {"purpose": "testing"}
    assert decoded["optional_field"] == 3.14159


def test_orjson_performance_comparison():
    """
    Basic performance test to compare standard json with orjson.
    This is more of a sanity check than a benchmark.
    """
    import time

    # Create a complex model
    model = ComplexModel(
        id=42,
        name="Test Object",
        uuid_field=TEST_UUID,
        date_field=TEST_DATE,
        datetime_field=TEST_DATETIME,
        tags=["python", "orjson", "fast"],
        metadata={"purpose": "testing"},
        optional_field=3.14159,
    )

    # Convert to dict for standard json
    model_dict = {
        "id": model.id,
        "name": model.name,
        "uuid_field": str(model.uuid_field),
        "date_field": model.date_field.isoformat(),
        "datetime_field": model.datetime_field.isoformat(),
        "tags": model.tags,
        "metadata": model.metadata,
        "optional_field": model.optional_field,
    }

    # Test orjson performance
    start = time.time()
    for _ in range(1000):
        encode_json(model)
    orjson_time = time.time() - start

    # Test standard json performance
    start = time.time()
    for _ in range(1000):
        json.dumps(model_dict)
    std_json_time = time.time() - start

    # We just want to make sure orjson is not significantly slower
    # In reality, it should be faster, but we don't want to make the test brittle
    assert orjson_time <= std_json_time * 1.5, (
        "orjson should not be significantly slower than standard json"
    )


def test_orjson_decode_from_json():
    """Test that we can decode JSON into a Struct using orjson."""
    # Create JSON with all the fields
    json_data = {
        "id": 99,
        "name": "Decoded Object",
        "uuid_field": str(TEST_UUID),
        "date_field": TEST_DATE.isoformat(),
        "datetime_field": TEST_DATETIME.isoformat(),
        "tags": ["decoded", "object"],
        "metadata": {"source": "json"},
    }

    # Encode to JSON string (bytes for orjson)
    json_bytes = json.dumps(json_data).encode("utf-8")

    # Decode using our orjson-powered decoder
    decoded_model = decode_json(json_bytes, ComplexModel)

    # Verify the model was created correctly
    assert isinstance(decoded_model, ComplexModel)
    assert decoded_model.id == 99
    assert decoded_model.name == "Decoded Object"
    assert str(decoded_model.uuid_field) == str(TEST_UUID)
    assert decoded_model.tags == ["decoded", "object"]
    assert decoded_model.metadata == {"source": "json"}
