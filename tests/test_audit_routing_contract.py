"""Routing contracts shared by the Python and compiled implementations."""
import pytest

from tachyon_api.routing.trie import RadixTrie


def handler():
    return None


@pytest.mark.parametrize('path', ['/café/東京/🙂', '//café//東京/🙂/'])
def test_unicode_segments_and_slash_normalization(path):
    trie = RadixTrie()
    trie.add('/café/{city}/{symbol}', 'GET', handler)
    assert trie.match(path, 'GET') == (
        2, handler, {'city': '東京', 'symbol': '🙂'}, None,
    )


def test_shared_wildcard_names_belong_to_terminal_and_method():
    trie = RadixTrie()
    trie.add('/{user}/profile', 'GET', handler)
    trie.add('/{account}/settings', 'GET', handler)
    trie.add('/{target}/profile', 'POST', handler)
    assert trie.match('/alice/profile', 'GET')[2] == {'user': 'alice'}
    assert trie.match('/alice/settings', 'GET')[2] == {'account': 'alice'}
    assert trie.match('/alice/profile', 'POST')[2] == {'target': 'alice'}


def test_static_dead_end_backtracks_and_discards_stale_captures():
    trie = RadixTrie()
    trie.add('/a/fixed/{wrong}/tail', 'GET', handler)
    trie.add('/a/{first}/{second}/end', 'GET', handler)
    assert trie.match('/a/fixed/東京/end', 'GET') == (
        2, handler, {'first': 'fixed', 'second': '東京'}, None,
    )


def test_complete_static_match_has_priority_regardless_of_method():
    trie = RadixTrie()
    trie.add('/users/me', 'POST', handler)
    trie.add('/users/{name}', 'GET', handler)
    assert trie.match('/users/me', 'GET') == (1, None, {}, 'POST')


def test_static_nonterminal_does_not_hide_wildcard_terminal():
    trie = RadixTrie()
    trie.add('/users/me/details', 'GET', handler)
    trie.add('/users/{name}', 'GET', handler)
    assert trie.match('/users/me', 'GET')[2] == {'name': 'me'}


def test_duplicate_terminal_updates_parameter_names():
    trie = RadixTrie()
    trie.add('/{old}', 'GET', handler)
    trie.add('/{new}', 'GET', handler)
    assert trie.match('/42', 'GET')[2] == {'new': '42'}
