"""
Tests for TypeUtils and TypeConverter utilities.
"""

from typing import Optional, List, Union
from starlette.responses import JSONResponse

from tachyon_api.utils import TypeUtils, TypeConverter


class TestTypeUtils:
    def test_unwrap_optional_with_optional_type(self):
        inner_type, is_optional = TypeUtils.unwrap_optional(Optional[str])
        assert inner_type is str
        assert is_optional is True

    def test_unwrap_optional_with_non_optional_type(self):
        inner_type, is_optional = TypeUtils.unwrap_optional(str)
        assert inner_type is str
        assert is_optional is False

    def test_unwrap_optional_with_union_none(self):
        inner_type, is_optional = TypeUtils.unwrap_optional(Union[int, None])
        assert inner_type is int
        assert is_optional is True

    def test_is_list_type_with_list(self):
        is_list, item_type = TypeUtils.is_list_type(List[str])
        assert is_list is True
        assert item_type is str

    def test_is_list_type_with_non_list(self):
        is_list, item_type = TypeUtils.is_list_type(str)
        assert is_list is False
        assert item_type is str

    def test_get_type_name_basic_types(self):
        assert TypeUtils.get_type_name(int) == "integer"
        assert TypeUtils.get_type_name(str) == "string"
        assert TypeUtils.get_type_name(bool) == "boolean"
        assert TypeUtils.get_type_name(float) == "number"

    def test_get_type_name_custom_type(self):
        class CustomType:
            pass

        assert TypeUtils.get_type_name(CustomType) == "CustomType"


class TestTypeConverter:
    def test_convert_value_string(self):
        result = TypeConverter.convert_value("hello", str, "test_param")
        assert result == "hello"

    def test_convert_value_integer(self):
        result = TypeConverter.convert_value("123", int, "test_param")
        assert result == 123

    def test_convert_value_boolean_true_variants(self):
        true_values = ["true", "True", "TRUE", "1", "t", "T", "yes", "YES"]
        for value in true_values:
            result = TypeConverter.convert_value(value, bool, "test_param")
            assert result is True

    def test_convert_value_boolean_false_variants(self):
        false_values = ["false", "False", "FALSE", "0", "f", "F", "no", "NO"]
        for value in false_values:
            result = TypeConverter.convert_value(value, bool, "test_param")
            assert result is False

    def test_convert_value_optional_type(self):
        result = TypeConverter.convert_value("123", Optional[int], "test_param")
        assert result == 123

    def test_convert_value_invalid_integer_query_param(self):
        result = TypeConverter.convert_value(
            "invalid", int, "test_param", is_path_param=False
        )
        assert isinstance(result, JSONResponse)
        assert result.status_code == 422

    def test_convert_value_invalid_integer_path_param(self):
        result = TypeConverter.convert_value(
            "invalid", int, "test_param", is_path_param=True
        )
        assert isinstance(result, JSONResponse)
        assert result.status_code == 404

    def test_convert_list_values_basic(self):
        values = ["1", "2", "3"]
        result = TypeConverter.convert_list_values(values, int, "test_param")
        assert result == [1, 2, 3]

    def test_convert_list_values_with_optional_items(self):
        values = ["1", "", "3", "null"]
        result = TypeConverter.convert_list_values(values, Optional[int], "test_param")
        assert result == [1, None, 3, None]

    def test_convert_list_values_with_error(self):
        values = ["1", "invalid", "3"]
        result = TypeConverter.convert_list_values(values, int, "test_param")
        assert isinstance(result, JSONResponse)
        assert result.status_code == 422
