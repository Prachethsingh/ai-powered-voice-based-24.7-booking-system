"""
secure_db.py — Encrypted SQLite + Redis for ai powered voice based 24.7 booking system

SECURITY:
- Phone numbers encrypted with Fernet AES-128 before storage
- All queries parameterized (zero SQL injection risk)
- Rate limiting via Redis (5 bookings/hour per phone)
- Deduplication via Redis (5-minute window)
- WAL journal mode for concurrent reads
"""
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import redis
from loguru import logger

import config
from security import phone_encryptor
from audit_logger import audit


class SecureBookingDB:
    """
    Thread-safe, encrypted booking database.
    SQLite for persistence, Redis for fast dedup/rate-limiting.
    """

    def __init__(
        self,
        sqlite_path: str = config.SQLITE_DB_PATH,
        redis_host: str = config.REDIS_HOST,
        redis_port: int = config.REDIS_PORT,
        redis_password: str = config.REDIS_PASSWORD,
    ):
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        # Redis connection
        self._redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True,
        )
        self._test_redis()
        self._init_schema()
        logger.info(f"✅ SecureBookingDB ready: {self.sqlite_path}")

    # ── Connection ────────────────────────────────────────────────────────

    @contextmanager
    def _db(self):
        """Context manager: parameterized, WAL-mode SQLite connection."""
        conn = sqlite3.connect(str(self.sqlite_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")       # concurrent reads
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA synchronous = NORMAL")     # balanced durability
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _test_redis(self):
        try:
            self._redis.ping()
            logger.info("✅ Redis connected")
        except redis.exceptions.ConnectionError:
            logger.warning(
                "⚠️  Redis not reachable. Deduplication and rate limiting disabled.\n"
                "   Start Redis: redis-server --requirepass $REDIS_PASSWORD"
            )
            self._redis = None

    # ── Schema ────────────────────────────────────────────────────────────

    def _init_schema(self):
        with self._db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_enc     TEXT NOT NULL,            -- AES-128 encrypted
                    items         TEXT NOT NULL,            -- JSON array
                    call_id       TEXT,
                    status        TEXT DEFAULT 'pending',
                    created_at    REAL DEFAULT (strftime('%s','now'))
                );
                CREATE INDEX IF NOT EXISTS idx_bookings_phone
                    ON bookings(phone_enc);
                CREATE INDEX IF NOT EXISTS idx_bookings_created
                    ON bookings(created_at);

                CREATE TABLE IF NOT EXISTS users (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_enc       TEXT NOT NULL UNIQUE,
                    phone_hash      TEXT NOT NULL,           -- SHA-256 for audit
                    total_orders    INTEGER DEFAULT 0,
                    first_seen      REAL DEFAULT (strftime('%s','now')),
                    last_seen       REAL DEFAULT (strftime('%s','now'))
                );
                CREATE INDEX IF NOT EXISTS idx_users_enc
                    ON users(phone_enc);

                CREATE TABLE IF NOT EXISTS audit_events (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    event      TEXT NOT NULL,
                    call_id    TEXT,
                    phone_hash TEXT,           -- SHA-256 only
                    status     TEXT,
                    details    TEXT,           -- JSON
                    ts         REAL DEFAULT (strftime('%s','now'))
                );
            """)

    # ── Public API ────────────────────────────────────────────────────────

    def store_booking(
        self,
        phone: str,
        items: list,
        call_id: str = "unknown",
    ) -> dict:
        """
        Store a booking securely.

        Returns:
            {"success": True, "booking_id": 42, "message": "..."}
            {"success": False, "reason": "duplicate|rate_limited|invalid_phone"}
        """
        t0 = time.perf_counter()

        # Validate phone (should be 10-digit by now)
        if not phone or len(phone) != 10 or not phone.isdigit():
            audit.log_db_reject(call_id, "invalid_phone")
            return {"success": False, "reason": "invalid_phone"}

        phone_hash = phone_encryptor.hash(phone)
        phone_enc  = phone_encryptor.encrypt(phone)

        # Redis checks (skip if Redis unavailable)
        if self._redis:
            # Deduplication: max 1 booking per 5 minutes
            dup_key = f"vb:dup:{phone_hash}"
            if self._redis.exists(dup_key):
                audit.booking_duplicate(call_id, phone_hash)
                return {"success": False, "reason": "duplicate"}

            # Rate limiting: max 5 bookings per hour
            rate_key = f"vb:rate:{phone_hash}"
            current = self._redis.incr(rate_key)
            if current == 1:
                self._redis.expire(rate_key, 3600)  # 1-hour window
            if current > config.RATE_LIMIT_PER_HOUR:
                audit.rate_limited(call_id, phone_hash)
                return {"success": False, "reason": "rate_limited"}

        # Insert booking
        items_json = json.dumps(items)
        with self._db() as conn:
            cursor = conn.execute(
                """INSERT INTO bookings (phone_enc, items, call_id)
                   VALUES (?, ?, ?)""",
                (phone_enc, items_json, call_id),
            )
            booking_id = cursor.lastrowid

            # Upsert user profile
            existing = conn.execute(
                "SELECT id, total_orders FROM users WHERE phone_enc = ?",
                (phone_enc,),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE users
                       SET total_orders = total_orders + 1,
                           last_seen = strftime('%s','now')
                       WHERE id = ?""",
                    (existing["id"],),
                )
                is_repeat = True
            else:
                conn.execute(
                    """INSERT INTO users (phone_enc, phone_hash)
                       VALUES (?, ?)""",
                    (phone_enc, phone_hash),
                )
                is_repeat = False

        # Cache deduplication key
        if self._redis:
            self._redis.setex(dup_key, config.DEDUP_TTL, "1")

        latency_ms = (time.perf_counter() - t0) * 1000
        audit.booking_created(call_id, phone_hash, items, latency_ms)

        logger.info(
            f"[{call_id}] ✅ Booking #{booking_id} | "
            f"{'Repeat' if is_repeat else 'New'} customer | {items}"
        )

        return {
            "success": True,
            "booking_id": booking_id,
            "is_repeat_customer": is_repeat,
            "message": f"Order placed: {', '.join(items)}",
            "latency_ms": round(latency_ms, 2),
        }

    def get_recent_bookings(self, limit: int = 20) -> list:
        """Fetch recent bookings for dashboard (decrypts phones for display)."""
        with self._db() as conn:
            rows = conn.execute(
                """SELECT id, phone_enc, items, call_id, status, created_at
                   FROM bookings
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

        result = []
        for row in rows:
            try:
                phone = phone_encryptor.decrypt(row["phone_enc"])
                phone_masked = phone[:4] + "XXXXXX"  # Mask for dashboard
            except Exception:
                phone_masked = "XXXXXXXXXXXX"

            result.append({
                "id":         row["id"],
                "phone":      phone_masked,   # Partially masked
                "items":      json.loads(row["items"]),
                "call_id":    row["call_id"],
                "status":     row["status"],
                "created_at": row["created_at"],
            })
        return result

    def get_stats(self) -> dict:
        """Summary stats for the dashboard."""
        with self._db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
            today_cutoff = time.time() - 86400
            today = conn.execute(
                "SELECT COUNT(*) FROM bookings WHERE created_at > ?",
                (today_cutoff,),
            ).fetchone()[0]
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM bookings WHERE status = 'pending'"
            ).fetchone()[0]

        return {
            "total_bookings": total,
            "today_bookings": today,
            "total_users": users,
            "pending": pending,
        }

    def update_booking_status(self, booking_id: int, status: str) -> bool:
        """Update booking status (pending → confirmed → fulfilled)."""
        valid_statuses = {"pending", "confirmed", "fulfilled", "cancelled"}
        if status not in valid_statuses:
            return False
        with self._db() as conn:
            conn.execute(
                "UPDATE bookings SET status = ? WHERE id = ?",
                (status, booking_id),
            )
        return True


# Singleton
db = SecureBookingDB()
