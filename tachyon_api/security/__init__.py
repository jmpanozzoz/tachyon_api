"""Authentication schemes — Bearer, Basic, API keys (header/query/cookie), OAuth2."""

from ._api_key_cookie import APIKeyCookie
from ._api_key_header import APIKeyHeader
from ._api_key_query import APIKeyQuery
from ._basic_credentials import HTTPBasicCredentials
from ._bearer_credentials import HTTPAuthorizationCredentials
from ._http_basic import HTTPBasic
from ._http_bearer import HTTPBearer
from ._oauth2_bearer import OAuth2PasswordBearer

__all__ = [
    "HTTPAuthorizationCredentials",
    "HTTPBasicCredentials",
    "HTTPBearer",
    "HTTPBasic",
    "APIKeyHeader",
    "APIKeyQuery",
    "APIKeyCookie",
    "OAuth2PasswordBearer",
]
