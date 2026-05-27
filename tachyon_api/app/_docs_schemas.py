# Cold path — invoked at startup to register Tachyon's default error schemas
# on the OpenAPI generator.


class CommonSchemas:
    """Registers Tachyon's default error response schemas on an OpenAPI generator."""

    __slots__ = ()

    @staticmethod
    def register(generator) -> None:
        generator.add_schema(
            "ValidationErrorResponse",
            {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "error": {"type": "string"},
                    "code": {"type": "string"},
                    "errors": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "required": ["success", "error", "code"],
            },
        )
        generator.add_schema(
            "ResponseValidationError",
            {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "error": {"type": "string"},
                    "detail": {"type": "string"},
                    "code": {"type": "string"},
                },
                "required": ["success", "error", "code"],
            },
        )
