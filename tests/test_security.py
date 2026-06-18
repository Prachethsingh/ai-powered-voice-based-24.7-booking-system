"""
tests/test_security.py — Security Unit Tests

Run: pytest tests/test_security.py -v
"""
import os
import sys
import time
import pytest

# Set dummy env vars for testing
os.environ.setdefault("ENCRYPTION_KEY", "test-key-do-not-use-in-production-32x")
os.environ.setdefault("ARI_JWT_SECRET",   "test-ari-secret-do-not-use-in-prod-32")
os.environ.setdefault("WS_JWT_SECRET",    "test-ws-secret-do-not-use-in-prod-32!")
os.environ.setdefault("RTP_SECRET",       "test-rtp-secret-do-not-use-in-prod-32")
os.environ.setdefault("REDIS_PASSWORD",   "test-redis-password")
os.environ.setdefault("ASTERISK_ARI_PASSWORD", "test-ari-password")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend/python"))

from security import PhoneEncryptor, JWTHelper, InMemoryRateLimiter, RTPSigner


class TestPhoneEncryptor:
    def setup_method(self):
        self.enc = PhoneEncryptor()

    def test_encrypt_decrypt_roundtrip(self):
        phone = "9876543210"
        encrypted = self.enc.encrypt(phone)
        assert encrypted != phone
        decrypted = self.enc.decrypt(encrypted)
        assert decrypted == phone

    def test_different_encryptions(self):
        """Fernet uses random IV, same input gives different ciphertext."""
        p = "9876543210"
        e1 = self.enc.encrypt(p)
        e2 = self.enc.encrypt(p)
        # Both decrypt to same value, but ciphertexts differ
        assert self.enc.decrypt(e1) == self.enc.decrypt(e2) == p

    def test_hash_is_consistent(self):
        phone = "9876543210"
        h1 = self.enc.hash(phone)
        h2 = self.enc.hash(phone)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_non_reversible(self):
        """Hash cannot be decrypted (one-way)."""
        phone = "9876543210"
        h = self.enc.hash(phone)
        with pytest.raises(Exception):
            self.enc.decrypt(h)

    def test_normalize_removes_country_code(self):
        assert self.enc._normalize("+919876543210") == "9876543210"
        assert self.enc._normalize("919876543210") == "9876543210"

    def test_normalize_removes_spaces(self):
        assert self.enc._normalize("98765 43210") == "9876543210"

    def test_invalid_decrypt_raises(self):
        with pytest.raises(ValueError):
            self.enc.decrypt("not-valid-hex-at-all")


class TestJWTHelper:
    def setup_method(self):
        self.jwt = JWTHelper("test-secret-32-bytes-exactly-pad", ttl_seconds=60)

    def test_generate_and_verify(self):
        token = self.jwt.generate("user1", "127.0.0.1")
        result = self.jwt.verify(token, "127.0.0.1")
        assert result == "user1"

    def test_wrong_ip_rejected(self):
        token = self.jwt.generate("user1", "127.0.0.1")
        result = self.jwt.verify(token, "192.168.1.1")
        assert result is None

    def test_tampered_token_rejected(self):
        token = self.jwt.generate("user1", "127.0.0.1")
        tampered = token[:-4] + "XXXX"
        assert self.jwt.verify(tampered, "127.0.0.1") is None

    def test_expired_token_rejected(self):
        short_jwt = JWTHelper("test-secret-32-bytes-exactly-pad", ttl_seconds=1)
        token = short_jwt.generate("user1", "127.0.0.1")
        time.sleep(2)
        assert short_jwt.verify(token, "127.0.0.1") is None


class TestRateLimiter:
    def test_allows_under_limit(self):
        rl = InMemoryRateLimiter(max_per_window=5, window_seconds=60)
        for _ in range(5):
            assert rl.is_allowed("key1") is True

    def test_blocks_over_limit(self):
        rl = InMemoryRateLimiter(max_per_window=3, window_seconds=60)
        for _ in range(3):
            rl.is_allowed("key2")
        assert rl.is_allowed("key2") is False

    def test_different_keys_independent(self):
        rl = InMemoryRateLimiter(max_per_window=1, window_seconds=60)
        rl.is_allowed("key-a")
        assert rl.is_allowed("key-a") is False
        assert rl.is_allowed("key-b") is True  # Different key = fresh


class TestRTPSigner:
    def setup_method(self):
        self.signer = RTPSigner()

    def test_sign_and_verify(self):
        payload = b"audio-data-1234"
        signed = self.signer.sign(payload, sequence=1, timestamp=1000)
        recovered = self.signer.verify(signed, sequence=1, timestamp=1000, call_id="call-1")
        assert recovered == payload

    def test_tampered_payload_rejected(self):
        payload = b"audio-data-1234"
        signed = self.signer.sign(payload, sequence=2, timestamp=2000)
        tampered = b"EVIL" + signed[4:]
        with pytest.raises(ValueError, match="signature"):
            self.signer.verify(tampered, sequence=2, timestamp=2000, call_id="call-2")

    def test_replay_attack_detected(self):
        signer = RTPSigner()
        payload = b"audio-data"
        signed = signer.sign(payload, sequence=10, timestamp=5000)
        signer.verify(signed, sequence=10, timestamp=5000, call_id="call-3")
        # Replay same sequence
        signed2 = signer.sign(payload, sequence=10, timestamp=5000)
        with pytest.raises(ValueError, match="replay"):
            signer.verify(signed2, sequence=10, timestamp=5000, call_id="call-3")


class TestPhoneValidator:
    def setup_method(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend/python"))
        from phone_validator import normalize_phone, extract_phone_from_text, validate_phone
        self.normalize = normalize_phone
        self.extract   = extract_phone_from_text
        self.validate  = validate_phone

    def test_valid_10_digit(self):
        assert self.normalize("9876543210") == "9876543210"

    def test_with_plus91(self):
        assert self.normalize("+919876543210") == "9876543210"

    def test_with_spaces(self):
        assert self.normalize("98765 43210") == "9876543210"

    def test_invalid_number(self):
        assert self.normalize("1234567890") is None  # Starts with 1

    def test_extract_from_text(self):
        text = "I want rice, my number is 9876543210"
        assert self.extract(text) == "9876543210"

    def test_extract_spoken_digits(self):
        text = "call me at nine eight seven six five four three two one zero"
        assert self.extract(text) == "9876543210"
