"""Prune impossible overlapping misses without changing routing precedence."""
from tachyon_api.routing.trie import RadixTrie
import random

import pytest


def test_impossible_static_suffix_does_not_expand_every_overlap():
    trie = RadixTrie()
    for mask in range(128):
        parts = ["fixed" if mask & (1 << i) else f"{{p{i}}}" for i in range(7)]
        trie.add("/overlap/" + "/".join(parts) + "/end", "GET", object())
    lookups = []
    class CountedDict(dict):
        def get(self, key, default=None):
            lookups.append(key)
            return super().get(key, default)
    def count(node):
        for child in node.static.values():
            count(child)
        if node.param_child is not None:
            count(node.param_child)
        node.static = CountedDict(node.static)
    count(trie._root)
    assert trie.match("/overlap/" + "/".join(["fixed"] * 7) + "/missing", "GET")[0] == 0
    assert len(lookups) < 10


def test_dynamic_last_segment_keeps_fallback_and_static_405_priority():
    trie = RadixTrie()
    static, dynamic = object(), object()
    trie.add("/a/static/end", "GET", static)
    trie.add("/a/{value}/{last}", "POST", dynamic)
    result = trie.match("/a/static/unknown", "POST")
    assert result[:3] == (2, dynamic, {"value": "static", "last": "unknown"})
    assert trie.match("/a/static/end", "POST")[0] == 1


def test_suffix_pruning_preserves_unicode_repeated_slashes_and_root():
    trie = RadixTrie()
    terminal, fallback, root = object(), object(), object()
    trie.add("/a/static/finñ", "GET", terminal)
    trie.add("/a/{value}/tail", "GET", fallback)
    trie.add("/", "GET", root)
    assert trie.match("//a//static//finñ///", "GET")[1] is terminal
    assert trie.match("/a/static/tail/", "GET")[1] is fallback
    assert trie.match("///", "GET")[1] is root


@pytest.mark.parametrize("seed", [142, 143, 144, 145])
def test_generated_routes_match_declarative_static_priority(seed):
    rng = random.Random(seed)
    trie = RadixTrie()
    terminals, patterns = {}, []
    words = ["fixed", "users", "end", "δ", "ñ", "a", "b"]
    for index in range(150):
        segments = [f"{{p{i}}}" if rng.randrange(3) == 0 else rng.choice(words)
                    for i in range(rng.randrange(5))]
        shape = tuple(None if segment.startswith("{") else segment for segment in segments)
        names = [segment[1:-1] for segment in segments if segment.startswith("{")]
        method = rng.choice(["GET", "POST", "PUT"])
        handler = f"handler-{index}"
        trie.add("/" + "/".join(segments), method, handler)
        terminals.setdefault(shape, {})[method] = (handler, names)
        patterns.append(segments)
    for _ in range(500):
        segments = [rng.choice(words + ["42", "missing"]) if part.startswith("{") else part
                    for part in rng.choice(patterns)]
        if segments and rng.randrange(3) == 0:
            segments[rng.randrange(len(segments))] = "missing"
        method = rng.choice(["GET", "POST", "PUT", "DELETE", "get"])
        candidates = [(shape, methods) for shape, methods in terminals.items()
                      if len(shape) == len(segments) and all(p is None or p == value for p, value in zip(shape, segments))]
        if not candidates:
            expected = (0, None, {}, None)
        else:
            shape, methods = max(candidates, key=lambda pair: tuple(part is not None for part in pair[0]))
            selected = methods.get(method.upper())
            if selected is None:
                expected = (1, None, {}, ", ".join(sorted(methods)))
            else:
                handler, names = selected
                values = [value for part, value in zip(shape, segments) if part is None]
                expected = (2, handler, dict(zip(names, values)), None)
        slash = "//" if rng.randrange(2) else "/"
        path = slash + slash.join(segments) + slash
        assert trie.match(path, method) == expected, (seed, path, method)
