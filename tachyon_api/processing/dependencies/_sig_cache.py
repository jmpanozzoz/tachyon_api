"""Resolved signatures shared by endpoint compilation, DI, and OpenAPI."""

import inspect
import sys
from types import FunctionType
from functools import partial
from typing import Callable, get_type_hints
from weakref import WeakKeyDictionary

_SIG_CACHE = WeakKeyDictionary()


def get_signature(fn: Callable) -> inspect.Signature:
    try:
        sig = _SIG_CACHE.get(fn)
    except TypeError:
        sig = None
    if sig is not None:
        return sig[0]
    sig = inspect.signature(fn)
    target = fn
    while isinstance(target, partial):
        target = target.func
    target = inspect.unwrap(target)
    if isinstance(target, type):
        target = target.__init__
    if not inspect.isfunction(target) and not inspect.ismethod(target):
        target = target.__call__
    if sys.version_info < (3, 11):
        declared = target.__func__ if inspect.ismethod(target) else target
        if inspect.isfunction(declared):
            # Python 3.10 adds Optional[T] for default=None. Evaluate an
            # annotation-only function so declared types match Python 3.11+.
            target = FunctionType(declared.__code__, declared.__globals__, closure=declared.__closure__)
            target.__annotations__ = declared.__annotations__
    try:
        hints = get_type_hints(target, include_extras=True)
    except NameError:
        # Local endpoint/model declarations are common in app factories. Resolve
        # them while registration still has access to the defining stack.
        localns = {}
        frame = inspect.currentframe()
        try:
            frames = []
            while frame is not None:
                frames.append(frame)
                frame = frame.f_back
            for frame in reversed(frames):
                localns.update(frame.f_locals)
            hints = get_type_hints(target, localns=localns, include_extras=True)
        finally:
            del frame
            del frames
    sig = sig.replace(
        parameters=[p.replace(annotation=hints.get(p.name, p.annotation))
                    for p in sig.parameters.values()],
        return_annotation=hints.get("return", sig.return_annotation),
    )
    try:
        _SIG_CACHE[fn] = [sig, None]
    except TypeError:
        pass
    return sig


def is_async_callable(fn: Callable) -> bool:
    return inspect.iscoroutinefunction(fn) or inspect.iscoroutinefunction(getattr(fn, "__call__", None))


def get_bindings(fn: Callable):
    """Prepare immutable argument instructions beside the resolved signature."""
    from ...di import Depends, _registry
    from ...params import Query, Header, Body, Cookie, Form, File, Path
    from starlette.requests import Request
    from starlette.websockets import WebSocket

    signature = get_signature(fn)
    try:
        cached = _SIG_CACHE.get(fn)
    except TypeError:
        cached = None
    if cached is not None and cached[1] is not None:
        return cached[1]
    target = fn
    while isinstance(target, partial):
        target = target.func
    target = inspect.unwrap(target)
    target = target if inspect.isfunction(target) else getattr(target, "__call__", target)
    if inspect.isgeneratorfunction(target) or inspect.isasyncgenfunction(target):
        raise TypeError("Generator dependencies are not supported; use application lifespan for resources")
    bindings = []
    for p in signature.parameters.values():
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        ann, default = p.annotation, p.default
        if ann in (Request, WebSocket):
            kind, value = "request", ann
        elif isinstance(default, Depends):
            value = default.dependency if default.dependency is not None else ann
            if value is inspect.Parameter.empty:
                raise TypeError(f"Dependency parameter '{p.name}' requires a type annotation")
            kind = "dependency"
        elif default is inspect.Parameter.empty and ann in _registry:
            kind, value = "dependency", ann
        elif isinstance(default, (Header, Query)):
            from ..compiler import _build_typed_descriptor, KIND_HEADER, KIND_QUERY
            kind = "marker"
            value = _build_typed_descriptor(p.name, KIND_HEADER if isinstance(default, Header) else KIND_QUERY, ann, default)
        elif isinstance(default, (Body, Cookie, Form, File, Path)):
            raise TypeError(f"{type(default).__name__} is not supported in dependency parameter '{p.name}'; use a typed Request instead")
        elif default is not inspect.Parameter.empty:
            kind, value = "default", default
        elif isinstance(fn, type) and fn in _registry and ann is inspect.Parameter.empty:
            raise TypeError(f"Parameter '{p.name}' in '{fn.__name__}' has no type annotation; cannot resolve dependency.")
        else:
            raise TypeError(f"Cannot resolve dependency parameter '{p.name}' in {fn!r}")
        bindings.append((p.name, p.kind == inspect.Parameter.POSITIONAL_ONLY, kind, value))
    bindings = tuple(bindings)
    if cached is not None:
        cached[1] = bindings
    return bindings


def prepare_dependency(fn: Callable, visited: set = None, *, overrides=None, captured=False) -> None:
    """Validate lifetimes using prepared edges, including current overrides.

    A singleton may capture only explicitly singleton provider classes. Ordinary
    callables are request-local even when their signature contains no inputs.
    """
    from ...di import _registry, _scopes, SCOPE_SINGLETON
    active = set() if visited is None else set(visited)
    completed = set()

    def visit(provider, is_captured):
        state = (provider, is_captured)
        if provider in active:
            raise TypeError(f"Circular dependency detected while preparing {provider!r}")
        if state in completed:
            return
        active.add(provider)
        try:
            singleton = isinstance(provider, type) and provider in _registry and _scopes[provider] == SCOPE_SINGLETON
            bindings = get_bindings(provider)
            if is_captured and not singleton:
                raise TypeError(f"Singleton dependency cannot capture request/transient or callable dependency {provider!r}; use a request-scoped parent or a singleton provider class")
            if overrides is not None and provider in overrides and overrides[provider] is not provider:
                replacement = overrides[provider]
                if callable(replacement):
                    visit(replacement, is_captured)
            else:
                for name, positional, kind, value in bindings:
                    if singleton and kind in ("request", "marker"):
                        raise TypeError(f"Singleton dependency {provider!r} cannot capture request parameter '{name}'; use a request-scoped parent")
                    if kind == "dependency":
                        visit(value, singleton)
            completed.add(state)
        finally:
            active.remove(provider)

    visit(fn, captured)
