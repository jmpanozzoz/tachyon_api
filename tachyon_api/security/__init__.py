"""Authentication schemes — Bearer, Basic, API keys (header/query/cookie), OAuth2."""

from ._api_keys import APIKeyCookie, APIKeyHeader, APIKeyQuery
from ._credentials import HTTPAuthorizationCredentials, HTTPBasicCredentials
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
