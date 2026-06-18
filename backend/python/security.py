"""
security.py — Security utilities for ai powered voice based 24.7 booking system

- Fernet AES-128-CBC for phone number encryption
- HMAC-SHA256 for RTP packet signing
- SHA-256 for audit log phone hashing (one-way, non-reversible)
- JWT token generation/verification

SECURITY PRINCIPLE: Phone numbers are NEVER stored in plaintext.
They are encrypted at write, decrypted only at read (for admin).
Audit logs store only SHA-256 hash of phone (non-reversible).
"""
import hashlib
import hmac
import os
import struct
import time
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

import config


# ── Phone Number Encryption ───────────────────────────────────────────────

class PhoneEncryptor:
    """AES-128-CBC (Fernet) encryption for phone numbers."""

    def __init__(self):
        key = config.ENCRYPTION_KEY.encode()
        # Fernet requires a URL-safe base64-encoded 32-byte key
        # If key is a raw Fernet key string, use directly
        try:
            self._cipher = Fernet(key)
        except Exception:
            # Derive 32-byte key from env string and base64 encode it
            import base64
            derived = hashlib.sha256(key).digest()
            b64_key = base64.urlsafe_b64encode(derived)
            self._cipher = Fernet(b64_key)

    def encrypt(self, phone: str) -> str:
        """Encrypt phone number. Returns hex string for SQLite storage."""
        normalized = self._normalize(phone)
        encrypted_bytes = self._cipher.encrypt(normalized.encode())
        return encrypted_bytes.hex()

    def decrypt(self, encrypted_hex: str) -> str:
        """Decrypt phone number from hex string."""
        try:
            encrypted_bytes = bytes.fromhex(encrypted_hex)
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except (InvalidToken, ValueError) as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Cannot decrypt phone number") from e

    def hash(self, phone: str) -> str:
        """One-way SHA-256 hash for audit logs. Not reversible."""
        normalized = self._normalize(phone)
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def _normalize(phone: str) -> str:
        """Strip country code, spaces, dashes. Return 10-digit number."""
        cleaned = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        # Remove +91 or 91 prefix
        if cleaned.startswith("+91"):
            cleaned = cleaned[3:]
        elif cleaned.startswith("91") and len(cleaned) == 12:
            cleaned = cleaned[2:]
        return cleaned


# ── RTP Packet Signing ────────────────────────────────────────────────────

class RTPSigner:
    """HMAC-SHA256 signing for RTP audio packets.
    Prevents man-in-the-middle tampering of audio streams.
    """

    def __init__(self):
        self._secret = config.RTP_SECRET.encode()
        self._sequence_tracker: dict[str, int] = {}  # call_id -> last_seq

    def sign(self, payload: bytes, sequence: int, timestamp: int) -> bytes:
        """Append HMAC-SHA256 signature to RTP payload."""
        header = struct.pack(">II", sequence, timestamp)
        mac = hmac.new(self._secret, payload + header, hashlib.sha256).digest()
        return payload + mac  # 32-byte signature appended

    def verify(self, signed_payload: bytes, sequence: int, timestamp: int, call_id: str) -> bytes:
        """Verify and extract clean audio payload.
        Raises ValueError on invalid signature or replay attack.
        """
        if len(signed_payload) < 32:
            raise ValueError("RTP packet too short (no signature)")

        payload = signed_payload[:-32]
        received_mac = signed_payload[-32:]

        header = struct.pack(">II", sequence, timestamp)
        expected_mac = hmac.new(self._secret, payload + header, hashlib.sha256).digest()

        # Constant-time compare (prevent timing attacks)
        if not hmac.compare_digest(received_mac, expected_mac):
            raise ValueError(f"RTP signature mismatch for call {call_id}")

        # Replay attack prevention
        last_seq = self._sequence_tracker.get(call_id, -1)
        if sequence <= last_seq:
            raise ValueError(f"RTP replay detected: seq {sequence} <= {last_seq}")
        self._sequence_tracker[call_id] = sequence

        return payload


# ── JWT Token (Simple, No External Library) ───────────────────────────────

class JWTHelper:
    """Lightweight JWT-style token for API auth.
    Format: <timestamp>.<hmac-sha256>
    """

    def __init__(self, secret: str, ttl_seconds: int = 3600):
        self._secret = secret.encode()
        self._ttl = ttl_seconds

    def generate(self, user_id: str, ip: str) -> str:
        """Generate token for user_id + IP combination."""
        timestamp = int(time.time())
        payload = f"{user_id}:{ip}:{timestamp}"
        mac = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{mac}"

    def verify(self, token: str, ip: str) -> Optional[str]:
        """Returns user_id if valid, None if invalid/expired."""
        try:
            payload_part, received_mac = token.rsplit(".", 1)
            expected_mac = hmac.new(
                self._secret, payload_part.encode(), hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(received_mac, expected_mac):
                return None  # Signature mismatch

            user_id, token_ip, timestamp_str = payload_part.split(":")

            if token_ip != ip:
                return None  # IP mismatch

            if time.time() - int(timestamp_str) > self._ttl:
                return None  # Expired

            return user_id
        except Exception:
            return None


# ── Rate Limiter ──────────────────────────────────────────────────────────

class InMemoryRateLimiter:
    """Simple in-memory rate limiter (Redis handles production rate limiting)."""

    def __init__(self, max_per_window: int = 100, window_seconds: int = 60):
        self._max = max_per_window
        self._window = window_seconds
        self._store: dict[str, list[float]] = {}

    def is_allowed(self, key: str) -> bool:
        """Returns True if request is allowed, False if rate limited."""
        now = time.time()
        window_start = now - self._window

        if key not in self._store:
            self._store[key] = []

        # Remove old timestamps
        self._store[key] = [t for t in self._store[key] if t > window_start]

        if len(self._store[key]) >= self._max:
            return False

        self._store[key].append(now)
        return True


# ── Singletons ────────────────────────────────────────────────────────────

phone_encryptor = PhoneEncryptor()
rtp_signer      = RTPSigner()
ari_jwt         = JWTHelper(config.ARI_JWT_SECRET)
ws_jwt          = JWTHelper(config.WS_JWT_SECRET)
api_rate_limiter = InMemoryRateLimiter(max_per_window=200, window_seconds=60)
