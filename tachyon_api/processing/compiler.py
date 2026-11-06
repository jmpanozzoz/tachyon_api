"""Endpoint pre-compilation: analyse a function once at registration, reuse per request."""

from __future__ import annotations

import inspect
from typing import Any, Callable, List, Optional

import msgspec

from ..params import Body, Query, Path, Header, Cookie, Form, File
from ..background import BackgroundTasks
from ..di import Depends, _registry
from ..utils import TypeUtils
from .dependencies._sig_cache import get_signature, is_async_callable, prepare_dependency


# Parameter kinds prepared at registration and used by the dispatch loop.
# (int compare is a single machine instruction vs string hash+compare)
KIND_REQUEST       = 0
KIND_BG            = 1
KIND_BODY          = 2
KIND_QUERY         = 3
KIND_HEADER        = 4
KIND_COOKIE        = 5
KIND_FORM          = 6
KIND_FILE          = 7
KIND_PATH          = 8
KIND_PATH_IMPLICIT = 9
KIND_DEP_CALLABLE  = 10
KIND_DEP_CLASS     = 11

# Param marker classes → kind int (O(1) lookup replaces isinstance chain)
_MARKER_TO_KIND = {
    Body:   KIND_BODY,
    Query:  KIND_QUERY,
    Header: KIND_HEADER,
    Cookie: KIND_COOKIE,
    Form:   KIND_FORM,
    File:   KIND_FILE,
    Path:   KIND_PATH,
}


class ParamDescriptor:
    __slots__ = (
        "name", "kind", "annotation", "effective_name", "default",
        "is_list", "item_type", "item_is_optional", "base_type",
        "decoder", "dependency",
    )

    def __init__(
        self,
        name: str,
        kind: int,
        annotation: Any = None,
        effective_name: str = "",
        default: Any = inspect.Parameter.empty,
        is_list: bool = False,
        item_type: Any = str,        # unwrapped item base type (Optional already stripped)
        item_is_optional: bool = False,
        base_type: Any = str,
        decoder: Any = None,
        dependency: Optional[Callable] = None,
    ):
        self.name = name
        self.kind = kind
        self.annotation = annotation
        self.effective_name = effective_name if effective_name else name
        self.default = default
        self.is_list = is_list
        self.item_type = item_type
        self.item_is_optional = item_is_optional
        self.base_type = base_type
        self.decoder = decoder
        self.dependency = dependency


class CompiledEndpoint:
    __slots__ = (
        "func", "is_async", "params", "has_params", "has_callable_deps",
        "param_count", "keyword_names",
    )

    def __init__(self, func: Callable, is_async: bool, params: List[ParamDescriptor], keyword_names: Any = None):
        self.keyword_names = keyword_names
        self.func = func
        self.is_async = is_async
        self.params = params
        # Pre-computed flags — zero cost at request time
        self.has_params = bool(params)
        # Nested factories and overrides share the same request cache.
        self.has_callable_deps = any(
            p.kind in (KIND_DEP_CALLABLE, KIND_DEP_CLASS) for p in params
        )
        # Pre-computed length — used to pre-allocate the args list in process_parameters
        self.param_count = len(params)


def compile_endpoint(func: Callable, path: str) -> CompiledEndpoint:
    """Analyse endpoint signature once and return a CompiledEndpoint descriptor."""
    is_async = is_async_callable(func)
    sig = get_signature(func)
    params: List[ParamDescriptor] = []

    for param in sig.parameters.values():
        ann   = param.annotation
        default = param.default

        # 1. Starlette Request injection
        from starlette.requests import Request
        if ann is Request:
            params.append(ParamDescriptor(name=param.name, kind=KIND_REQUEST))
            continue

        # 2. BackgroundTasks injection
        if ann is BackgroundTasks:
            params.append(ParamDescriptor(name=param.name, kind=KIND_BG))
            continue

        # 3. Explicit callable dependency: Depends(some_callable)
        if isinstance(default, Depends) and default.dependency is not None:
            dep_fn = default.dependency
            prepare_dependency(dep_fn)
            params.append(ParamDescriptor(
                name=param.name,
                kind=KIND_DEP_CALLABLE,
                dependency=dep_fn,
            ))
            continue

        # 4. Implicit or explicit class dependency (@injectable / Depends())
        is_implicit = (default is inspect.Parameter.empty and ann in _registry)
        is_explicit_class = isinstance(default, Depends) and default.dependency is None
        if is_implicit or is_explicit_class:
            prepare_dependency(ann)
            params.append(ParamDescriptor(
                name=param.name,
                kind=KIND_DEP_CLASS,
                annotation=ann,
            ))
            continue

        # 5. Explicit param markers
        kind = _MARKER_TO_KIND.get(type(default))
        if kind is not None:
            pd = _build_typed_descriptor(param.name, kind, ann, default)
            params.append(pd)
            continue

        # 6. Implicit path param (no default, name in path template)
        if default is inspect.Parameter.empty and f"{{{param.name}}}" in path:
            base_type, _ = TypeUtils.unwrap_optional(ann)
            is_list, raw_item = TypeUtils.is_list_type(base_type)
            item_base, item_is_opt = TypeUtils.unwrap_optional(raw_item) if is_list else (raw_item, False)
            params.append(ParamDescriptor(
                name=param.name,
                kind=KIND_PATH_IMPLICIT,
                annotation=ann,
                base_type=base_type,
                is_list=is_list,
                item_type=item_base,
                item_is_optional=item_is_opt,
            ))
            continue

    positional = [p.name for p in sig.parameters.values()
                  if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    names = [p.name for p in params]
    keyword_names = None if names == positional[:len(names)] else tuple(names)
    if keyword_names and any(sig.parameters[name].kind == inspect.Parameter.POSITIONAL_ONLY for name in names):
        raise TypeError("Injected positional-only parameters cannot follow omitted defaults")
    compiled = CompiledEndpoint(func=func, is_async=is_async, params=params, keyword_names=keyword_names)
    return compiled


def _build_typed_descriptor(name: str, kind: int, ann: Any, marker: Any) -> ParamDescriptor:
    if kind == KIND_FILE:
        from ..files import validate_file_parameter
        validate_file_parameter(ann, marker.default)
    base_type, _ = TypeUtils.unwrap_optional(ann)
    is_list, raw_item_type = TypeUtils.is_list_type(base_type)
    # Unwrap Optional from item type too (e.g. List[Optional[int]] → item=int, item_is_opt=True)
    item_type, item_is_opt = TypeUtils.unwrap_optional(raw_item_type) if is_list else (raw_item_type, False)

    effective_name = name
    if kind == KIND_HEADER:
        effective_name = (
            marker.alias.lower() if getattr(marker, "alias", None)
            else TypeUtils.normalize_header_name(name)
        )
    elif kind in (KIND_COOKIE, KIND_FORM, KIND_FILE):
        effective_name = getattr(marker, "alias", None) or name

    decoder = None
    if kind == KIND_BODY:
        # Reject unsupported body annotations during registration.
        decoder = msgspec.json.Decoder(ann)

    return ParamDescriptor(
        name=name,
        kind=kind,
        annotation=ann,
        effective_name=effective_name,
        default=marker.default if hasattr(marker, "default") else inspect.Parameter.empty,
        is_list=is_list,
        item_type=item_type,       # already unwrapped from Optional
        item_is_optional=item_is_opt,
        base_type=base_type,
        decoder=decoder,
    )
