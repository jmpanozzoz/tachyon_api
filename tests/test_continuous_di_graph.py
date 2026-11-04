"""Dependency preparation must visit shared DAG nodes once per lifetime context."""
import importlib

import pytest

from tachyon_api import Depends, Tachyon
from tachyon_api.di import injectable
from tachyon_api.processing.dependencies import DependencyResolver
from tachyon_api.processing.dependencies._sig_cache import prepare_dependency


def shared_graph(depth):
    @injectable
    class Leaf:
        pass
    classes = [Leaf]
    for index in range(depth):
        def constructor(self, left, right):
            self.left, self.right = left, right
        constructor.__annotations__ = {"left": classes[-1], "right": classes[-1]}
        classes.append(injectable(type(f"Shared{index}", (), {"__init__": constructor})))
    return classes


@pytest.mark.asyncio
async def test_shared_graph_preparation_is_linear_even_on_cached_resolution(monkeypatch):
    classes = shared_graph(14)
    module = importlib.import_module("tachyon_api.processing.dependencies._sig_cache")
    original = module.get_bindings
    visits = []
    def counted(provider):
        visits.append(provider)
        return original(provider)
    monkeypatch.setattr(module, "get_bindings", counted)
    app = Tachyon()
    cached = object()
    app.register_instance(classes[-1], cached)
    resolver = DependencyResolver(app)
    for _ in range(2):
        visits.clear()
        assert await resolver.resolve_class_dependency(classes[-1], {}, None) is cached
        assert len(visits) == len(classes)


def test_preparation_keeps_root_and_captured_lifetime_contexts_separate():
    def local_factory():
        return "request-local"
    @injectable
    class Singleton:
        def __init__(self, value=Depends(local_factory)):
            pass
    def root(first=Depends(local_factory), second=Depends(Singleton)):
        pass
    with pytest.raises(TypeError, match="Singleton dependency cannot capture"):
        prepare_dependency(root)


def test_completed_graph_does_not_hide_cycles_or_dynamic_override_changes():
    classes = shared_graph(3)
    @injectable
    class Replacement:
        def __init__(self, value):
            pass
    Replacement.__init__.__annotations__["value"] = classes[-1]
    with pytest.raises(TypeError, match="Circular dependency"):
        prepare_dependency(classes[-1], overrides={classes[0]: Replacement})
    prepare_dependency(classes[-1])
    with pytest.raises(TypeError, match="Singleton dependency cannot capture"):
        prepare_dependency(classes[-1], overrides={classes[0]: lambda: "request-local"})
    prepare_dependency(classes[-1])
