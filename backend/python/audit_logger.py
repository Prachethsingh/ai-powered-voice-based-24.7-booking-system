"""
audit_logger.py — Security audit logging for ai powered voice based 24.7 booking system

All sensitive operations are logged with:
- Timestamp
- Operation type
- Phone hash (SHA-256, never plaintext)
- Status (success/failure)
- Call ID
- Latency

Logs are append-only and stored in logs/audit.log
"""
import json
import os
import time
from enum import Enum
from pathlib import Path
from typing import Optional

from loguru import logger

import config


class AuditEvent(str, Enum):
    BOOKING_CREATED   = "BOOKING_CREATED"
    BOOKING_DUPLICATE = "BOOKING_DUPLICATE"
    BOOKING_REJECTED  = "BOOKING_REJECTED"
    DB_REJECT         = "DB_REJECT"
    PHONE_INVALID     = "PHONE_INVALID"
    RATE_LIMITED      = "RATE_LIMITED"
    CALL_STARTED      = "CALL_STARTED"
    CALL_ENDED        = "CALL_ENDED"
    STT_COMPLETED     = "STT_COMPLETED"
    INTENT_EXTRACTED  = "INTENT_EXTRACTED"
    DB_ERROR          = "DB_ERROR"
    AUTH_FAILED       = "AUTH_FAILED"
    RTP_TAMPER        = "RTP_TAMPER"


class AuditLogger:
    """Append-only security audit logger."""

    def __init__(self, log_path: str = config.AUDIT_LOG_PATH):
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

        # Configure loguru for audit log (separate from app log)
        logger.add(
            str(self._log_path),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
            rotation="10 MB",
            retention="90 days",
            compression="gz",
            filter=lambda record: record["extra"].get("audit", False),
        )

    def log(
        self,
        event: AuditEvent,
        call_id: Optional[str] = None,
        phone_hash: Optional[str] = None,
        status: str = "OK",
        latency_ms: Optional[float] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Write a structured audit log entry."""
        entry = {
            "event": event.value,
            "ts": time.time(),
            "call_id": call_id or "N/A",
            "phone_hash": phone_hash or "N/A",   # SHA-256, not plaintext
            "status": status,
        }
        if latency_ms is not None:
            entry["latency_ms"] = round(latency_ms, 2)
        if details:
            entry["details"] = details

        logger.bind(audit=True).info(json.dumps(entry))

    def booking_created(self, call_id: str, phone_hash: str, items: list, latency_ms: float):
        self.log(AuditEvent.BOOKING_CREATED, call_id, phone_hash,
                 "OK", latency_ms, {"items_count": len(items)})

    def booking_duplicate(self, call_id: str, phone_hash: str):
        self.log(AuditEvent.BOOKING_DUPLICATE, call_id, phone_hash, "REJECTED")

    def rate_limited(self, call_id: str, phone_hash: str):
        self.log(AuditEvent.RATE_LIMITED, call_id, phone_hash, "REJECTED")

    def rtp_tamper_detected(self, call_id: str, reason: str):
        self.log(AuditEvent.RTP_TAMPER, call_id, status="SECURITY_ALERT",
                 details={"reason": reason})

    def auth_failed(self, ip: str, reason: str):
        self.log(AuditEvent.AUTH_FAILED, status="SECURITY_ALERT",
                 details={"ip": ip, "reason": reason})

    def log_db_reject(self, call_id: str, reason: str):
        """Log a booking rejection (invalid phone, duplicate, rate-limit)."""
        event_map = {
            "invalid_phone": AuditEvent.PHONE_INVALID,
            "duplicate":     AuditEvent.BOOKING_DUPLICATE,
            "rate_limited":  AuditEvent.RATE_LIMITED,
        }
        event = event_map.get(reason, AuditEvent.BOOKING_REJECTED)
        self.log(event, call_id, status="REJECTED", details={"reason": reason})


# Singleton
audit = AuditLogger()
