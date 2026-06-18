"""
tests/test_pipeline.py — LangChain pipeline tests (no model needed)

Tests the fallback regex mode so you can run without downloading models.

Run: pytest tests/test_pipeline.py -v
"""
import os
import sys
import pytest

os.environ.setdefault("ENCRYPTION_KEY", "test-key-do-not-use-in-production-32x")
os.environ.setdefault("ARI_JWT_SECRET",   "test-ari-secret-do-not-use-in-prod-32")
os.environ.setdefault("WS_JWT_SECRET",    "test-ws-secret-do-not-use-in-prod-32!")
os.environ.setdefault("RTP_SECRET",       "test-rtp-secret-do-not-use-in-prod-32")
os.environ.setdefault("REDIS_PASSWORD",   "test-redis-password")
os.environ.setdefault("ASTERISK_ARI_PASSWORD", "test-ari-password")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend/python"))

from langchain_pipeline import FallbackParser, VoiceOrderParser


class TestFallbackParser:
    def setup_method(self):
        self.parser = FallbackParser()

    def test_basic_order(self):
        r = self.parser.parse("I want rice and milk, number 9876543210")
        assert r["phone"] == "9876543210"
        assert any("rice" in i for i in r["items"])
        assert any("milk" in i for i in r["items"])

    def test_phone_extraction(self):
        r = self.parser.parse("my number is 8765432109 and I want bread")
        assert r["phone"] == "8765432109"

    def test_multiple_items(self):
        r = self.parser.parse("I need rice oil and sugar, call 9876543210")
        assert r["phone"] == "9876543210"
        assert len(r["items"]) >= 2

    def test_no_phone(self):
        r = self.parser.parse("I want eggs and bread")
        assert r["phone"] is None
        assert r["confidence"] == "low"

    def test_no_items(self):
        r = self.parser.parse("My number is 9876543210")
        assert r["phone"] == "9876543210"

    def test_spoken_phone(self):
        r = self.parser.parse(
            "I want milk, nine eight seven six five four three two one zero"
        )
        assert r["phone"] == "9876543210"


class TestVoiceOrderParser:
    def setup_method(self):
        self.parser = VoiceOrderParser()

    def test_parse_full_intent(self):
        r = self.parser.parse("PHONE:9876543210 ITEMS:rice 2kg,milk 1L")
        assert r["phone"] == "9876543210"
        assert "rice 2kg" in r["items"]
        assert "milk 1L" in r["items"]
        assert r["confidence"] == "high"

    def test_parse_unknown_phone(self):
        r = self.parser.parse("PHONE:UNKNOWN ITEMS:bread,eggs")
        assert r["phone"] is None
        assert "bread" in r["items"]
        assert r["confidence"] == "low"

    def test_parse_case_insensitive(self):
        r = self.parser.parse("phone:9876543210 items:rice,dal")
        assert r["phone"] == "9876543210"

    def test_parse_messy_llm_output(self):
        """LLM sometimes adds extra text before the format."""
        r = self.parser.parse(
            "Based on the voice message:\nPHONE:9876543210 ITEMS:rice,milk\nThank you."
        )
        assert r["phone"] == "9876543210"
        assert "rice" in r["items"]
