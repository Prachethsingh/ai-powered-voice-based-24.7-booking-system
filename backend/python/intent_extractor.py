"""
intent_extractor.py — Standalone Intent Extraction API

Thin wrapper around langchain_pipeline.py.
Use this if you want to call intent extraction
independently from the full voice pipeline.

Example:
    from intent_extractor import extract_intent
    result = extract_intent("I want rice and milk, number 9876543210")
    print(result)  # {"phone": "9876543210", "items": ["rice", "milk"], ...}
"""
import dev_defaults  # noqa: F401  (sets dev env vars only if .env absent)
from langchain_pipeline import get_pipeline


def extract_intent(text: str, call_id: str = "direct") -> dict:
    """
    Extract phone number and items from a voice transcript.

    Args:
        text:    Raw STT transcript
        call_id: Optional call identifier for logging

    Returns:
        {
            "phone":      "9876543210" | None,
            "items":      ["rice 2kg", "milk 1L"],
            "confidence": "high" | "low",
            "mode":       "llm" | "fallback_regex",
            "latency_ms": 234.5,
        }
    """
    return get_pipeline().process(text, call_id=call_id)


# ── CLI ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "I want 2 kg rice and 1 liter milk, my number is 9876543210"
    print(f"\nInput : {text}")
    r = extract_intent(text)
    print(f"Phone : {r.get('phone', 'NOT FOUND')}")
    print(f"Items : {r.get('items', [])}")
    print(f"Mode  : {r.get('mode')} | {r.get('latency_ms', 0):.1f}ms")
