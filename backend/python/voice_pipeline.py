"""
voice_pipeline.py — End-to-End Voice Call Processing

Wires together: STT → LangChain → DB → WebSocket broadcast
One call = one VoiceCallProcessor instance.
"""
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from loguru import logger

from stt_engine import WhisperSTT
from langchain_pipeline import get_pipeline
from secure_db import db
from security import rtp_signer
from audit_logger import audit, AuditEvent

# Global STT instance (shared across all calls, thread-safe)
_stt: Optional[WhisperSTT] = None


def get_stt() -> WhisperSTT:
    global _stt
    if _stt is None:
        _stt = WhisperSTT()
    return _stt


@dataclass
class CallResult:
    """Result of processing a single call."""
    call_id:     str
    phone:       Optional[str]
    items:       list
    stt_text:    str
    stt_ms:      float
    intent_ms:   float
    db_ms:       float
    total_ms:    float
    booking_id:  Optional[int]
    status:      str        # "success" | "no_phone" | "no_items" | "duplicate" | "error"
    message:     str
    mode:        str        # "llm" | "fallback_regex"


class VoiceCallProcessor:
    """
    Processes a single incoming call from audio bytes to stored booking.
    
    Usage:
        processor = VoiceCallProcessor(call_id="call-001")
        result = processor.process_audio(audio_bytes)
    """

    def __init__(
        self,
        call_id: str,
        on_result: Optional[Callable[[CallResult], None]] = None,
    ):
        self.call_id = call_id
        self.on_result = on_result  # WebSocket broadcast callback
        self._stt = get_stt()
        self._pipeline = get_pipeline()

    def process_audio(self, audio: bytes, sample_rate: int = 16000) -> CallResult:
        """
        Full pipeline: audio bytes → STT → intent → DB → result.
        
        This is called once per utterance (not continuous streaming).
        For streaming: call process_audio_chunk() repeatedly.
        """
        t_total = time.perf_counter()
        audit.log(AuditEvent.CALL_STARTED, self.call_id)

        # ── Step 1: STT ──────────────────────────────────────────────────
        t0 = time.perf_counter()
        stt_result = self._stt.transcribe(audio, sample_rate)
        stt_ms = (time.perf_counter() - t0) * 1000
        stt_text = stt_result["text"]

        if not stt_text:
            return self._make_result(
                stt_text="", phone=None, items=[],
                stt_ms=stt_ms, intent_ms=0, db_ms=0,
                total_ms=(time.perf_counter() - t_total) * 1000,
                status="error", message="STT returned empty transcript",
                booking_id=None, mode="none",
            )

        audit.log(AuditEvent.STT_COMPLETED, self.call_id,
                  latency_ms=stt_ms, details={"text_len": len(stt_text)})

        # ── Step 2: Intent Extraction (LangChain) ────────────────────────
        t0 = time.perf_counter()
        intent = self._pipeline.process(stt_text, self.call_id)
        intent_ms = (time.perf_counter() - t0) * 1000

        phone = intent.get("phone")
        items = intent.get("items", [])

        audit.log(AuditEvent.INTENT_EXTRACTED, self.call_id,
                  phone_hash=None,  # Don't log raw phone even in audit
                  latency_ms=intent_ms,
                  details={"has_phone": bool(phone), "item_count": len(items)})

        # ── Step 3: Validation ───────────────────────────────────────────
        if not phone:
            return self._make_result(
                stt_text=stt_text, phone=None, items=items,
                stt_ms=stt_ms, intent_ms=intent_ms, db_ms=0,
                total_ms=(time.perf_counter() - t_total) * 1000,
                status="no_phone",
                message="Could not extract phone number. Please say your 10-digit number.",
                booking_id=None, mode=intent.get("mode", "unknown"),
            )

        if not items:
            return self._make_result(
                stt_text=stt_text, phone=phone, items=[],
                stt_ms=stt_ms, intent_ms=intent_ms, db_ms=0,
                total_ms=(time.perf_counter() - t_total) * 1000,
                status="no_items",
                message="Could not extract items. Please tell us what you want to order.",
                booking_id=None, mode=intent.get("mode", "unknown"),
            )

        # ── Step 4: Secure DB Storage ────────────────────────────────────
        t0 = time.perf_counter()
        db_result = db.store_booking(phone=phone, items=items, call_id=self.call_id)
        db_ms = (time.perf_counter() - t0) * 1000

        total_ms = (time.perf_counter() - t_total) * 1000

        if not db_result["success"]:
            reason = db_result.get("reason", "unknown")
            status_map = {
                "duplicate":     "duplicate",
                "rate_limited":  "rate_limited",
                "invalid_phone": "no_phone",
            }
            return self._make_result(
                stt_text=stt_text, phone=phone, items=items,
                stt_ms=stt_ms, intent_ms=intent_ms, db_ms=db_ms,
                total_ms=total_ms,
                status=status_map.get(reason, "error"),
                message=f"Could not place order: {reason}",
                booking_id=None, mode=intent.get("mode", "unknown"),
            )

        # ── Step 5: Build Result ─────────────────────────────────────────
        result = self._make_result(
            stt_text=stt_text, phone=phone, items=items,
            stt_ms=stt_ms, intent_ms=intent_ms, db_ms=db_ms,
            total_ms=total_ms,
            status="success",
            message=db_result.get("message", "Order placed!"),
            booking_id=db_result.get("booking_id"),
            mode=intent.get("mode", "unknown"),
        )

        logger.info(
            f"[{self.call_id}] ✅ DONE | "
            f"STT:{stt_ms:.0f}ms Intent:{intent_ms:.0f}ms "
            f"DB:{db_ms:.0f}ms Total:{total_ms:.0f}ms"
        )

        # Broadcast to WebSocket dashboard
        if self.on_result:
            self.on_result(result)

        return result

    def _make_result(self, **kwargs) -> CallResult:
        return CallResult(call_id=self.call_id, **kwargs)

    def build_tts_response(self, result: CallResult) -> str:
        """Generate a TTS-friendly response string."""
        if result.status == "success":
            items_str = ", ".join(result.items[:3])
            if len(result.items) > 3:
                items_str += f" and {len(result.items)-3} more"
            return (
                f"Thank you! Your order for {items_str} has been placed. "
                f"We will deliver to your number ending in {result.phone[-4:]}."
            )
        elif result.status == "no_phone":
            return "Sorry, I could not catch your phone number. Please say it again clearly."
        elif result.status == "no_items":
            return "Sorry, what items would you like to order? Please speak clearly."
        elif result.status == "duplicate":
            return "You already placed an order recently. We have it on record."
        elif result.status == "rate_limited":
            return "Too many orders placed recently. Please try again later."
        else:
            return "Sorry, something went wrong. Please call again."
