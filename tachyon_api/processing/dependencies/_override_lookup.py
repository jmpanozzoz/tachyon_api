# HOT PATH — looks up the `dependency_overrides` registry (used by tests and DI overrides).
#
# Returns the resolved override value (invoking the override factory if callable)
# or `_SENTINEL` if no override is registered.  Callers must compare against
# `_SENTINEL` instead of `None` because `None` is a valid override value.
#
# Reads `app.dependency_overrides` *lazily* at lookup time so the resolver
# can be constructed before Tachyon's `dependency_overrides` attribute exists.

from typing import Any

_SENTINEL = object()


class OverrideLookup:
    """Answers: "is there a registered override for this dependency key?" """

    __slots__ = ("_app",)

    def __init__(self, app) -> None:
        self._app = app

    def lookup(self, key: Any) -> Any:
        overrides = self._app.dependency_overrides
        if key not in overrides:
            return _SENTINEL
        override = overrides[key]
        if callable(override):
            return override()
        return override
