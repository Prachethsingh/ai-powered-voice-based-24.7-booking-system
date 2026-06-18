"""
dev_defaults.py — Ephemeral dev-mode secrets for standalone script testing.

Import this FIRST, before `import config`, in any module that should be
runnable directly (python3 some_module.py) without a real .env present:

    import dev_defaults   # noqa: F401  (side effect: sets env vars)
    import config

Safety: this ONLY injects throwaway values when no .env file exists at
the project root at all. If a real .env is present, this module does
nothing — config.py's own load_dotenv() is the single source of truth
in every real deployment. main.py (the actual production entrypoint)
never imports this module.
"""
import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/python -> backend -> root
_ENV_FILE = _ROOT / ".env"

if not _ENV_FILE.exists():
    _DEV_DEFAULTS = {
        "ENCRYPTION_KEY": "dev-key-32-bytes-padded-for-test",
        "ARI_JWT_SECRET":           "dev-secret-32-bytes-padded-here1",
        "WS_JWT_SECRET":            "dev-secret-32-bytes-padded-here2",
        "RTP_SECRET":               "dev-secret-32-bytes-padded-here3",
        "REDIS_PASSWORD":           "dev-pass",
        "ASTERISK_ARI_PASSWORD":    "dev-pass",
    }
    for _key, _val in _DEV_DEFAULTS.items():
        os.environ.setdefault(_key, _val)
