"""Compatibility names preserve Uvicorn's normal response handling."""
from unittest.mock import patch

from tachyon_api import server


def test_legacy_writer_always_defers_without_touching_transport():
    class Untouchable:
        def __getattribute__(self, name):
            raise AssertionError(f'Legacy hook accessed {name}')

    assert server.tachyon_direct_write(Untouchable(), Untouchable()) is False


def test_server_run_preserves_explicit_uvicorn_configuration():
    app = object()
    with patch('uvicorn.run') as run:
        server.run(app, http='h11', host='127.0.0.1', port=9000)
    run.assert_called_once_with(app, http='h11', host='127.0.0.1', port=9000)


def test_legacy_protocol_is_standard_uvicorn_protocol():
    from uvicorn.protocols.http.h11_impl import H11Protocol

    assert server.TachyonHTTPProtocol is H11Protocol
