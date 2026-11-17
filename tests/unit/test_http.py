"""Unit tests for SafeHttpClient, SSRF guards, rate limiting, and caching."""

from pathlib import Path
from unittest.mock import patch

import pytest
import respx
from httpx import Response

from alphalens.config import Settings
from alphalens.data.errors import (
    DomainNotAllowed,
    InsecureScheme,
    NetworkDisabledError,
    ResponseTooLarge,
    TooManyRedirects,
    UnexpectedContentType,
    UnsafeAddress,
    UpstreamError,
)
from alphalens.data.http import SafeHttpClient


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Fixture providing isolated Settings configured for testing."""
    return Settings(
        app_env="test",
        cache_dir=tmp_path / "cache",
        upload_dir=tmp_path / "uploads",
        allowed_domains=["api.bseindia.com", "nsetools.com", "*.nseindia.com"],
        http_offline=False,  # explicit test execution
        http_rate_limit_per_second=100.0,  # avoid artificial slowdown in unit tests
    )


def test_http_offline_guard(test_settings: Settings) -> None:
    """Offline guard raises NetworkDisabledError when http_offline is True."""
    test_settings.http_offline = True
    client = SafeHttpClient(settings=test_settings)
    with pytest.raises(NetworkDisabledError):
        client.get("https://api.bseindia.com/data")


def test_http_insecure_schemes_and_ports_rejected(test_settings: Settings) -> None:
    """Rejects non-https, userinfo, non-standard ports, and IP-literal hostnames."""
    client = SafeHttpClient(settings=test_settings)

    # 1. Plain HTTP
    with pytest.raises(InsecureScheme) as exc1:
        client.get("http://api.bseindia.com/data")
    assert "only https://" in str(exc1.value)

    # 2. Userinfo in URL
    with pytest.raises(InsecureScheme) as exc2:
        client.get("https://user:pass@api.bseindia.com/data")
    assert "userinfo" in str(exc2.value)

    # 3. Non-default port
    with pytest.raises(InsecureScheme) as exc3:
        client.get("https://api.bseindia.com:8443/data")
    assert "Non-default port" in str(exc3.value)

    # 4. IP literal host
    with pytest.raises(InsecureScheme) as exc4:
        client.get("https://13.235.1.1/data")
    assert "IP literal host" in str(exc4.value)


def test_http_non_allowlisted_host_rejected(test_settings: Settings) -> None:
    """Hostnames outside Settings.allowed_domains are blocked with DomainNotAllowed."""
    client = SafeHttpClient(settings=test_settings)

    with pytest.raises(DomainNotAllowed) as exc:
        client.get("https://evil-financial-data.com/feed")
    assert "evil-financial-data.com" in str(exc.value)


@patch("socket.getaddrinfo")
def test_http_ssrf_private_and_reserved_ips_blocked(
    mock_getaddrinfo: pytest.MonkeyPatch, test_settings: Settings
) -> None:
    """DNS resolving to private, loopback, link-local, or reserved IPs raises UnsafeAddress."""
    client = SafeHttpClient(settings=test_settings)

    bad_ips = [
        "127.0.0.1",  # Loopback
        "10.0.0.1",  # RFC 1918 Private
        "192.168.1.1",  # RFC 1918 Private
        "169.254.169.254",  # AWS/Cloud metadata
        "::1",  # IPv6 Loopback
        "fc00::1",  # IPv6 Unique Local
    ]

    for ip in bad_ips:
        # Mock getaddrinfo returning the bad IP
        mock_getaddrinfo.return_value = [(2, 1, 6, "", (ip, 443))]
        with pytest.raises(UnsafeAddress) as exc:
            client.get("https://api.bseindia.com/quotes")
        assert "non-public or reserved" in str(exc.value)


@respx.mock
@patch("socket.getaddrinfo")
def test_http_redirect_hops_and_ssrf_validation(
    mock_getaddrinfo: pytest.MonkeyPatch, test_settings: Settings
) -> None:
    """Redirects validate domain, SSRF, and enforce maximum 3 hops."""
    # Mock DNS resolving to a safe public IP
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
    client = SafeHttpClient(settings=test_settings)

    # 1. Redirect to a non-allowlisted domain is blocked
    respx.get("https://api.bseindia.com/initial").mock(
        return_value=Response(302, headers={"Location": "https://untrusted-site.com/target"})
    )
    with pytest.raises(DomainNotAllowed):
        client.get("https://api.bseindia.com/initial")

    # 2. More than 3 redirects raises TooManyRedirects
    respx.get("https://api.bseindia.com/hop1").mock(
        return_value=Response(302, headers={"Location": "https://api.bseindia.com/hop2"})
    )
    respx.get("https://api.bseindia.com/hop2").mock(
        return_value=Response(302, headers={"Location": "https://api.bseindia.com/hop3"})
    )
    respx.get("https://api.bseindia.com/hop3").mock(
        return_value=Response(302, headers={"Location": "https://api.bseindia.com/hop4"})
    )
    respx.get("https://api.bseindia.com/hop4").mock(
        return_value=Response(302, headers={"Location": "https://api.bseindia.com/final"})
    )

    with pytest.raises(TooManyRedirects):
        client.get("https://api.bseindia.com/hop1")


@respx.mock
@patch("socket.getaddrinfo")
def test_http_response_size_limits(
    mock_getaddrinfo: pytest.MonkeyPatch, test_settings: Settings
) -> None:
    """Enforces Content-Length and streaming chunk size limits."""
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
    client = SafeHttpClient(settings=test_settings)

    # 1. Blocked via Content-Length header
    respx.get("https://api.bseindia.com/huge_header").mock(
        return_value=Response(200, headers={"Content-Length": "15000000"}, content=b"start")
    )
    with pytest.raises(ResponseTooLarge):
        client.get("https://api.bseindia.com/huge_header", max_bytes=1000)

    # 2. Blocked via chunk streaming (Content-Length missing)
    big_body = b"X" * 2000
    respx.get("https://api.bseindia.com/huge_stream").mock(
        return_value=Response(200, content=big_body)
    )
    with pytest.raises(ResponseTooLarge):
        client.get("https://api.bseindia.com/huge_stream", max_bytes=1000)


@respx.mock
@patch("socket.getaddrinfo")
def test_http_content_type_validation(
    mock_getaddrinfo: pytest.MonkeyPatch, test_settings: Settings
) -> None:
    """MIME type mismatch raises UnexpectedContentType."""
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
    client = SafeHttpClient(settings=test_settings)

    respx.get("https://api.bseindia.com/feed").mock(
        return_value=Response(
            200, headers={"Content-Type": "text/html; charset=utf-8"}, content=b"<h1>Hello</h1>"
        )
    )

    with pytest.raises(UnexpectedContentType) as exc:
        client.get("https://api.bseindia.com/feed", expected_content_types={"application/json"})
    assert "text/html" in str(exc.value)


@respx.mock
@patch("socket.getaddrinfo")
@patch("time.sleep")
def test_http_retries_and_exponential_backoff(
    mock_sleep: pytest.MonkeyPatch,
    mock_getaddrinfo: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """503 then 200 succeeds with backoff; 404 does NOT retry."""
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
    client = SafeHttpClient(settings=test_settings)

    # 1. 503 then 200 -> Retries and succeeds
    route_503 = respx.get("https://api.bseindia.com/unstable").mock(
        side_effect=[
            Response(503, content=b"Service Unavailable"),
            Response(200, content=b'{"status": "ok"}'),
        ]
    )
    res = client.get("https://api.bseindia.com/unstable")
    assert res.body == '{"status": "ok"}'
    assert route_503.call_count == 2
    mock_sleep.assert_called()

    # 2. 404 Client error -> No retry
    route_404 = respx.get("https://api.bseindia.com/missing").mock(
        return_value=Response(404, content=b"Not Found")
    )
    with pytest.raises(UpstreamError) as exc_404:
        client.get("https://api.bseindia.com/missing")
    assert exc_404.value.status_code == 404
    assert route_404.call_count == 1


@respx.mock
@patch("socket.getaddrinfo")
@patch("time.sleep")
def test_http_retry_after_header_handling(
    mock_sleep: pytest.MonkeyPatch,
    mock_getaddrinfo: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """Rate limit 429 parses Retry-After and pauses."""
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
    client = SafeHttpClient(settings=test_settings)

    route_429 = respx.get("https://api.bseindia.com/throttled").mock(
        side_effect=[
            Response(429, headers={"Retry-After": "2"}, content=b"Rate limited"),
            Response(200, content=b'{"ok": true}'),
        ]
    )

    res = client.get("https://api.bseindia.com/throttled")
    assert res.body == '{"ok": true}'
    assert route_429.call_count == 2
    mock_sleep.assert_called_with(2.0)


@respx.mock
@patch("socket.getaddrinfo")
def test_http_logging_never_contains_query_string(
    mock_getaddrinfo: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """Logs contain host, path, status, and duration; query strings are stripped."""
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
    client = SafeHttpClient(settings=test_settings)

    respx.get("https://api.bseindia.com/search").mock(
        return_value=Response(200, content=b'{"results": []}')
    )

    with patch("alphalens.data.http.logger.info") as mock_log:
        client.get("https://api.bseindia.com/search?api_key=SECRET&token=CONFIDENTIAL")

        mock_log.assert_called_once()
        log_kwargs = mock_log.call_args[1]
        assert log_kwargs["host"] == "api.bseindia.com"
        assert log_kwargs["path"] == "/search"
        assert "SECRET" not in str(log_kwargs)
        assert "CONFIDENTIAL" not in str(log_kwargs)


@respx.mock
@patch("socket.getaddrinfo")
def test_http_rate_limiter_throttles(
    mock_getaddrinfo: pytest.MonkeyPatch, test_settings: Settings
) -> None:
    """Per-host token bucket throttles requests."""
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
    test_settings.http_rate_limit_per_second = 2.0  # 2 req/sec
    client = SafeHttpClient(settings=test_settings)

    respx.get("https://nsetools.com/quote").mock(
        return_value=Response(200, content=b'{"price": 100}')
    )

    with patch("time.sleep") as mock_sleep:
        client.get("https://nsetools.com/quote", use_cache=False)
        client.get("https://nsetools.com/quote", use_cache=False)
        # 3rd request should trigger bucket acquire sleep
        client.get("https://nsetools.com/quote", use_cache=False)
        assert mock_sleep.called
