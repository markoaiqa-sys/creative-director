from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx


@dataclass
class CacheEntry:
    value: Any
    expires_at: datetime


class IngestionCache:
    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._entries.get(key)
            if not entry:
                return None
            if entry.expires_at <= datetime.now(tz=UTC):
                self._entries.pop(key, None)
                return None
            return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        ttl_seconds = max(0, ttl_seconds)
        async with self._lock:
            self._entries[key] = CacheEntry(
                value=value,
                expires_at=datetime.now(tz=UTC) + timedelta(seconds=ttl_seconds),
            )


class RateLimitedFetchGate:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_fetch_at: dict[str, datetime] = {}

    async def wait(self, url: str, rate_limit_per_minute: int) -> None:
        host = urlparse(url).netloc.lower() or url.lower()
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            if rate_limit_per_minute <= 0:
                return
            min_interval = 60.0 / float(rate_limit_per_minute)
            now = datetime.now(tz=UTC)
            last_fetch = self._last_fetch_at.get(host)
            if last_fetch is not None:
                elapsed = (now - last_fetch).total_seconds()
                if elapsed < min_interval:
                    await asyncio.sleep(min_interval - elapsed)
            self._last_fetch_at[host] = datetime.now(tz=UTC)


class BaseIngestor:
    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            limits=limits,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            },
        )
        self._cache = IngestionCache()
        self._gate = RateLimitedFetchGate()

    async def fetch_text(
        self,
        url: str,
        *,
        cache_key: str | None = None,
        force_refresh: bool = False,
        cache_ttl_seconds: int = 1800,
        rate_limit_per_minute: int = 30,
    ) -> str:
        key = cache_key or url
        if not force_refresh:
            cached = await self._cache.get(key)
            if isinstance(cached, str):
                return cached

        await self._gate.wait(url, rate_limit_per_minute)
        response = await self._client.get(url)
        response.raise_for_status()
        text = response.text
        await self._cache.set(key, text, cache_ttl_seconds)
        return text

    async def aclose(self) -> None:
        await self._client.aclose()
