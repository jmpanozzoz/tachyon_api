"""Parameter extraction pipeline — composes atomic extractors per kind.

One Python implementation serves every installation.
"""

from __future__ import annotations

from typing import Optional, Tuple

from starlette.responses import JSONResponse

from ..background import BackgroundTasks
from ..responses import validation_error_response
from ._extractors import (
    BodyExtractor,
    CookieExtractor,
    FileExtractor,
    FormExtractor,
    HeaderExtractor,
    PathExtractor,
    QueryExtractor,
    QueryListExtractor,
)
from .compiler import (
    CompiledEndpoint,
    KIND_BG,
    KIND_BODY,
    KIND_COOKIE,
    KIND_DEP_CALLABLE,
    KIND_DEP_CLASS,
    KIND_FILE,
    KIND_FORM,
    KIND_HEADER,
    KIND_PATH,
    KIND_PATH_IMPLICIT,
    KIND_QUERY,
    KIND_REQUEST,
)
from .scope import TachyonScope

class ParameterProcessor:
    """Orchestrates parameter extraction by delegating to atomic extractors."""

    __slots__ = (
        "app",
        "_body", "_query_scalar", "_query_list",
        "_header", "_cookie", "_form", "_file", "_path",
    )

    def __init__(self, app_instance) -> None:
        self.app = app_instance
        self._body = BodyExtractor()
        self._query_scalar = QueryExtractor()
        self._query_list = QueryListExtractor()
        self._header = HeaderExtractor()
        self._cookie = CookieExtractor()
        self._form = FormExtractor()
        self._file = FileExtractor()
        self._path = PathExtractor()

    async def process_parameters(
        self,
        compiled: CompiledEndpoint,
        request: TachyonScope,
        dependency_cache,
    ) -> Tuple[list, Optional[JSONResponse], Optional[BackgroundTasks]]:
        args: list = [None] * compiled.param_count
        bg: Optional[BackgroundTasks] = None
        form_data = None

        for i, p in enumerate(compiled.params):
            kind = p.kind

            # ── Framework-level injections ────────────────────────────────
            if kind == KIND_REQUEST:
                args[i] = request.as_request()
                continue
            if kind == KIND_BG:
                if bg is None:
                    bg = BackgroundTasks()
                args[i] = bg
                continue
            if kind == KIND_DEP_CALLABLE:
                args[i] = await self.app._dependency_resolver.resolve_callable_dependency(
                    p.dependency, dependency_cache, request
                )
                continue
            if kind == KIND_DEP_CLASS:
                args[i] = await self.app._dependency_resolver.resolve_class_dependency(
                    p.annotation, dependency_cache, request
                )
                continue

            # ── User-input extraction (delegated to atomic extractors) ────
            # Each extractor returns a `(value, error)` plain tuple.  Tuple
            # unpacking is materially faster than NamedTuple attribute access
            # at request rate (~150ns/req saved with ≥2 params per request).
            if kind == KIND_BODY:
                val, err = await self._body.extract(p, request)

            elif kind == KIND_QUERY:
                extractor = self._query_list if p.is_list else self._query_scalar
                val, err = extractor.extract(p, request.query_params)

            elif kind == KIND_HEADER:
                val, err = self._header.extract(p, request)

            elif kind == KIND_COOKIE:
                val, err = self._cookie.extract(p, request)

            elif kind == KIND_FORM:
                if form_data is None:
                    try:
                        form_data = await request.form()
                    except Exception:
                        return args, validation_error_response("Failed to parse form data"), bg
                val, err = self._form.extract(p, form_data)

            elif kind == KIND_FILE:
                if form_data is None:
                    try:
                        form_data = await request.form()
                    except Exception:
                        return args, validation_error_response("Failed to parse form data"), bg
                val, err = self._file.extract(p, form_data)

            elif kind == KIND_PATH or kind == KIND_PATH_IMPLICIT:
                val, err = self._path.extract(p, request.path_params)

            else:
                # Unknown kind — defensive fallback
                continue

            if err is not None:
                return args, err, bg
            args[i] = val

        return args, None, bg
