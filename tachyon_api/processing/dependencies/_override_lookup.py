# HOT PATH — looks up the `dependency_overrides` registry (used by tests and DI overrides).
#
# Returns the registered value or `_SENTINEL`. Callers must compare against
# `_SENTINEL` instead of `None` because `None` is a valid override value.
#
# Reads `app.dependency_overrides` *lazily* at lookup time so the resolver
# can be constructed before Tachyon's `dependency_overrides` attribute exists.

_SENTINEL = object()


class OverrideLookup:
    """Answers: "is there a registered override for this dependency key?" """

    __slots__ = ("_app",)

    def __init__(self, app) -> None:
        self._app = app

    def get_override(self, key):
        return self._app.dependency_overrides.get(key, _SENTINEL)
