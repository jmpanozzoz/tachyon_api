"""Stream error recognized by multipart cleanup and HTTP validation handling."""


class RequestBodyTooLarge(OSError):
    """Raised before buffering bytes beyond the configured request limit."""
