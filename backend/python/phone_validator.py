"""
phone_validator.py — Indian phone number validation and extraction

Handles:
- 10-digit numbers (9876543210)
- With country code (+919876543210 or 919876543210)
- With spaces/dashes (98765 43210)
- Spoken form ("nine eight seven six five four three two one zero")
- Mixed (caller says digits one by one)
"""
import re
from typing import Optional
from loguru import logger

# Valid Indian mobile prefixes (6, 7, 8, 9)
INDIAN_MOBILE_PATTERN = re.compile(r"^[6-9]\d{9}$")

# Patterns to extract from raw text
DIGIT_PATTERNS = [
    re.compile(r"\b([6-9]\d{9})\b"),                     # 10-digit run
    re.compile(r"\b(\+91[6-9]\d{9})\b"),                 # +91 prefix
    re.compile(r"\b(91[6-9]\d{9})\b"),                   # 91 prefix
]

# Spoken digit words → digit
SPOKEN_DIGITS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "oh": "0",  # Common alternative for zero in phone numbers
}

# Hindi digit words (for mixed language)
HINDI_DIGITS = {
    "shunya": "0", "ek": "1", "do": "2", "teen": "3", "char": "4",
    "paanch": "5", "chhe": "6", "saat": "7", "aath": "8", "nau": "9",
}


def normalize_phone(phone: str) -> Optional[str]:
    """Strip country code, spaces, dashes. Return 10-digit or None."""
    cleaned = re.sub(r"[\s\-\(\)\.]", "", phone.strip())
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    if INDIAN_MOBILE_PATTERN.match(cleaned):
        return cleaned
    return None


def extract_phone_from_text(text: str) -> Optional[str]:
    """
    Extract Indian phone number from STT text.

    Tries multiple strategies:
    1. Direct digit pattern (most common)
    2. Spoken digit words ("nine eight seven...")
    3. Hindi digit words ("nau aath saat...")
    """
    # Strategy 1: Direct digit pattern
    for pattern in DIGIT_PATTERNS:
        match = pattern.search(text)
        if match:
            phone = normalize_phone(match.group(1))
            if phone:
                logger.debug(f"Phone extracted (digit pattern): {phone}")
                return phone

    # Strategy 2: Spoken English digits
    phone = _extract_spoken_digits(text, SPOKEN_DIGITS)
    if phone:
        logger.debug(f"Phone extracted (spoken English): {phone}")
        return phone

    # Strategy 3: Hindi digit words
    phone = _extract_spoken_digits(text, HINDI_DIGITS)
    if phone:
        logger.debug(f"Phone extracted (Hindi digits): {phone}")
        return phone

    logger.warning(f"No phone found in: '{text[:60]}...'")
    return None


def _extract_spoken_digits(text: str, word_map: dict) -> Optional[str]:
    """Convert consecutive spoken digit words to a phone number string."""
    words = text.lower().split()
    digit_string = ""
    found_digits = []

    for word in words:
        clean_word = re.sub(r"[^a-z]", "", word)
        if clean_word in word_map:
            found_digits.append(word_map[clean_word])
        else:
            # Break in spoken digits — check if we have 10
            if len(found_digits) == 10:
                digit_string = "".join(found_digits)
                break
            elif len(found_digits) > 10:
                # Might have extra digits, take last 10
                digit_string = "".join(found_digits[-10:])
                break
            found_digits = []  # Reset if broken

    if not digit_string and len(found_digits) == 10:
        digit_string = "".join(found_digits)

    return normalize_phone(digit_string) if digit_string else None


def validate_phone(phone: str) -> bool:
    """Return True if phone is a valid Indian mobile number."""
    return normalize_phone(phone) is not None


def mask_phone(phone: str) -> str:
    """Mask phone for safe logging: 9876XXXXX0"""
    if len(phone) < 10:
        return "XXXXXXXXXX"
    return phone[:4] + "X" * (len(phone) - 5) + phone[-1]


# ── Quick Tests ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("9876543210", "9876543210"),
        ("+919876543210", "9876543210"),
        ("919876543210", "9876543210"),
        ("98765 43210", "9876543210"),
        ("98765-43210", "9876543210"),
        ("I want rice my number is nine eight seven six five four three two one zero", "9876543210"),
        ("nau aath saat chhe paanch char teen do ek shunya", "9876543210"),
    ]

    for inp, expected in tests:
        if len(inp) > 20:
            result = extract_phone_from_text(inp)
        else:
            result = normalize_phone(inp)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{inp[:40]}' → {result} (expected {expected})")
