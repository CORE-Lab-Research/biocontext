"""Base adapter and caching abstractions for biological data sources."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import json
import sqlite3
import time
from pathlib import Path


class SQLiteCache:
    """Persistent SQLite key-value cache with optional TTL."""

    def __init__(self, db_path: str = ".cache/biocontext.db", default_ttl_sec: int = 86400 * 7):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.default_ttl_sec = default_ttl_sec
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_store (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    PRIMARY KEY (namespace, cache_key)
                )
                """
            )
            conn.commit()

    def get(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data_json, expires_at FROM cache_store WHERE namespace = ? AND cache_key = ?",
                (namespace, key)
            )
            row = cursor.fetchone()
            if not row:
                return None
            data_json, expires_at = row
            if now > expires_at:
                cursor.execute(
                    "DELETE FROM cache_store WHERE namespace = ? AND cache_key = ?",
                    (namespace, key)
                )
                conn.commit()
                return None
            return json.loads(data_json)

    def set(self, namespace: str, key: str, value: Dict[str, Any], ttl_sec: Optional[int] = None) -> None:
        ttl = ttl_sec if ttl_sec is not None else self.default_ttl_sec
        now = time.time()
        expires_at = now + ttl
        data_json = json.dumps(value)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache_store (namespace, cache_key, data_json, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (namespace, key, data_json, now, expires_at)
            )
    def clear(self) -> int:
        """Purge all entries from cache store and return number of deleted rows."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cache_store")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM cache_store")
            conn.commit()
            return count

    def stats(self) -> Dict[str, Any]:
        """Return cache store item counts and namespace distribution."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cache_store")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT namespace, COUNT(*) FROM cache_store GROUP BY namespace")
            by_ns = dict(cursor.fetchall())
            return {"total_entries": total, "by_namespace": by_ns, "db_path": str(self.db_path)}


class AsyncRateLimiter:
    """Token-bucket async rate limiter preventing HTTP 429 penalties."""

    def __init__(self, requests_per_second: float):
        import asyncio
        self.rate = requests_per_second
        self.interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
        self.lock = asyncio.Lock()
        self.last_request_time = 0.0

    async def acquire(self) -> None:
        if self.rate <= 0:
            return
        import asyncio
        async with self.lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_request_time
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self.last_request_time = asyncio.get_event_loop().time()


class BaseBioAdapter(ABC):
    """Abstract Base Class for external biological resource adapters."""

    def __init__(self, name: str, cache: Optional[SQLiteCache] = None):
        self.name = name
        self.cache = cache or SQLiteCache()

    @abstractmethod
    async def resolve_gene(self, query: str, taxon_id: int = 9606) -> Optional[Dict[str, Any]]:
        """Resolve a gene query string against the authoritative database."""
        pass
