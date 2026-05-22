# Builds an OpenAPI `operation` dict for one endpoint by introspecting the
# function signature.  Side-effect: registers nested-Struct component schemas
# on the supplied generator via `generator.add_schema(...)`.

import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple

from ._param_schemas import build_param_schema
from ._struct_schemas import _schema_for_python_type


def _summary_from_func(func: Callable) -> str:
    return func.__name__.replace("_", " ").title()


class RouteOperationBuilder:
    """Builds the OpenAPI operation dict for one route."""

    __slots__ = ("_generator",)

    def __init__(self, generator) -> None:
        self._generator = generator

    def build(
        self, path: str, method: str, endpoint_func: Callable, **kwargs: Any
    ) -> Dict[str, Any]:
        sig = inspect.signature(endpoint_func)

        operation = self._base_operation(endpoint_func, kwargs)
        self._apply_response_model(operation, kwargs.get("response_model"))
        if "tags" in kwargs:
            operation["tags"] = kwargs["tags"]

        parameters, request_body_schema = self._scan_params(sig, path)

        if parameters:
            operation["parameters"] = parameters
        if request_body_schema:
            operation["requestBody"] = request_body_schema

        return operation

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _base_operation(endpoint_func: Callable, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "summary": kwargs.get("summary", _summary_from_func(endpoint_func)),
            "description": kwargs.get("description", endpoint_func.__doc__ or ""),
            "responses": {
                "200": {
                    "description": "Successful Response",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "422": {
                    "description": "Validation Error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}
                        }
                    },
                },
                "500": {
                    "description": "Response Validation Error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ResponseValidationError"}
                        }
                    },
                },
            },
        }

    def _apply_response_model(self, operation: Dict[str, Any], response_model: Any) -> None:
        if response_model is None:
            return
        local_components: Dict[str, Any] = {}
        try:
            schema = _schema_for_python_type(response_model, local_components, set())
        except Exception:
            return
        for comp_name, comp_schema in local_components.items():
            self._generator.add_schema(comp_name, comp_schema)
        operation["responses"]["200"]["content"]["application/json"]["schema"] = schema

    def _scan_params(
        self, sig: inspect.Signature, path: str
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        from ..params import Body, Cookie, File, Form, Header, Path, Query
        from ..di import Depends, _registry

        _PARAM_IN = {Query: "query", Header: "header", Cookie: "cookie"}
        parameters: List[Dict[str, Any]] = []
        request_body_schema: Optional[Dict[str, Any]] = None
        form_properties: Dict[str, Any] = {}
        form_required: List[str] = []

        for param in sig.parameters.values():
            # Skip DI deps — they don't appear in the OpenAPI spec
            if isinstance(param.default, Depends) or (
                param.default is inspect.Parameter.empty
                and param.annotation in _registry
            ):
                continue

            # Query / Header / Cookie markers
            for param_cls, location in _PARAM_IN.items():
                if isinstance(param.default, param_cls):
                    parameters.append(
                        {
                            "name": param.name,
                            "in": location,
                            "required": param.default.default is ...,
                            "schema": build_param_schema(param.annotation),
                            "description": getattr(param.default, "description", ""),
                        }
                    )
                    break
            else:
                # Path (explicit Path() or implicit via template)
                if isinstance(param.default, Path) or f"{{{param.name}}}" in path:
                    parameters.append(
                        {
                            "name": param.name,
                            "in": "path",
                            "required": True,
                            "schema": build_param_schema(param.annotation),
                            "description": (
                                getattr(param.default, "description", "")
                                if isinstance(param.default, Path)
                                else ""
                            ),
                        }
                    )
                elif isinstance(param.default, File):
                    form_properties[param.name] = {"type": "string", "format": "binary"}
                    if param.default.default is ...:
                        form_required.append(param.name)
                elif isinstance(param.default, Form):
                    form_properties[param.name] = build_param_schema(param.annotation)
                    if param.default.default is ...:
                        form_required.append(param.name)
                elif isinstance(param.default, Body):
                    request_body_schema = self._build_body_schema(param.annotation)

        if form_properties:
            request_body_schema = self._build_form_schema(form_properties, form_required)

        return parameters, request_body_schema

    def _build_body_schema(self, annotation: Any) -> Optional[Dict[str, Any]]:
        local_components: Dict[str, Any] = {}
        try:
            schema = _schema_for_python_type(annotation, local_components, set())
        except Exception:
            return None
        for comp_name, comp_schema in local_components.items():
            self._generator.add_schema(comp_name, comp_schema)
        return {
            "content": {"application/json": {"schema": schema}},
            "required": True,
        }

    @staticmethod
    def _build_form_schema(
        properties: Dict[str, Any], required: List[str]
    ) -> Dict[str, Any]:
        form_schema: Dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            form_schema["required"] = required
        return {
            "content": {"multipart/form-data": {"schema": form_schema}},
            "required": True,
        }
