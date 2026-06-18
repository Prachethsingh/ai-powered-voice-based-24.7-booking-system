-- ============================================================
-- ai powered voice based 24.7 booking system — SQLite Schema
-- Phone numbers stored ENCRYPTED (Fernet AES-128-CBC)
-- Phone hashes stored as SHA-256 (non-reversible, for audit)
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

-- ── Bookings ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_enc   TEXT    NOT NULL,               -- AES-128-CBC encrypted phone
    items       TEXT    NOT NULL,               -- JSON array: ["rice 2kg","milk 1L"]
    call_id     TEXT,                           -- Asterisk call ID
    status      TEXT    DEFAULT 'pending',      -- pending|confirmed|fulfilled|cancelled
    created_at  REAL    DEFAULT (strftime('%s','now')),
    updated_at  REAL    DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_bookings_phone   ON bookings(phone_enc);
CREATE INDEX IF NOT EXISTS idx_bookings_created ON bookings(created_at);
CREATE INDEX IF NOT EXISTS idx_bookings_status  ON bookings(status);

-- ── Users ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_enc       TEXT    NOT NULL UNIQUE,    -- AES-128-CBC encrypted phone
    phone_hash      TEXT    NOT NULL,           -- SHA-256 hash (for audit log)
    total_orders    INTEGER DEFAULT 0,
    first_seen      REAL    DEFAULT (strftime('%s','now')),
    last_seen       REAL    DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_users_phone_enc  ON users(phone_enc);
CREATE INDEX IF NOT EXISTS idx_users_phone_hash ON users(phone_hash);

-- ── Audit Log ─────────────────────────────────────────────────────────────
-- Stores events with phone HASH only (never raw number)
CREATE TABLE IF NOT EXISTS audit_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event       TEXT    NOT NULL,               -- BOOKING_CREATED, AUTH_FAILED, etc.
    call_id     TEXT,
    phone_hash  TEXT,                           -- SHA-256 hash (not reversible)
    status      TEXT,                           -- OK | REJECTED | SECURITY_ALERT
    details     TEXT,                           -- JSON extra info
    latency_ms  REAL,
    ts          REAL    DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_events(event);
CREATE INDEX IF NOT EXISTS idx_audit_ts    ON audit_events(ts);

-- ── Useful views ──────────────────────────────────────────────────────────

CREATE VIEW IF NOT EXISTS v_daily_stats AS
SELECT
    date(created_at, 'unixepoch', 'localtime') AS day,
    COUNT(*) AS total_orders,
    COUNT(DISTINCT phone_enc) AS unique_customers,
    SUM(CASE WHEN status = 'fulfilled' THEN 1 ELSE 0 END) AS fulfilled,
    SUM(CASE WHEN status = 'pending'   THEN 1 ELSE 0 END) AS pending
FROM bookings
GROUP BY day
ORDER BY day DESC;

CREATE VIEW IF NOT EXISTS v_security_alerts AS
SELECT * FROM audit_events
WHERE status IN ('SECURITY_ALERT', 'REJECTED')
ORDER BY ts DESC
LIMIT 100;
