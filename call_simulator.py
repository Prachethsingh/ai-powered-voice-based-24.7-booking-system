"""
call_simulator.py — Simulate voice calls for testing WITHOUT Asterisk

Lets you test the full pipeline from the command line:
  python call_simulator.py                     # interactive mode
  python call_simulator.py "I want rice 9876543210"  # single shot
  python call_simulator.py --batch             # run all test cases

No microphone, no Asterisk, no phone needed.
It goes: text → LangChain pipeline → DB → prints result
"""
import os
import sys
import time
import json
import argparse
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend/python"))

import dev_defaults  # noqa: F401  (sets throwaway dev secrets only if .env absent)

# Load real .env if present. load_dotenv() does NOT override already-set
# env vars by default, so this only fills in values dev_defaults left
# unset — when .env truly exists, dev_defaults already skipped itself.
if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()

from langchain_pipeline import get_pipeline, VoiceOrderPipeline
from phone_validator import extract_phone_from_text

# ── Test Cases ─────────────────────────────────────────────────────────────

TEST_CASES = [
    # Format: (input_text, expected_phone, expected_items_keywords)
    ("I want 2 kg rice and 1 liter milk, my phone is 9876543210",
     "9876543210", ["rice", "milk"]),
    ("Please send bread and eggs number 8765432109",
     "8765432109", ["bread", "eggs"]),
    ("Mujhe chawal aur dal chahiye, number 7654321098",
     "7654321098", ["rice", "dal"]),
    ("Oru kilo arisi venum en number 9123456789",
     "9123456789", ["rice"]),
    ("Two kilos sugar and one packet salt call nine eight seven six five four three two one zero",
     "9876543210", ["sugar", "salt"]),
    ("I need tomatoes onions potatoes contact 6543210987",
     "6543210987", ["tomato", "onion", "potato"]),
    # Edge cases
    ("Hello I want rice",       None,         ["rice"]),   # No phone
    ("My number is 9876543210", "9876543210", []),          # No items
    ("",                        None,         []),          # Empty
]

RESET = "\033[0m"


def simulate_call(text: str, call_id: str = None) -> dict:
    """Run a single simulated call through the full pipeline."""
    if not call_id:
        call_id = f"sim_{uuid.uuid4().hex[:8]}"

    pipeline = get_pipeline()
    t0 = time.perf_counter()
    result = pipeline.process(text, call_id=call_id)
    total_ms = (time.perf_counter() - t0) * 1000

    # Try to store in DB if phone + items found
    booking_id = None
    status = "success"
    message = ""

    if result.get("phone") and result.get("items"):
        try:
            from secure_db import db
            db_result = db.store_booking(
                phone=result["phone"],
                items=result["items"],
                call_id=call_id,
            )
            if db_result["success"]:
                booking_id = db_result.get("booking_id")
                message = db_result.get("message", "")
                status = "success"
            else:
                status = db_result.get("reason", "error")
                message = f"DB rejected: {status}"
        except Exception as e:
            # DB not available in pure test mode
            status = "success"
            message = "(DB skipped in test mode)"
    elif not result.get("phone"):
        status = "no_phone"
        message = "Phone not found in transcript"
    else:
        status = "no_items"
        message = "Items not found in transcript"

    return {
        "call_id":    call_id,
        "input":      text,
        "phone":      result.get("phone"),
        "items":      result.get("items", []),
        "mode":       result.get("mode", "unknown"),
        "status":     status,
        "message":    message,
        "booking_id": booking_id,
        "latency_ms": total_ms,
    }


def print_result(r: dict):
    status_icons = {
        "success": "[OK]",
        "no_phone": "[NO-PHONE]",
        "no_items": "[NO-ITEMS]",
        "error": "[ERROR]",
    }
    icon = status_icons.get(r["status"], "[?]")
    print(f"\n{icon} {r['status'].upper()}{RESET}")
    print(f"  Input     : {r['input'][:70]}")
    print(f"  Phone     : {r['phone'] or 'NOT FOUND'}")
    print(f"  Items     : {', '.join(r['items']) if r['items'] else 'NOT FOUND'}")
    print(f"  Mode      : {r['mode']}")
    print(f"  Latency   : {r['latency_ms']:.0f}ms")
    if r.get("booking_id"):
        print(f"  Booking # : {r['booking_id']}")
    if r.get("message"):
        print(f"  Message   : {r['message']}")


def run_batch():
    """Run all test cases and print pass/fail summary."""
    print("\n" + "=" * 60)
    print("  ai powered voice based 24.7 booking system — Batch Simulation")
    print("=" * 60)

    pipeline = VoiceOrderPipeline(model_path="models/nonexistent.gguf")  # forces fallback

    passed = 0
    failed = 0
    results = []

    for i, (text, exp_phone, exp_keywords) in enumerate(TEST_CASES, 1):
        r = pipeline.process(text, call_id=f"batch_{i:03d}")

        phone_ok = (r.get("phone") == exp_phone)
        items_ok = all(
            any(kw.lower() in item.lower() for item in r.get("items", []))
            for kw in exp_keywords
        ) if exp_keywords else True

        ok = phone_ok and items_ok
        passed += int(ok)
        failed += int(not ok)

        icon = "[OK]" if ok else "[FAIL]"
        print(f"\n[{i:2d}] {icon}  {text[:55]}")
        check = "[+]" if phone_ok else "[-]"
        print(f"      Phone: {r.get('phone')} (exp: {exp_phone}) {check}")
        check2 = "[+]" if items_ok else "[-]"
        print(f"      Items: {r.get('items')} | kw: {exp_keywords} {check2}")
        print(f"      Mode : {r.get('mode')} | {r.get('latency_ms', 0):.0f}ms")

        results.append({"ok": ok, "input": text, **r})

    print("\n" + "=" * 60)
    print(f"  Results: {passed}/{len(TEST_CASES)} passed | {failed} failed")
    print("=" * 60)
    return results


def interactive_mode():
    """REPL for manual testing."""
    print("\n" + "=" * 60)
    print("  ai powered voice based 24.7 booking system — Call Simulator (Interactive)")
    print("  Type a voice message, or 'quit' to exit")
    print("  Example: I want rice, number is 9876543210")
    print("=" * 60 + "\n")

    while True:
        try:
            text = input("Caller says: ").strip()
            if text.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            if not text:
                continue
            r = simulate_call(text)
            print_result(r)
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


def main():
    parser = argparse.ArgumentParser(description="ai powered voice based 24.7 booking system Call Simulator")
    parser.add_argument("text", nargs="?", help="Voice text to process")
    parser.add_argument("--batch", action="store_true", help="Run all test cases")
    parser.add_argument("--json",  action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.batch:
        results = run_batch()
        if args.json:
            print(json.dumps(results, indent=2))
    elif args.text:
        r = simulate_call(args.text)
        if args.json:
            print(json.dumps(r, indent=2))
        else:
            print_result(r)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()