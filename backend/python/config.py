"""
config.py — Central configuration for ai powered voice based 24.7 booking system
All values from environment variables. Never hardcoded.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")


def _require(key: str) -> str:
    """Get env var or crash with clear message."""
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(
            f"❌ Required env var '{key}' is not set.\n"
            f"   Run: ./scripts/generate_keys.sh"
        )
    return val


# ── Security ─────────────────────────────────────────────────────────────
ENCRYPTION_KEY: str = _require("ENCRYPTION_KEY")
ARI_JWT_SECRET: str = _require("ARI_JWT_SECRET")
WS_JWT_SECRET: str  = _require("WS_JWT_SECRET")
RTP_SECRET: str     = _require("RTP_SECRET")
REDIS_PASSWORD: str = _require("REDIS_PASSWORD")
ASTERISK_ARI_PASSWORD: str = _require("ASTERISK_ARI_PASSWORD")

# ── Redis ─────────────────────────────────────────────────────────────────
REDIS_HOST: str = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
DEDUP_TTL: int  = int(os.getenv("REDIS_DEDUP_TTL_SECONDS", "300"))  # 5 min

# ── Asterisk ─────────────────────────────────────────────────────────────
ASTERISK_HOST: str      = os.getenv("ASTERISK_HOST", "127.0.0.1")
ASTERISK_ARI_PORT: int  = int(os.getenv("ASTERISK_ARI_PORT", "8088"))
ASTERISK_ARI_USER: str  = os.getenv("ASTERISK_ARI_USER", "asterisk")

# ── Models ───────────────────────────────────────────────────────────────
SMOLLM_MODEL_PATH: str  = os.getenv("SMOLLM_MODEL_PATH", "models/smollm-335m-finetuned.Q4_K_M.gguf")
WHISPER_MODEL_PATH: str = os.getenv("WHISPER_MODEL_PATH", "models/tiny.en.Q4_K_M.gguf")
WHISPER_LANGUAGE: str   = os.getenv("WHISPER_LANGUAGE", "en")

# ── Database ─────────────────────────────────────────────────────────────
SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "database/bookings.sqlite")

# ── Server Ports ─────────────────────────────────────────────────────────
PYTHON_API_PORT: int  = int(os.getenv("PYTHON_API_PORT", "8001"))
WEBSOCKET_PORT: int   = int(os.getenv("WEBSOCKET_PORT", "8080"))

# ── Security Policy ───────────────────────────────────────────────────────
RATE_LIMIT_PER_HOUR: int = int(os.getenv("RATE_LIMIT_BOOKINGS_PER_HOUR", "5"))
ALLOWED_WS_ORIGINS: list = os.getenv(
    "ALLOWED_WEBSOCKET_ORIGINS", "http://localhost:3000"
).split(",")
ALLOWED_ARI_IPS: list = os.getenv(
    "ALLOWED_ARI_IPS", "127.0.0.1"
).split(",")

# ── CPU Tuning ────────────────────────────────────────────────────────────
LLM_N_THREADS: int  = int(os.getenv("LLM_N_THREADS", "4"))
LLM_N_BATCH: int    = int(os.getenv("LLM_N_BATCH", "8"))
LLM_N_CTX: int      = int(os.getenv("LLM_N_CTX", "512"))
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "64"))
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))

# ── Concurrency (10-20 simultaneous calls) ─────────────────────────────────
MAX_CONCURRENT_WORKERS: int = int(os.getenv("MAX_CONCURRENT_WORKERS", "6"))
MAX_QUEUE_SIZE: int         = int(os.getenv("MAX_QUEUE_SIZE", "40"))

# ── Logging ───────────────────────────────────────────────────────────────
LOG_LEVEL: str      = os.getenv("LOG_LEVEL", "INFO")
AUDIT_LOG_PATH: str = os.getenv("AUDIT_LOG_PATH", "logs/audit.log")

# ── Indian Phone Pattern ──────────────────────────────────────────────────
# Starts with 6-9, followed by 9 more digits
INDIAN_PHONE_REGEX = r"^(\+91|0)?[6-9]\d{9}$"
