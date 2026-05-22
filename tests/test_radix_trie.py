"""
HF-06: Unit tests for RadixTrie — covers edge cases not exercised by integration tests.
"""

import pytest
from tachyon_api.routing.trie import RadixTrie, _NOT_FOUND, _METHOD_NOT_ALLOWED, _FOUND


def _h():
    """Dummy handler."""
    pass


# ── Basic matching ─────────────────────────────────────────────────────────────

class TestBasicRouteMatching:
    def test_static_route_found(self):
        t = RadixTrie()
        t.add("/hello", "GET", _h)
        status, handler, params, _ = t.match("/hello", "GET")
        assert status == _FOUND
        assert handler is _h
        assert params == {}

    def test_root_path_registration(self):
        t = RadixTrie()
        t.add("/", "GET", _h)
        status, handler, params, _ = t.match("/", "GET")
        assert status == _FOUND
        assert handler is _h

    def test_not_found_returns_correct_status(self):
        t = RadixTrie()
        t.add("/exists", "GET", _h)
        status, handler, params, _ = t.match("/does-not-exist", "GET")
        assert status == _NOT_FOUND
        assert handler is None

    def test_empty_trie_returns_not_found(self):
        t = RadixTrie()
        status, _, _, _ = t.match("/anything", "GET")
        assert status == _NOT_FOUND

    def test_path_case_sensitive(self):
        t = RadixTrie()
        t.add("/Users", "GET", _h)
        assert t.match("/Users", "GET")[0] == _FOUND
        assert t.match("/users", "GET")[0] == _NOT_FOUND

    def test_trailing_slash_treated_as_equivalent(self):
        # _segments filters empty strings, so /users/ == /users in the trie.
        # This is intentional — trailing slashes are transparently ignored.
        t = RadixTrie()
        t.add("/users", "GET", _h)
        assert t.match("/users", "GET")[0] == _FOUND
        assert t.match("/users/", "GET")[0] == _FOUND  # trailing slash ignored

    def test_double_slash_treated_as_empty_segment(self):
        t = RadixTrie()
        t.add("/users/admin", "GET", _h)
        # //users/admin has an extra empty segment ignored by _segments
        assert t.match("//users/admin", "GET")[0] == _FOUND

    def test_deep_static_path(self):
        t = RadixTrie()
        t.add("/a/b/c/d/e/f/g/h/i/j", "GET", _h)
        status, _, params, _ = t.match("/a/b/c/d/e/f/g/h/i/j", "GET")
        assert status == _FOUND
        assert params == {}


# ── Path parameters ────────────────────────────────────────────────────────────

class TestPathParameters:
    def test_single_param_extracted(self):
        t = RadixTrie()
        t.add("/users/{user_id}", "GET", _h)
        status, _, params, _ = t.match("/users/42", "GET")
        assert status == _FOUND
        assert params == {"user_id": "42"}

    def test_multiple_params_extracted(self):
        t = RadixTrie()
        t.add("/users/{user_id}/posts/{post_id}", "GET", _h)
        status, _, params, _ = t.match("/users/99/posts/7", "GET")
        assert status == _FOUND
        assert params == {"user_id": "99", "post_id": "7"}

    def test_param_with_underscore_name(self):
        t = RadixTrie()
        t.add("/items/{item_slug}", "GET", _h)
        _, _, params, _ = t.match("/items/my-widget", "GET")
        assert params == {"item_slug": "my-widget"}

    def test_static_takes_priority_over_param(self):
        t = RadixTrie()
        static_h = lambda: "static"
        param_h = lambda: "param"
        t.add("/users/admin", "GET", static_h)
        t.add("/users/{id}", "GET", param_h)
        _, handler, params, _ = t.match("/users/admin", "GET")
        assert handler is static_h
        assert params == {}

    def test_param_route_falls_through_to_param(self):
        t = RadixTrie()
        static_h = lambda: "static"
        param_h = lambda: "param"
        t.add("/users/admin", "GET", static_h)
        t.add("/users/{id}", "GET", param_h)
        _, handler, params, _ = t.match("/users/123", "GET")
        assert handler is param_h
        assert params == {"id": "123"}

    def test_param_values_are_strings(self):
        t = RadixTrie()
        t.add("/items/{id}", "GET", _h)
        _, _, params, _ = t.match("/items/42", "GET")
        assert isinstance(params["id"], str)

    def test_each_match_allocates_fresh_dict(self):
        t = RadixTrie()
        t.add("/users/{id}", "GET", _h)
        _, _, params1, _ = t.match("/users/1", "GET")
        _, _, params2, _ = t.match("/users/2", "GET")
        assert params1 is not params2
        assert params1 == {"id": "1"}
        assert params2 == {"id": "2"}


# ── Method handling ────────────────────────────────────────────────────────────

class TestMethodHandling:
    def test_method_not_allowed_returns_correct_status(self):
        t = RadixTrie()
        t.add("/items", "GET", _h)
        status, handler, _, allow = t.match("/items", "POST")
        assert status == _METHOD_NOT_ALLOWED
        assert handler is None
        assert allow == "GET"

    def test_allow_header_is_presorted_string(self):
        t = RadixTrie()
        t.add("/endpoint", "POST", _h)
        t.add("/endpoint", "GET", _h)
        t.add("/endpoint", "DELETE", _h)
        _, _, _, allow = t.match("/endpoint", "PATCH")
        assert allow == "DELETE, GET, POST"

    def test_allow_header_single_method(self):
        t = RadixTrie()
        t.add("/item", "GET", _h)
        _, _, _, allow = t.match("/item", "POST")
        assert allow == "GET"

    def test_multiple_methods_same_path(self):
        get_h = lambda: "get"
        post_h = lambda: "post"
        t = RadixTrie()
        t.add("/data", "GET", get_h)
        t.add("/data", "POST", post_h)
        assert t.match("/data", "GET")[1] is get_h
        assert t.match("/data", "POST")[1] is post_h

    def test_duplicate_registration_overwrites(self):
        first = lambda: "first"
        second = lambda: "second"
        t = RadixTrie()
        t.add("/path", "GET", first)
        t.add("/path", "GET", second)
        _, handler, _, _ = t.match("/path", "GET")
        assert handler is second

    def test_no_params_returns_empty_dict_for_static_route(self):
        from collections.abc import Mapping
        t = RadixTrie()
        t.add("/static", "GET", _h)
        _, _, params, _ = t.match("/static", "GET")
        assert params == {}
        assert isinstance(params, Mapping)  # MappingProxyType or dict, both are Mappings
