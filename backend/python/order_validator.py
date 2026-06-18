"""
order_validator.py — Phase 4: Order Validation and Confirmation

Standalone validation layer sitting between intent extraction (Phase 3)
and digital storage (Phase 5). Mirrors the internship roadmap's Phase 4
so each phase has a clear, gradeable module.

Validates:
  1. Phone number format (Indian 10-digit, starts 6-9)
  2. Duplicate detection (5-minute Redis window)
  3. Rate limiting (5 orders/hour per phone)
  4. Item list sanity (non-empty, no garbage entries)

Produces a human-readable TTS confirmation string for the caller.
"""
from dataclasses import dataclass
from typing import Optional

import dev_defaults  # noqa: F401  (sets dev env vars only if .env absent)
from loguru import logger

import config
from phone_validator import normalize_phone, validate_phone
from secure_db import db
from security import phone_encryptor
from audit_logger import audit


@dataclass
class ValidationResult:
    valid:          bool
    phone:          Optional[str]
    items:          list
    rejection_reason: Optional[str]   # None if valid
    confirmation_text: str            # TTS-ready message


class OrderValidator:
    """Phase 4: validates and confirms orders before digital storage."""

    MIN_ITEMS = 1
    MAX_ITEMS = 20    # sanity cap — a single call shouldn't yield 50 items

    def validate(self, phone: Optional[str], items: list, call_id: str = "unknown") -> ValidationResult:
        """
        Run all Phase 4 checks. Does NOT write to the database — that's
        Phase 5's job (digital_order_manager.py / secure_db.py). This
        module only decides accept/reject and builds the spoken response.
        """
        # ── Check 1: Phone format ───────────────────────────────────────
        normalized = normalize_phone(phone) if phone else None
        if not normalized:
            return ValidationResult(
                valid=False, phone=None, items=items,
                rejection_reason="invalid_phone",
                confirmation_text=(
                    "Sorry, I could not understand your phone number. "
                    "Please say your 10-digit mobile number clearly."
                ),
            )

        # ── Check 2: Item sanity ────────────────────────────────────────
        clean_items = [i.strip() for i in items if i and i.strip()]
        if len(clean_items) < self.MIN_ITEMS:
            return ValidationResult(
                valid=False, phone=normalized, items=[],
                rejection_reason="no_items",
                confirmation_text=(
                    "Sorry, I did not catch what you would like to order. "
                    "Please tell us the items you need."
                ),
            )
        if len(clean_items) > self.MAX_ITEMS:
            clean_items = clean_items[: self.MAX_ITEMS]
            logger.warning(f"[{call_id}] Item list truncated to {self.MAX_ITEMS}")

        # ── Check 3 & 4: Duplicate + rate limit ─────────────────────────
        # (Redis checks happen at write-time in secure_db.store_booking,
        #  but we pre-check here so we can give an accurate spoken
        #  response BEFORE attempting the write.)
        phone_hash = phone_encryptor.hash(normalized)

        if db._redis:
            dup_key = f"vb:dup:{phone_hash}"
            if db._redis.exists(dup_key):
                audit.log_db_reject(call_id, "duplicate")
                return ValidationResult(
                    valid=False, phone=normalized, items=clean_items,
                    rejection_reason="duplicate",
                    confirmation_text=(
                        "You already placed an order a few minutes ago. "
                        "We have it on record and it is being processed."
                    ),
                )

            rate_key = f"vb:rate:{phone_hash}"
            current = db._redis.get(rate_key)
            if current and int(current) >= config.RATE_LIMIT_PER_HOUR:
                audit.log_db_reject(call_id, "rate_limited")
                return ValidationResult(
                    valid=False, phone=normalized, items=clean_items,
                    rejection_reason="rate_limited",
                    confirmation_text=(
                        "You have reached the maximum number of orders for this hour. "
                        "Please try again later."
                    ),
                )

        # ── All checks passed ────────────────────────────────────────────
        items_str = self._speakable_item_list(clean_items)
        confirmation = (
            f"Thank you! Your order for {items_str} has been confirmed. "
            f"We will contact you on your number ending {normalized[-4:]}."
        )

        return ValidationResult(
            valid=True, phone=normalized, items=clean_items,
            rejection_reason=None,
            confirmation_text=confirmation,
        )

    @staticmethod
    def _speakable_item_list(items: list) -> str:
        """Turn ['rice 2kg', 'milk 1L', 'eggs'] into 'rice 2kg, milk 1L and eggs'."""
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        return ", ".join(items[:-1]) + f" and {items[-1]}"


# Singleton
order_validator = OrderValidator()


# ── CLI Test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    v = OrderValidator()
    r = v.validate("9876543210", ["rice 2kg", "milk 1L"], call_id="test")
    print(f"Valid: {r.valid}")
    print(f"Confirmation: {r.confirmation_text}")

    r2 = v.validate("12345", ["rice"], call_id="test2")
    print(f"\nValid: {r2.valid} | Reason: {r2.rejection_reason}")
    print(f"Confirmation: {r2.confirmation_text}")
