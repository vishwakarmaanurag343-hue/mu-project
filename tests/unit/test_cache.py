"""Unit tests for diskcache caching layer and @cached decorator."""

from pathlib import Path
from unittest.mock import patch

import pytest
import respx
from httpx import Response
from pydantic import BaseModel

from alphalens.config import Settings
from alphalens.data.cache import (
    cached,
    clear_namespace,
    compute_http_cache_key,
    get_disk_cache,
)
from alphalens.data.errors import UpstreamError
from alphalens.data.http import SafeHttpClient


class SampleModel(BaseModel):
    ticker: str
    price: float


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        cache_dir=tmp_path / "cache",
        allowed_domains=["api.bseindia.com"],
        http_offline=False,
    )


@respx.mock
@patch("socket.getaddrinfo")
def test_cache_hit_returns_same_body_and_timestamp(
    mock_getaddrinfo: pytest.MonkeyPatch, test_settings: Settings
) -> None:
    """Cache hit avoids second network call and returns original fetched_at."""
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
    client = SafeHttpClient(settings=test_settings)

    route = respx.get("https://api.bseindia.com/prices").mock(
        return_value=Response(200, content=b'{"TCS": 3500}')
    )

    # 1. First fetch (cache miss)
    first_res = client.get("https://api.bseindia.com/prices", namespace="prices")
    assert first_res.body == '{"TCS": 3500}'
    assert route.call_count == 1

    # 2. Second fetch (cache hit)
    second_res = client.get("https://api.bseindia.com/prices", namespace="prices")
    assert second_res.body == '{"TCS": 3500}'
    assert second_res.fetched_at == first_res.fetched_at
    assert route.call_count == 1  # No extra network request


@respx.mock
@patch("socket.getaddrinfo")
def test_cache_errors_never_stored(
    mock_getaddrinfo: pytest.MonkeyPatch, test_settings: Settings
) -> None:
    """Unsuccessful HTTP responses (500) are never written to disk cache."""
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
    client = SafeHttpClient(settings=test_settings)

    respx.get("https://api.bseindia.com/faulty").mock(
        return_value=Response(500, content=b"Server error")
    )

    with pytest.raises(UpstreamError):
        client.get("https://api.bseindia.com/faulty", namespace="news")

    cache = get_disk_cache(test_settings.cache_dir)
    key = compute_http_cache_key("GET", "https://api.bseindia.com/faulty", namespace_version="news")
    assert cache.get(key) is None


def test_cache_decorator_with_pydantic_and_json_safety(tmp_path: Path) -> None:
    """@cached decorator caches Pydantic models and JSON types; rejects non-serializable objects without pickle."""
    cache_dir = tmp_path / "cache"
    call_counts = {"model": 0, "primitive": 0, "unsupported": 0}

    @cached(namespace="fundamentals", ttl=3600, cache_dir=cache_dir)
    def fetch_company_data(ticker: str) -> SampleModel:
        call_counts["model"] += 1
        return SampleModel(ticker=ticker, price=2450.0)

    # 1. Test model serialization & caching
    res1 = fetch_company_data("INFY.NS")
    res2 = fetch_company_data("INFY.NS")
    assert call_counts["model"] == 1
    assert res1.ticker == "INFY.NS"
    assert res2.price == 2450.0

    # 2. Test JSON serializable primitives
    @cached(namespace="prices", ttl=3600, cache_dir=cache_dir)
    def calculate_mean(values: list[float]) -> float:
        call_counts["primitive"] += 1
        return sum(values) / len(values)

    val1 = calculate_mean([10.0, 20.0, 30.0])
    val2 = calculate_mean([10.0, 20.0, 30.0])
    assert call_counts["primitive"] == 1
    assert val1 == 20.0
    assert val2 == 20.0

    # 3. Test non-serializable object rejection without pickle
    class CustomNonSerializable:
        pass

    @cached(namespace="prices", ttl=3600, cache_dir=cache_dir)
    def return_complex_object() -> CustomNonSerializable:
        call_counts["unsupported"] += 1
        return CustomNonSerializable()

    with pytest.raises(TypeError) as exc:
        return_complex_object()
    assert "must be JSON-serializable" in str(exc.value)


def test_clear_namespace_utility(tmp_path: Path) -> None:
    """clear_namespace evicts only entries belonging to the specified namespace."""
    cache_dir = tmp_path / "cache"

    @cached(namespace="news", ttl=3600, cache_dir=cache_dir)
    def get_news(headline: str) -> str:
        return f"Processed: {headline}"

    @cached(namespace="prices", ttl=3600, cache_dir=cache_dir)
    def get_price(ticker: str) -> float:
        return 100.5

    get_news("RBI monetary policy announcement")
    get_price("RELIANCE.NS")

    cleared = clear_namespace("news", cache_dir=cache_dir)
    assert cleared == 1

    # News evicted (calls function again), price remains cached
    with patch.object(Path, "mkdir"):
        cache = get_disk_cache(cache_dir)
        with cache:
            assert len(cache) == 1


def test_cache_ttl_expiry_triggers_refetch(tmp_path: Path) -> None:
    """Expired cache entry is invalidated and triggers upstream refetch."""
    cache_dir = tmp_path / "cache"
    call_count = 0

    @cached(namespace="prices", ttl=1, cache_dir=cache_dir)
    def fetch_live_val() -> int:
        nonlocal call_count
        call_count += 1
        return call_count

    assert fetch_live_val() == 1
    assert fetch_live_val() == 1  # Cache hit
    assert call_count == 1

    # Manually expire diskcache key by setting expire to -1
    cache = get_disk_cache(cache_dir)
    with cache:
        for k in list(cache):
            raw = cache.get(k)
            cache.set(k, raw, expire=0)

    # After expiry, function is executed again
    assert fetch_live_val() == 2
    assert call_count == 2


@respx.mock
@patch("socket.getaddrinfo")
def test_error_responses_are_not_cached(
    mock_getaddrinfo: pytest.MonkeyPatch, test_settings: Settings, tmp_path: Path
) -> None:
    """Upstream HTTP error responses (5xx, 4xx) must never be cached."""
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
    cache_dir = tmp_path / "http_cache"
    test_settings.cache_dir = cache_dir

    client = SafeHttpClient(settings=test_settings)

    route = respx.get("https://api.bseindia.com/error-endpoint").mock(
        return_value=Response(500, content=b"Internal Server Error")
    )

    with pytest.raises(UpstreamError):
        client.get("https://api.bseindia.com/error-endpoint")

    # Verify nothing was added to disk cache
    cache = get_disk_cache(cache_dir)
    with cache:
        assert len(cache) == 0

    # Mock success on recovery and verify it then caches
    route.return_value = Response(200, content=b'{"recovered": true}')
    res = client.get("https://api.bseindia.com/error-endpoint")
    assert res.body == '{"recovered": true}'
    with cache:
        assert len(cache) == 1
