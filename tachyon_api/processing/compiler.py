"""Endpoint pre-compilation: analyse a function once at registration, reuse per request."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, List, Optional, Type

import msgspec

from ..params import Body, Query, Path, Header, Cookie, Form, File
from ..models import Struct
from ..background import BackgroundTasks
from ..di import Depends, _registry
from ..utils import TypeUtils


# Parameter kinds — integer constants for O(1) C-level comparison in Cython.
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
        "name", "kind", "annotation", "marker", "effective_name", "default",
        "is_list", "item_type", "item_is_optional", "base_type", "is_optional",
        "decoder", "dependency", "dep_is_async",
    )

    def __init__(
        self,
        name: str,
        kind: str,
        annotation: Any = None,
        marker: Any = None,
        effective_name: str = "",
        default: Any = inspect.Parameter.empty,
        is_list: bool = False,
        item_type: Any = str,        # unwrapped item base type (Optional already stripped)
        item_is_optional: bool = False,
        base_type: Any = str,
        is_optional: bool = False,
        decoder: Any = None,
        dependency: Optional[Callable] = None,
        dep_is_async: bool = False,
    ):
        self.name = name
        self.kind = kind
        self.annotation = annotation
        self.marker = marker
        self.effective_name = effective_name if effective_name else name
        self.default = default
        self.is_list = is_list
        self.item_type = item_type
        self.item_is_optional = item_is_optional
        self.base_type = base_type
        self.is_optional = is_optional
        self.decoder = decoder
        self.dependency = dependency
        self.dep_is_async = dep_is_async


class CompiledEndpoint:
    __slots__ = (
        "func", "is_async", "params", "has_params", "has_callable_deps",
        "has_path_params", "param_count",
    )

    def __init__(self, func: Callable, is_async: bool, params: List[ParamDescriptor]):
        self.func = func
        self.is_async = is_async
        self.params = params
        # Pre-computed flags — zero cost at request time
        self.has_params = bool(params)
        from ..di import _scopes, SCOPE_SINGLETON
        self.has_callable_deps = any(
            p.kind == KIND_DEP_CALLABLE
            or (p.kind == KIND_DEP_CLASS and _scopes.get(p.annotation, SCOPE_SINGLETON) != SCOPE_SINGLETON)
            for p in params
        )
        self.has_path_params = any(p.kind in (KIND_PATH, KIND_PATH_IMPLICIT) for p in params)
        # Pre-computed length — used to pre-allocate the args list in process_parameters
        self.param_count = len(params)


# Global cache: func → CompiledEndpoint (populated once per registered endpoint)
_COMPILED: dict[Callable, CompiledEndpoint] = {}


def compile_endpoint(func: Callable, path: str) -> CompiledEndpoint:
    """Analyse endpoint signature once and return a CompiledEndpoint descriptor."""
    if func in _COMPILED:
        return _COMPILED[func]

    is_async = asyncio.iscoroutinefunction(func)
    sig = inspect.signature(func)
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
            params.append(ParamDescriptor(
                name=param.name,
                kind=KIND_DEP_CALLABLE,
                dependency=dep_fn,
                dep_is_async=asyncio.iscoroutinefunction(dep_fn),
            ))
            continue

        # 4. Implicit or explicit class dependency (@injectable / Depends())
        is_implicit = (default is inspect.Parameter.empty and ann in _registry)
        is_explicit_class = isinstance(default, Depends) and default.dependency is None
        if is_implicit or is_explicit_class:
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
            base_type, is_opt = TypeUtils.unwrap_optional(ann)
            is_list, raw_item = TypeUtils.is_list_type(base_type)
            item_base, item_is_opt = TypeUtils.unwrap_optional(raw_item) if is_list else (raw_item, False)
            params.append(ParamDescriptor(
                name=param.name,
                kind=KIND_PATH_IMPLICIT,
                annotation=ann,
                base_type=base_type,
                is_optional=is_opt,
                is_list=is_list,
                item_type=item_base,
                item_is_optional=item_is_opt,
            ))
            continue

    compiled = CompiledEndpoint(func=func, is_async=is_async, params=params)
    _COMPILED[func] = compiled
    return compiled


def _build_typed_descriptor(name: str, kind: str, ann: Any, marker: Any) -> ParamDescriptor:
    base_type, is_opt = TypeUtils.unwrap_optional(ann)
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
        # msgspec supports Struct, List[Struct], Tuple[...], Optional[Struct],
        # dict, primitives, etc.  We delegate the "is this decodable" decision
        # to msgspec by trying to build a decoder — if the type is genuinely
        # unsupported, msgspec raises and we leave decoder=None so the body
        # extractor returns a 422 at request time.
        try:
            decoder = msgspec.json.Decoder(ann)
        except Exception:
            decoder = None

    return ParamDescriptor(
        name=name,
        kind=kind,
        annotation=ann,
        marker=marker,
        effective_name=effective_name,
        default=marker.default if hasattr(marker, "default") else inspect.Parameter.empty,
        is_list=is_list,
        item_type=item_type,       # already unwrapped from Optional
        item_is_optional=item_is_opt,
        base_type=base_type,
        is_optional=is_opt,
        decoder=decoder,
    )
