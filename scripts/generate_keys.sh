#!/usr/bin/env bash
# =============================================================
# scripts/generate_keys.sh — Generate all security keys for .env
# Run ONCE before first deployment: ./scripts/generate_keys.sh
# =============================================================

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=============================================="
echo " ai powered voice based 24.7 booking system — Security Key Generator"
echo "=============================================="

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "❌ python3 not found. Install it first."
  exit 1
fi

# Install cryptography if needed
python3 -c "from cryptography.fernet import Fernet" 2>/dev/null || \
  pip3 install cryptography -q

# Generate keys
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ARI_JWT=$(python3 -c "import secrets; print(secrets.token_hex(32))")
WS_JWT=$(python3 -c "import secrets; print(secrets.token_hex(32))")
RTP_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
REDIS_PW=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
ARI_PW=$(python3 -c "import secrets; print(secrets.token_urlsafe(20))")

ENV_FILE="$ROOT/.env"

if [ -f "$ENV_FILE" ]; then
  cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%s)"
  echo "ℹ️  Backed up existing .env to .env.backup.*"
fi

cat > "$ENV_FILE" <<EOF
# ============================================================
# ai powered voice based 24.7 booking system — Auto-generated .env
# Generated: $(date)
# KEEP THIS FILE SECRET. Never commit to git.
# ============================================================

# Encryption
ENCRYPTION_KEY=${FERNET_KEY}

# JWT
ARI_JWT_SECRET=${ARI_JWT}
WS_JWT_SECRET=${WS_JWT}

# RTP
RTP_SECRET=${RTP_SECRET}

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PW}
REDIS_DEDUP_TTL_SECONDS=300

# Asterisk
ASTERISK_HOST=127.0.0.1
ASTERISK_ARI_PORT=8088
ASTERISK_ARI_USER=asterisk
ASTERISK_ARI_PASSWORD=${ARI_PW}

# Model Paths
SMOLLM_MODEL_PATH=models/smollm-335m-finetuned.Q4_K_M.gguf
WHISPER_MODEL_PATH=models/tiny.en.Q4_K_M.gguf
WHISPER_LANGUAGE=en

# Database
SQLITE_DB_PATH=database/bookings.sqlite

# Ports
PYTHON_API_PORT=8001
NODE_SERVER_PORT=8000
WEBSOCKET_PORT=8080
REACT_PORT=3000

# Security Policy
RATE_LIMIT_BOOKINGS_PER_HOUR=5
ALLOWED_WEBSOCKET_ORIGINS=http://localhost:3000
ALLOWED_ARI_IPS=127.0.0.1

# CPU Tuning
LLM_N_THREADS=4
LLM_N_BATCH=8
LLM_N_CTX=512
LLM_MAX_TOKENS=64
LLM_TEMPERATURE=0.1

# Logging
LOG_LEVEL=INFO
AUDIT_LOG_PATH=logs/audit.log
EOF

# Secure permissions
chmod 600 "$ENV_FILE"

echo ""
echo "✅ .env created at: $ENV_FILE"
echo "✅ Permissions: 600 (owner read/write only)"
echo ""
echo "Generated keys:"
echo "  ENCRYPTION_KEY            = ${FERNET_KEY:0:10}..."
echo "  ARI_JWT_SECRET            = ${ARI_JWT:0:10}..."
echo "  WS_JWT_SECRET             = ${WS_JWT:0:10}..."
echo "  RTP_SECRET                = ${RTP_SECRET:0:10}..."
echo "  REDIS_PASSWORD            = ${REDIS_PW:0:8}..."
echo "  ASTERISK_ARI_PASSWORD     = ${ARI_PW:0:8}..."
echo ""
echo "⚠️  Update asterisk/ari.conf with ARI password:"
echo "   password = ${ARI_PW}"
echo ""
echo "Next: ./scripts/setup_asterisk.sh"
