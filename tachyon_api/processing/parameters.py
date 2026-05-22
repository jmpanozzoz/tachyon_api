"""Parameter extraction pipeline — composes atomic extractors per kind.

This is the pure-Python fallback.  Production builds with `[fast]` Cython
compiled will use ``parameters.pyx`` (single-file, semantically identical)
loaded as ``parameters.cpython-*.so``.  Both implementations produce identical
output for the same input.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

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

_DEFAULT_MAX_BODY_SIZE = 2 * 1024 * 1024  # 2 MB — override via Tachyon(max_body_size=...)


class ParameterProcessor:
    """Orchestrates parameter extraction by delegating to atomic extractors."""

    __slots__ = (
        "app",
        "_body", "_query_scalar", "_query_list",
        "_header", "_cookie", "_form", "_file", "_path",
    )

    def __init__(self, app_instance) -> None:
        self.app = app_instance
        max_body_size = getattr(app_instance, "max_body_size", _DEFAULT_MAX_BODY_SIZE)
        self._body = BodyExtractor(max_body_size)
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
                args[i] = self.app._dependency_resolver.resolve_dependency(
                    p.annotation, dependency_cache
                )
                continue

            # ── User-input extraction (delegated to atomic extractors) ────
            if kind == KIND_BODY:
                result = await self._body.extract(p, request)

            elif kind == KIND_QUERY:
                extractor = self._query_list if p.is_list else self._query_scalar
                result = extractor.extract(p, request.query_params)

            elif kind == KIND_HEADER:
                result = self._header.extract(p, request)

            elif kind == KIND_COOKIE:
                result = self._cookie.extract(p, request)

            elif kind == KIND_FORM:
                if form_data is None:
                    try:
                        form_data = await request.form()
                    except Exception:
                        return args, validation_error_response("Failed to parse form data"), bg
                result = self._form.extract(p, form_data)

            elif kind == KIND_FILE:
                if form_data is None:
                    try:
                        form_data = await request.form()
                    except Exception:
                        return args, validation_error_response("Failed to parse form data"), bg
                result = self._file.extract(p, form_data)

            elif kind == KIND_PATH or kind == KIND_PATH_IMPLICIT:
                result = self._path.extract(p, request.path_params)

            else:
                # Unknown kind — defensive fallback
                continue

            if result.error is not None:
                return args, result.error, bg
            args[i] = result.value

        return args, None, bg
