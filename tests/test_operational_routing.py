"""Prune impossible overlapping misses without changing routing precedence."""
from tachyon_api.routing.trie import RadixTrie


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
