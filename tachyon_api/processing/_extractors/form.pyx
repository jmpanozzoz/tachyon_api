# cython: language_level=3
"""Typed form extraction from parsed, bounded form data."""
from starlette.responses import JSONResponse

from ...utils import TypeConverter
from ...responses import validation_error_response
from ._missing import missing


cdef class FormExtractor:

    cpdef extract(self, object descriptor, object form_data):
        name = descriptor.effective_name
        if name not in form_data:
            return missing(descriptor, "form field", name)
        values = form_data.getlist(name)
        for value in values:
            if not isinstance(value, str):
                return None, validation_error_response(f"Invalid form field: {name}; expected text")
        if descriptor.is_list:
            converted = TypeConverter.convert_list_values_bare(
                values, descriptor.item_type, descriptor.item_is_optional, name
            )
        else:
            converted = TypeConverter.convert_value_bare(values[len(values) - 1], descriptor.base_type, name)
        if isinstance(converted, JSONResponse):
            return None, converted
        return converted, None
