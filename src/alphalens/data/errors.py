"""Exception hierarchy for external data fetchers and HTTP clients."""


class FetchError(Exception):
    """Base exception for all external data fetching errors.

    Ensures that error messages do not leak full query strings or credentials.
    """


class DomainNotAllowed(FetchError):
    """Raised when the target hostname is not included in Settings.allowed_domains."""


class InsecureScheme(FetchError):
    """Raised when a non-HTTPS URL, userinfo, non-standard port, or IP literal is supplied."""


class UnsafeAddress(FetchError):
    """Raised when a resolved IP address falls within private, loopback, or reserved ranges (SSRF)."""


class ResponseTooLarge(FetchError):
    """Raised when a response payload exceeds the configured maximum byte ceiling."""


class UnexpectedContentType(FetchError):
    """Raised when the received Content-Type header does not match expected MIME types."""


class TooManyRedirects(FetchError):
    """Raised when the client exceeds the maximum allowed redirect hops (3 hops)."""


class UpstreamError(FetchError):
    """Raised when an external server responds with an unhandled 4xx or 5xx HTTP status."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class NetworkDisabledError(FetchError):
    """Raised when a real network request is attempted while Settings.http_offline is active."""


class BenchmarkUnavailable(FetchError):
    """Raised when the canonical Nifty 50 TRI benchmark reference file cannot be located."""
