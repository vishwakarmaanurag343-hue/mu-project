"""Hardened, SSRF-protected, rate-limited HTTP client for external data fetchers."""

import contextlib
import fnmatch
import ipaddress
import random
import socket
import threading
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar
from urllib.parse import urlparse

import httpx

from alphalens.config import Settings, get_settings
from alphalens.data.cache import (
    CacheEntry,
    compute_http_cache_key,
    get_cached_response,
    get_disk_cache,
    store_cached_response,
)
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
from alphalens.logging import get_logger

logger = get_logger("alphalens.data.http")


class TokenBucket:
    """Thread-safe token bucket rate limiter for individual hostnames."""

    def __init__(self, rate_per_second: float, capacity: float | None = None) -> None:
        self.rate = rate_per_second
        self.capacity = capacity if capacity is not None else rate_per_second
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        """Acquire a token, blocking if bucket is empty."""
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                # Calculate sleep duration needed for next token
                wait_time = (1.0 - self.tokens) / self.rate
            time.sleep(max(0.001, wait_time))


class SafeHttpClient:
    """Hardened HTTP client enforcing SSRF protection, domain allowlists, and caching.

    Designed exclusively for synchronous data fetching in backend workers.
    """

    _rate_limiters: ClassVar[dict[str, TokenBucket]] = {}
    _rate_limiters_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._external_client = client

    def _get_rate_limiter(self, host: str) -> TokenBucket:
        with self._rate_limiters_lock:
            if host not in self._rate_limiters:
                self._rate_limiters[host] = TokenBucket(self.settings.http_rate_limit_per_second)
            return self._rate_limiters[host]

    def _validate_url_format(self, url: str) -> tuple[str, str, str]:
        """Validate URL scheme, userinfo, ports, and literal IP addresses.

        Returns (scheme, hostname, path).
        """
        parsed = urlparse(url)

        # 1. Reject non-https schemes
        if parsed.scheme.lower() != "https":
            raise InsecureScheme(f"Insecure scheme '{parsed.scheme}': only https:// is allowed")

        # 2. Reject userinfo (user:pass@host)
        if parsed.username or parsed.password:
            raise InsecureScheme("URLs with userinfo (user:pass@host) are forbidden")

        # 3. Reject non-default ports
        if parsed.port is not None and parsed.port != 443:
            raise InsecureScheme(
                f"Non-default port {parsed.port} is forbidden: only 443 is allowed"
            )

        # 4. Hostname check
        host = (parsed.hostname or "").lower()
        if not host:
            raise InsecureScheme("URL must contain a valid hostname")

        # 5. Reject literal IP addresses in hostname
        try:
            ipaddress.ip_address(host)
            raise InsecureScheme(f"IP literal host '{host}' is forbidden")
        except ValueError:
            pass  # Expected: hostname is a domain name, not an IP literal

        return parsed.scheme.lower(), host, parsed.path or "/"

    def _check_domain_allowlist(self, host: str) -> None:
        """Verify that hostname matches Settings.allowed_domains (exact or *.example.com)."""
        allowed = False
        for pattern in self.settings.allowed_domains:
            pattern = pattern.lower()
            if pattern.startswith("*."):
                # Wildcard pattern: *.example.com matches sub.example.com
                if fnmatch.fnmatch(host, pattern):
                    allowed = True
                    break
            elif host == pattern:
                allowed = True
                break

        if not allowed:
            raise DomainNotAllowed(f"Domain '{host}' is not in allowed domains list")

    def _check_ssrf_dns(self, host: str) -> None:
        """Resolve DNS and verify that NO resolved address is private, loopback, or reserved."""
        try:
            addr_info = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        except Exception as e:
            raise UnsafeAddress(f"DNS resolution failed for host '{host}': {e}") from e

        if not addr_info:
            raise UnsafeAddress(f"No IP addresses resolved for host '{host}'")

        for entry in addr_info:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError as e:
                raise UnsafeAddress(f"Invalid resolved IP '{ip_str}'") from e

            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_reserved
                or ip_obj.is_unspecified
            ):
                raise UnsafeAddress(
                    f"Resolved IP '{ip_str}' is non-public or reserved (SSRF guard)"
                )

    def _parse_retry_after(self, retry_after_header: str | None) -> float | None:
        """Parse Retry-After header as integer seconds or RFC 7231 HTTP-date."""
        if not retry_after_header:
            return None
        retry_str = retry_after_header.strip()
        try:
            # Seconds format
            return float(retry_str)
        except ValueError:
            pass

        try:
            dt = parsedate_to_datetime(retry_str)
            now = datetime.now(UTC)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            diff = (dt - now).total_seconds()
            return max(0.0, diff)
        except Exception:
            return None

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        expected_content_types: set[str] | None = None,
        max_bytes: int | None = None,
        namespace: str = "default",
        use_cache: bool = True,
        ttl: int | None = None,
    ) -> CacheEntry:
        """Execute a hardened HTTP GET request with SSRF validation, retries, and caching."""
        # 1. Offline guard
        if self.settings.is_offline:
            raise NetworkDisabledError("Network requests are disabled in current environment")

        effective_max_bytes = (
            max_bytes if max_bytes is not None else self.settings.http_max_response_bytes
        )
        effective_ttl = ttl
        if effective_ttl is None:
            effective_ttl = getattr(self.settings, f"cache_ttl_{namespace}", 3600)

        # 2. Check Cache
        cache = get_disk_cache(self.settings.cache_dir)
        cache_key = compute_http_cache_key("GET", url, params, namespace)

        if use_cache:
            cached_result = get_cached_response(cache, cache_key)
            if cached_result is not None:
                # Log cache hit
                parsed = urlparse(url)
                logger.info(
                    "http_request_completed",
                    host=parsed.hostname or "",
                    path=parsed.path or "/",
                    status=200,
                    bytes=len(str(cached_result.body)),
                    duration_ms=0,
                    attempt=1,
                    cache_hit=True,
                )
                return cached_result

        # 3. Setup timeouts
        timeouts = httpx.Timeout(
            connect=self.settings.http_connect_timeout,
            read=self.settings.http_read_timeout,
            write=self.settings.http_write_timeout,
            pool=self.settings.http_pool_timeout,
        )

        current_url = url
        redirect_hops = 0
        max_redirect_hops = 3

        while True:
            # Validate format & SSRF DNS for current URL
            _, host, path = self._validate_url_format(current_url)
            self._check_domain_allowlist(host)
            self._check_ssrf_dns(host)

            # Acquire host rate limit token
            limiter = self._get_rate_limiter(host)
            limiter.acquire()

            # Execute with exponential backoff & full jitter
            max_retries = 3
            base_backoff = 1.0
            max_backoff = 30.0
            attempt = 0

            response: httpx.Response | None = None
            last_exception: Exception | None = None

            while attempt <= max_retries:
                attempt += 1
                start_time = time.monotonic()

                # Clean client per request to avoid cookie persistence across hosts
                client = self._external_client or httpx.Client(
                    timeout=timeouts,
                    follow_redirects=False,
                    headers={"User-Agent": self.settings.http_user_agent},
                )

                try:
                    # Stream response to strictly enforce byte limit
                    with client.stream("GET", current_url, params=params) as resp:
                        duration_ms = round((time.monotonic() - start_time) * 1000, 2)

                        # Check Content-Length if present
                        cl_header = resp.headers.get("Content-Length")
                        if cl_header:
                            with contextlib.suppress(ValueError):
                                if int(cl_header) > effective_max_bytes:
                                    raise ResponseTooLarge(
                                        f"Response Content-Length {cl_header} exceeds limit {effective_max_bytes}"
                                    )

                        # Check status code for retry conditions
                        status = resp.status_code

                        # Check Redirects
                        if resp.is_redirect:
                            redirect_hops += 1
                            if redirect_hops > max_redirect_hops:
                                raise TooManyRedirects(
                                    f"Maximum redirect hops ({max_redirect_hops}) exceeded"
                                )
                            loc = resp.headers.get("Location")
                            if not loc:
                                raise TooManyRedirects("Redirect response missing Location header")
                            current_url = loc
                            break  # Break inner retry loop to re-validate target URL in outer loop

                        # Handle Retry Conditions: 429 and 5xx
                        if status == 429 or status >= 500:
                            if attempt <= max_retries:
                                retry_after = self._parse_retry_after(
                                    resp.headers.get("Retry-After")
                                )
                                if retry_after is not None:
                                    wait_duration = min(60.0, retry_after)
                                else:
                                    # Full jitter exponential backoff: sleep in [0, min(max_backoff, base * 2^attempt)]
                                    upper = min(max_backoff, base_backoff * (2 ** (attempt - 1)))
                                    wait_duration = random.uniform(0.0, upper)  # nosec B311

                                time.sleep(wait_duration)
                                continue

                            raise UpstreamError(
                                f"Upstream host returned status {status}", status_code=status
                            )

                        # Handle client errors (4xx other than 429: do NOT retry)
                        if 400 <= status < 500:
                            raise UpstreamError(
                                f"Upstream host returned client error status {status}",
                                status_code=status,
                            )

                        # Check Content-Type header
                        content_type_header = resp.headers.get("Content-Type", "")
                        content_mime = content_type_header.split(";")[0].strip().lower()

                        if expected_content_types and content_mime not in expected_content_types:
                            raise UnexpectedContentType(
                                f"Received content type '{content_mime}' does not match expected {expected_content_types}"
                            )

                        # Stream chunks to prevent memory bombing
                        total_bytes = 0
                        chunks: list[bytes] = []
                        for chunk in resp.iter_bytes(chunk_size=65536):
                            total_bytes += len(chunk)
                            if total_bytes > effective_max_bytes:
                                raise ResponseTooLarge(
                                    f"Response streamed bytes exceeded limit of {effective_max_bytes} bytes"
                                )
                            chunks.append(chunk)

                        raw_body = b"".join(chunks).decode("utf-8", errors="replace")

                        # Structured log without query params
                        logger.info(
                            "http_request_completed",
                            host=host,
                            path=path,
                            status=status,
                            bytes=total_bytes,
                            duration_ms=duration_ms,
                            attempt=attempt,
                            cache_hit=False,
                        )

                        # Store in disk cache
                        return store_cached_response(
                            cache=cache,
                            key=cache_key,
                            body=raw_body,
                            source_host=host,
                            namespace=namespace,
                            expire_seconds=effective_ttl,
                        )

                except (httpx.ConnectError, httpx.TimeoutException) as exc:
                    last_exception = exc
                    if attempt <= max_retries:
                        upper = min(max_backoff, base_backoff * (2 ** (attempt - 1)))
                        time.sleep(random.uniform(0.0, upper))  # nosec B311
                        continue
                    raise UpstreamError(
                        f"Connection failed after {attempt} attempts: {exc}", 503
                    ) from exc
                finally:
                    if not self._external_client:
                        client.close()

            if last_exception and not response:
                raise UpstreamError(
                    f"Request failed: {last_exception}",
                    status_code=503,
                ) from last_exception
