"""Disk-backed HTTP and function caching layer with JSON serialization."""

import contextlib
import hashlib
import inspect
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from functools import wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, get_type_hints
from urllib.parse import parse_qsl, urlparse

import diskcache  # type: ignore[import-untyped]
from pydantic import BaseModel

from alphalens.config import get_settings

P = ParamSpec("P")
R = TypeVar("R")

CACHE_SCHEMA_VERSION = "v1"


def get_disk_cache(cache_dir: Path | None = None) -> diskcache.Cache:
    """Return configured DiskCache instance under cache_dir / 'http'."""
    settings = get_settings()
    target_dir = (cache_dir or settings.cache_dir) / "http"
    target_dir.mkdir(parents=True, exist_ok=True)
    return diskcache.Cache(str(target_dir), size_limit=settings.http_cache_max_bytes)


def compute_http_cache_key(
    method: str,
    url: str,
    params: dict[str, Any] | None = None,
    namespace_version: str = CACHE_SCHEMA_VERSION,
) -> str:
    """Compute deterministic SHA-256 cache key for an HTTP request.

    Normalizes method, scheme, host, path, and sorts all query parameters.
    """
    parsed = urlparse(url)
    norm_method = method.upper()
    norm_scheme = parsed.scheme.lower()
    norm_host = (parsed.hostname or "").lower()
    norm_path = parsed.path or "/"

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if params:
        for k, v in params.items():
            query_pairs.append((str(k), str(v)))

    sorted_query = sorted(query_pairs, key=lambda x: (x[0], x[1]))
    serialized_query = "&".join(f"{k}={v}" for k, v in sorted_query)

    key_repr = f"{norm_method}:{norm_scheme}://{norm_host}{norm_path}:{serialized_query}:{namespace_version}"
    return hashlib.sha256(key_repr.encode("utf-8")).hexdigest()


class CacheEntry(BaseModel):
    """Metadata container for cached responses and function outputs."""

    body: str | dict[str, Any] | list[Any]
    fetched_at: str
    source_host: str
    namespace: str
    schema_version: str = CACHE_SCHEMA_VERSION


def store_cached_response(
    cache: diskcache.Cache,
    key: str,
    body: str | dict[str, Any] | list[Any],
    source_host: str,
    namespace: str,
    expire_seconds: int | None = None,
    fetched_at: str | None = None,
) -> CacheEntry:
    """Store size-checked, successful response payload using pure JSON serialization."""
    entry = CacheEntry(
        body=body,
        fetched_at=fetched_at or datetime.now(UTC).isoformat(),
        source_host=source_host,
        namespace=namespace,
        schema_version=CACHE_SCHEMA_VERSION,
    )
    # Ensure JSON serializable without pickle
    serialized = entry.model_dump_json()
    cache.set(key, serialized, expire=expire_seconds)
    return entry


def get_cached_response(
    cache: diskcache.Cache,
    key: str,
) -> CacheEntry | None:
    """Retrieve and deserialize cached response entry if present and unexpired."""
    raw = cache.get(key)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        return CacheEntry(**data)
    except Exception:
        # Invalid or corrupted cache entry
        cache.delete(key)
        return None


def clear_namespace(namespace: str, cache_dir: Path | None = None) -> int:
    """Evict all cache records belonging to a specified namespace."""
    cache = get_disk_cache(cache_dir)
    cleared = 0
    with cache:
        for key in list(cache):
            raw = cache.get(key)
            if raw and isinstance(raw, (str, bytes)):
                with contextlib.suppress(Exception):
                    data = json.loads(raw)
                    if data.get("namespace") == namespace:
                        cache.delete(key)
                        cleared += 1
            elif isinstance(key, str) and f":{namespace}:" in key:
                cache.delete(key)
                cleared += 1
    return cleared


def cache_stats(cache_dir: Path | None = None) -> dict[str, Any]:
    """Retrieve diagnostic statistics on disk cache utilization."""
    cache = get_disk_cache(cache_dir)
    with cache:
        return {
            "volume_bytes": cache.volume(),
            "count": len(cache),
            "directory": str(cache.directory),
        }


def _json_serializable_fallback(obj: Any) -> Any:
    """Fallback converter for Pydantic models or date objects."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, (datetime, date, Path)):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _args_serializable_fallback(obj: Any) -> Any:
    """Fallback converter for function arguments including self / class instances."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, (datetime, date, Path)):
        return str(obj)
    if hasattr(obj, "__class__") and not isinstance(
        obj, (type, int, float, str, bool, list, dict, set, tuple)
    ):
        return f"<{obj.__class__.__module__}.{obj.__class__.__qualname__}>"
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def cached(
    namespace: str,
    ttl: int | None = None,
    cache_dir: Path | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to cache non-HTTP functions (e.g. yfinance, calculations) with pure JSON.

    Enforces that return values are Pydantic models or JSON-serializable types.
    Strictly forbids pickle.
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            settings = get_settings()
            cache = get_disk_cache(cache_dir)

            # Determine TTL
            effective_ttl = ttl
            if effective_ttl is None:
                effective_ttl = getattr(settings, f"cache_ttl_{namespace}", 3600)

            # Compute key from module, qualname, and serialized arguments
            arg_str = json.dumps(
                {"args": args, "kwargs": kwargs},
                default=_args_serializable_fallback,
                sort_keys=True,
            )
            key_repr = f"fn:{fn.__module__}:{fn.__qualname__}:{namespace}:{arg_str}"
            key = hashlib.sha256(key_repr.encode("utf-8")).hexdigest()

            cached_item = cache.get(key)
            if cached_item is not None:
                try:
                    payload = json.loads(cached_item)
                    res_val = payload["result"]
                    # If function has a Pydantic return type annotation, reconstruct the model
                    with contextlib.suppress(Exception):
                        hints = get_type_hints(fn)
                        ret_type = hints.get("return")
                        if (
                            inspect.isclass(ret_type)
                            and issubclass(ret_type, BaseModel)
                            and isinstance(res_val, dict)
                        ):
                            return ret_type(**res_val)  # type: ignore[return-value]
                    return res_val  # type: ignore[no-any-return]
                except Exception:
                    cache.delete(key)

            # Invoke function
            result = fn(*args, **kwargs)

            # Verify return value is JSON-serializable without pickle
            try:
                serializable_result: Any
                if isinstance(result, BaseModel):
                    serializable_result = result.model_dump()
                else:
                    serializable_result = result

                cache_payload = json.dumps(
                    {
                        "result": serializable_result,
                        "fetched_at": datetime.now(UTC).isoformat(),
                        "namespace": namespace,
                    },
                    default=_json_serializable_fallback,
                )
            except Exception as e:
                raise TypeError(
                    f"Return value of {fn.__name__} must be JSON-serializable or a Pydantic model: {e}"
                ) from e

            cache.set(key, cache_payload, expire=effective_ttl)
            return result

        return wrapper

    return decorator
