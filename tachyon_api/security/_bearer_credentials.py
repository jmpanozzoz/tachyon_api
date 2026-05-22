# Value object for `scheme + credentials` parsed from an Authorization header.


class HTTPAuthorizationCredentials:
    """Holds the scheme + credentials extracted from an Authorization header."""

    __slots__ = ("scheme", "credentials")

    def __init__(self, scheme: str, credentials: str) -> None:
        self.scheme = scheme
        self.credentials = credentials
