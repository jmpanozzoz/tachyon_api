# cython: language_level=3
"""
Cython-compiled endpoint pre-compiler.

cdef class gives C-level struct field access for ParamDescriptor and CompiledEndpoint.
p.kind, p.name, p.base_type etc. become direct C struct field reads, not Python
dict-based attribute lookups (~3-5x faster per access).
"""

import asyncio
import inspect
import msgspec

from ..params import Body, Query, Path, Header, Cookie, Form, File
from ..models import Struct
from ..background import BackgroundTasks
from ..di import Depends, _registry, _scopes, SCOPE_SINGLETON
from ..utils import TypeUtils

# Integer kind constants — same values as compiler.py (pure Python fallback)
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

_MARKER_TO_KIND = {
    Body:   KIND_BODY,
    Query:  KIND_QUERY,
    Header: KIND_HEADER,
    Cookie: KIND_COOKIE,
    Form:   KIND_FORM,
    File:   KIND_FILE,
    Path:   KIND_PATH,
}

_COMPILED = {}  # func → CompiledEndpoint


cdef class ParamDescriptor:
    """One parameter's compiled metadata. C struct — all accesses are field reads."""

    cdef public str    name
    cdef public int    kind
    cdef public object annotation
    cdef public object marker
    cdef public str    effective_name
    cdef public object default
    cdef public bint   is_list
    cdef public object item_type
    cdef public bint   item_is_optional
    cdef public object base_type
    cdef public bint   is_optional
    cdef public object decoder
    cdef public object dependency
    cdef public bint   dep_is_async

    def __init__(
        self,
        str name,
        int kind,
        annotation=None,
        marker=None,
        str effective_name="",
        default=inspect.Parameter.empty,  # inspect is imported at module level
        bint is_list=False,
        item_type=str,
        bint item_is_optional=False,
        base_type=str,
        bint is_optional=False,
        decoder=None,
        dependency=None,
        bint dep_is_async=False,
    ):
        self.name          = name
        self.kind          = kind
        self.annotation    = annotation
        self.marker        = marker
        self.effective_name = effective_name if effective_name else name
        self.default       = default
        self.is_list       = is_list
        self.item_type     = item_type
        self.item_is_optional = item_is_optional
        self.base_type     = base_type
        self.is_optional   = is_optional
        self.decoder       = decoder
        self.dependency    = dependency
        self.dep_is_async  = dep_is_async


cdef class CompiledEndpoint:
    """Compiled endpoint metadata. C struct for zero-overhead flag checks."""

    cdef public object func
    cdef public bint   is_async
    cdef public list   params
    cdef public bint   has_params
    cdef public bint   has_callable_deps
    cdef public bint   has_path_params
    cdef public int    param_count

    def __init__(self, func, bint is_async, list params):
        self.func             = func
        self.is_async         = is_async
        self.params           = params
        self.has_params       = bool(params)
        self.param_count      = len(params)
        # Allocate dependency_cache at request time iff any param needs it:
        #   • KIND_DEP_CALLABLE (Depends(callable)) — always per-request
        #   • KIND_DEP_CLASS with non-singleton scope — request- or transient-scoped
        # MUST mirror compiler.py exactly — v1.2.85 / pre-v1.3.0 audit incident:
        # missing the scope check here silently breaks non-singleton class DI in
        # compiled mode while pure-Python users are unaffected.
        self.has_callable_deps = any(
            (<ParamDescriptor>p).kind == KIND_DEP_CALLABLE
            or (
                (<ParamDescriptor>p).kind == KIND_DEP_CLASS
                and _scopes.get((<ParamDescriptor>p).annotation, SCOPE_SINGLETON) != SCOPE_SINGLETON
            )
            for p in params
        )
        self.has_path_params  = any((<ParamDescriptor>p).kind in (KIND_PATH, KIND_PATH_IMPLICIT) for p in params)


def compile_endpoint(func, str path):
    if func in _COMPILED:
        return _COMPILED[func]

    cdef bint is_async = asyncio.iscoroutinefunction(func)
    sig = inspect.signature(func)
    cdef list params = []

    for param in sig.parameters.values():
        ann     = param.annotation
        default = param.default

        from starlette.requests import Request
        if ann is Request:
            params.append(ParamDescriptor(name=param.name, kind=KIND_REQUEST))
            continue

        if ann is BackgroundTasks:
            params.append(ParamDescriptor(name=param.name, kind=KIND_BG))
            continue

        if isinstance(default, Depends) and default.dependency is not None:
            dep_fn = default.dependency
            params.append(ParamDescriptor(
                name=param.name, kind=KIND_DEP_CALLABLE,
                dependency=dep_fn,
                dep_is_async=asyncio.iscoroutinefunction(dep_fn),
            ))
            continue

        is_implicit    = (default is inspect.Parameter.empty and ann in _registry)
        is_explicit_cls = isinstance(default, Depends) and default.dependency is None
        if is_implicit or is_explicit_cls:
            params.append(ParamDescriptor(
                name=param.name, kind=KIND_DEP_CLASS, annotation=ann,
            ))
            continue

        kind = _MARKER_TO_KIND.get(type(default))
        if kind is not None:
            params.append(_build_typed_descriptor(param.name, kind, ann, default))
            continue

        if default is inspect.Parameter.empty and f"{{{param.name}}}" in path:
            base_type, is_opt = TypeUtils.unwrap_optional(ann)
            is_list, raw_item = TypeUtils.is_list_type(base_type)
            item_base, item_is_opt = TypeUtils.unwrap_optional(raw_item) if is_list else (raw_item, False)
            params.append(ParamDescriptor(
                name=param.name, kind=KIND_PATH_IMPLICIT,
                annotation=ann, base_type=base_type, is_optional=is_opt,
                is_list=is_list, item_type=item_base, item_is_optional=item_is_opt,
            ))
            continue

    compiled = CompiledEndpoint(func=func, is_async=is_async, params=params)
    _COMPILED[func] = compiled
    return compiled


cdef _build_typed_descriptor(str name, int kind, object ann, object marker):
    base_type, is_opt = TypeUtils.unwrap_optional(ann)
    is_list, raw_item = TypeUtils.is_list_type(base_type)
    item_type, item_is_opt = TypeUtils.unwrap_optional(raw_item) if is_list else (raw_item, False)

    cdef str effective_name = name
    if kind == KIND_HEADER:
        effective_name = (
            marker.alias.lower() if getattr(marker, "alias", None)
            else TypeUtils.normalize_header_name(name)
        )
    elif kind == KIND_COOKIE or kind == KIND_FORM or kind == KIND_FILE:
        effective_name = getattr(marker, "alias", None) or name

    decoder = None
    if kind == KIND_BODY:
        # See compiler.py for rationale — try msgspec, accept any decodable type.
        try:
            decoder = msgspec.json.Decoder(ann)
        except Exception:
            decoder = None

    return ParamDescriptor(
        name=name, kind=kind, annotation=ann, marker=marker,
        effective_name=effective_name,
        default=marker.default if hasattr(marker, "default") else inspect.Parameter.empty,
        is_list=is_list, item_type=item_type, item_is_optional=item_is_opt,
        base_type=base_type, is_optional=is_opt, decoder=decoder,
    )
