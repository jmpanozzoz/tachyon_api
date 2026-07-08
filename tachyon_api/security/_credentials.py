# Value objects for parsed authentication credentials.


class HTTPAuthorizationCredentials:
    """Holds the scheme + credentials extracted from an Authorization header."""

    __slots__ = ("scheme", "credentials")

    def __init__(self, scheme: str, credentials: str) -> None:
        self.scheme = scheme
        self.credentials = credentials


class HTTPBasicCredentials:
    """Holds the decoded username + password from a Basic auth header."""

    __slots__ = ("username", "password")

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
