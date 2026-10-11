"""Bounded per-process TTL+LRU cache for immutable GeoInsight JSON responses.

Only GET measurement / GeoJSON results use this cache. It does not authorize
access, coordinate other processes, or cache mutable/database-private data.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
import time
from typing import Callable

from starlette.responses import Response


@dataclass(frozen=True)
class CachedJSON:
    body: bytes
    etag: str
    expires_at: float


class BoundedResponseCache:
    """Fixed-memory, fixed-count, thread-safe TTL/LRU cache scoped to one app."""

    def __init__(self, *, max_entries: int, max_bytes: int, max_item_bytes: int,
                 ttl_seconds: int, clock: Callable[[], float] = time.monotonic):
        if not 0 <= max_entries <= 256:
            raise ValueError('cache max_entries out of range')
        if not 0 <= max_bytes <= 128 * 1024 * 1024:
            raise ValueError('cache max_bytes out of range')
        if not 1024 <= max_item_bytes <= 16 * 1024 * 1024:
            raise ValueError('cache max_item_bytes out of range')
        if not 1 <= ttl_seconds <= 3600:
            raise ValueError('cache ttl_seconds out of range')
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.max_item_bytes = max_item_bytes
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._lock = Lock()
        self._items: OrderedDict[tuple[str, str], CachedJSON] = OrderedDict()
        self._bytes = 0
        self.hits = 0
        self.misses = 0

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._items)

    @property
    def cached_bytes(self) -> int:
        with self._lock:
            return self._bytes

    def _evict(self, key: tuple[str, str]) -> None:
        item = self._items.pop(key)
        self._bytes -= len(item.body)

    def get(self, key: tuple[str, str]) -> CachedJSON | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                self.misses += 1
                return None
            if self.clock() >= item.expires_at:
                self._evict(key)
                self.misses += 1
                return None
            self._items.move_to_end(key)
            self.hits += 1
            return item

    def put(self, key: tuple[str, str], item: CachedJSON) -> bool:
        size = len(item.body)
        if not self.max_entries or not self.max_bytes or size > self.max_item_bytes or size > self.max_bytes:
            return False
        with self._lock:
            if key in self._items:
                self._evict(key)
            now = self.clock()
            for expired_key, expired_item in list(self._items.items()):
                if now >= expired_item.expires_at:
                    self._evict(expired_key)
            while self._items and (len(self._items) >= self.max_entries or self._bytes + size > self.max_bytes):
                self._evict(next(iter(self._items)))
            self._items[key] = item
            self._bytes += size
            return True

    def build(self, body: bytes) -> CachedJSON:
        return CachedJSON(
            body=body,
            etag='"sha256-' + sha256(body).hexdigest() + '"',
            expires_at=self.clock() + self.ttl_seconds,
        )


def if_none_match_matches(header: str | None, etag: str) -> bool:
    """RFC 9110 weak comparison for GET If-None-Match, including lists and *."""
    if not header or len(header) > 8192:
        return False
    for candidate in header.split(','):
        candidate = candidate.strip()
        if candidate == '*':
            return True
        if candidate[:2].lower() == 'w/':
            candidate = candidate[2:].strip()
        if candidate == etag:
            return True
    return False


def conditional_json_response(item: CachedJSON, if_none_match: str | None, *, cache_status: str) -> Response:
    headers = {
        'ETag': item.etag,
        # Client caches may store, but they must validate on every use.
        # Shared reverse-proxy caches must not store per-request GIS outputs.
        'Cache-Control': 'private, no-cache',
        'X-GeoInsight-Cache': cache_status,
    }
    if if_none_match_matches(if_none_match, item.etag):
        return Response(status_code=304, headers=headers)
    return Response(content=item.body, media_type='application/json', headers=headers)
