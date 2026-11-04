"""Response schemas validate values even when constructed in application code."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import msgspec
import pytest

from tachyon_api import Struct
from tachyon_api.processing.response_processor import ResponseProcessor


class Child(Struct):
    value: Annotated[int, msgspec.Meta(gt=0)]


class Parent(Struct):
    child: Child


@pytest.mark.parametrize("payload, model", [
    (Child("wrong"), Child),
    (Child(0), Child),
    (Parent(Child(-1)), Parent),
    ([Child("wrong")], list[Child]),
    ({"child": Child("wrong")}, Parent),
])
def test_response_schema_rejects_invalid_existing_nested_values(payload, model):
    response = ResponseProcessor._build_response(payload, model)
    assert response.status_code == 500


def test_mutation_is_validated_without_changing_the_user_object():
    child = Child(1)
    child.value = "invalid"
    assert ResponseProcessor._build_response(child, Child).status_code == 500
    assert child.value == "invalid"


def test_response_validation_preserves_wire_names_and_native_scalar_values():
    class Native(Struct, rename="camel"):
        raw_bytes: bytes
        created_at: datetime
        identifier: UUID
        amount: Decimal

    original = Native(b"hello", datetime(2026, 1, 1, tzinfo=timezone.utc), UUID(int=1), Decimal("1.25"))
    response = ResponseProcessor._build_response(original, Native)
    assert response.status_code == 200
    assert msgspec.json.decode(response.body, type=Native) == original


def test_response_model_filters_extra_fields():
    response = ResponseProcessor._build_response({"value": 2, "secret": "hidden"}, Child)
    assert msgspec.json.decode(response.body) == {"value": 2}


@pytest.mark.parametrize("payload, model", [
    (b"abc", bytes), ([b"abc"], list[bytes]),
    (Decimal("1.25"), Decimal), (timedelta(seconds=3), timedelta),
    (frozenset({1, 2}), frozenset[int]),
])
def test_valid_response_schema_supports_all_msgspec_scalars(payload, model):
    response = ResponseProcessor._build_response(payload, model)
    assert response.status_code == 200
    assert msgspec.json.decode(response.body, type=model) == payload


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("nested", [False, True])
def test_nonfinite_numbers_cannot_emit_null_against_numeric_schema(number, nested):
    payload, model = ({"value": number}, dict[str, float]) if nested else (number, float)
    response = ResponseProcessor._build_response(payload, model)
    assert response.status_code == 500
