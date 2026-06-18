"""
external_integration.py — Phase 7: External System Integration

Connects ai powered voice based 24.7 booking system order data to outside systems:
  - Generic webhook POST (ERP, POS, any REST endpoint)
  - CSV export (for legacy/offline systems, Excel-based shops)
  - JSON export (for custom integrations)
  - Generic webhook POST (ERP, POS, any REST endpoint)
  - CSV export (for legacy/offline systems, Excel-based shops)
  - JSON export (for custom integrations)

All integrations are OPTIONAL and OFF by default — a small shop using
only the dashboard needs none of this. Configure via .env:
  WEBHOOK_URL=https://your-erp.example.com/api/orders
  WEBHOOK_AUTH_TOKEN=...
"""
import csv
import io
import json
import os
import time
from pathlib import Path
from typing import Optional

import dev_defaults  # noqa: F401  (sets dev env vars only if .env absent)
import httpx
from loguru import logger

import config


class ExternalIntegration:
    """Phase 7: optional outbound sync to ERP / POS / file exports."""

    def __init__(self):
        self.webhook_url   = os.getenv("WEBHOOK_URL", "")
        self.webhook_token = os.getenv("WEBHOOK_AUTH_TOKEN", "")
        self.enabled = bool(self.webhook_url)

        if self.enabled:
            logger.info(f"✅ External webhook integration enabled: {self.webhook_url}")
        else:
            logger.info("ℹ️  External webhook integration disabled (no WEBHOOK_URL set)")

    # ── Webhook (ERP / POS) ──────────────────────────────────────────────

    def sync_booking(self, booking: dict) -> bool:
        """
        POST a booking to the configured external webhook.
        Booking dict should have: id, phone (masked), items, status, created_at.
        Returns True on success, False otherwise (never raises — sync
        failures must never block the caller's order from being saved).
        """
        if not self.enabled:
            return False

        payload = {
            "source": "ai-powered-voice-booking",
            "booking_id": booking.get("id"),
            "items": booking.get("items"),
            "status": booking.get("status"),
            "created_at": booking.get("created_at"),
            # Note: we send the MASKED phone only, never the raw/decrypted
            # number, to external systems unless explicitly configured
            # with a trusted internal ERP that has its own access controls.
            "phone_masked": booking.get("phone"),
        }

        headers = {"Content-Type": "application/json"}
        if self.webhook_token:
            headers["Authorization"] = f"Bearer {self.webhook_token}"

        try:
            resp = httpx.post(self.webhook_url, json=payload, headers=headers, timeout=5.0)
            if resp.status_code in (200, 201, 202):
                logger.info(f"✅ Booking #{booking.get('id')} synced to external system")
                return True
            logger.warning(
                f"⚠️  Webhook sync failed for booking #{booking.get('id')}: "
                f"HTTP {resp.status_code}"
            )
            return False
        except httpx.RequestError as e:
            logger.warning(f"⚠️  Webhook sync error for booking #{booking.get('id')}: {e}")
            return False

    # ── CSV Export (legacy systems) ──────────────────────────────────────

    @staticmethod
    def export_csv(bookings: list, output_path: str = "exports/orders_export.csv") -> str:
        """
        Export a list of booking dicts to CSV for Excel-based shops
        or legacy POS systems that import via file upload.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Booking ID", "Phone (masked)", "Items", "Status", "Created At"])
            for b in bookings:
                items = b.get("items")
                items_str = ", ".join(items) if isinstance(items, list) else str(items)
                created = b.get("created_at")
                created_str = (
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created))
                    if created else ""
                )
                writer.writerow([
                    b.get("id"), b.get("phone"), items_str,
                    b.get("status"), created_str,
                ])

        logger.info(f"✅ Exported {len(bookings)} bookings → {out}")
        return str(out)

    # ── JSON Export ───────────────────────────────────────────────────────

    @staticmethod
    def export_json(bookings: list, output_path: str = "exports/orders_export.json") -> str:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(bookings, f, indent=2, default=str)
        logger.info(f"✅ Exported {len(bookings)} bookings → {out}")
        return str(out)


# Singleton
external_integration = ExternalIntegration()


# ── CLI Test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_bookings = [
        {"id": 1, "phone": "9876XXXXX0", "items": ["rice 2kg", "milk 1L"],
         "status": "pending", "created_at": time.time()},
        {"id": 2, "phone": "8765XXXXX9", "items": ["bread", "eggs"],
         "status": "fulfilled", "created_at": time.time() - 3600},
    ]
    integ = ExternalIntegration()
    csv_path  = integ.export_csv(sample_bookings)
    json_path = integ.export_json(sample_bookings)
    print(f"CSV : {csv_path}")
    print(f"JSON: {json_path}")
