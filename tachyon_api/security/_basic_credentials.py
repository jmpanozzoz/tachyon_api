# Value object for decoded Basic-auth `username + password`.


class HTTPBasicCredentials:
    """Holds the decoded username + password from a Basic auth header."""

    __slots__ = ("username", "password")

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
