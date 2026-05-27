from contextlib import contextmanager

from psycopg2.pool import SimpleConnectionPool

from app.core.config import Settings


class DatabasePool:
    def __init__(self, settings: Settings) -> None:
        self._dsn = settings.supabase_url
        self._pool: SimpleConnectionPool | None = None
        if self._dsn and self._dsn.startswith("postgresql://"):
            # Add connection options for stability
            # connect_timeout: 5 seconds to detect connection issues early
            # keepalives: 1 (enable TCP keepalives)
            # keepalives_idle: 30 seconds before sending keepalive
            # keepalives_interval: 10 seconds between keepalives
            # keepalives_count: 5 keepalive attempts before giving up
            dsn_with_options = f"{self._dsn}?connect_timeout=5&keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=5"
            self._pool = SimpleConnectionPool(
                minconn=settings.db_pool_min_size,
                maxconn=settings.db_pool_max_size,
                dsn=dsn_with_options,
            )

    @property
    def enabled(self) -> bool:
        return self._pool is not None

    @contextmanager
    def connection(self):
        if not self._pool:
            yield None
            return

        conn = self._pool.getconn()
        conn.autocommit = False
        broken = False
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                # Connection already closed by server, mark as broken
                broken = True
            raise
        finally:
            # If connection is broken, close it; otherwise return to pool
            if broken:
                conn.close()
            else:
                self._pool.putconn(conn)

    def close(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None
