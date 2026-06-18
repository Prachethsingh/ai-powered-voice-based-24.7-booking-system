#!/usr/bin/env bash
# scripts/setup_asterisk.sh — Install and configure Asterisk PBX
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=============================="
echo " ai powered voice based 24.7 booking system — Asterisk Setup"
echo "=============================="

# Load .env
[ -f "$ROOT/.env" ] && source "$ROOT/.env" || { echo "❌ Run generate_keys.sh first"; exit 1; }

# Install Asterisk
if ! command -v asterisk &>/dev/null; then
  echo "Installing Asterisk..."
  apt-get update -qq
  apt-get install -y asterisk asterisk-config
fi
echo "✅ Asterisk installed"

# Copy configs
ASTERISK_ETC="/etc/asterisk"
cp "$ROOT/asterisk/extensions.conf" "$ASTERISK_ETC/extensions.conf"
cp "$ROOT/asterisk/pjsip.conf"      "$ASTERISK_ETC/pjsip.conf"

# Inject ARI password from .env
ARI_PW="${ASTERISK_ARI_PASSWORD:-change-me}"
cat > "$ASTERISK_ETC/ari.conf" <<EOF
[general]
enabled = yes
websocket_enabled = yes
allowed_origins = 127.0.0.1,localhost
pretty = no

[asterisk]
type = user
read_only = no
password = ${ARI_PW}
EOF

chmod 640 "$ASTERISK_ETC/ari.conf"
echo "✅ Asterisk configs deployed"

# Set file limits for concurrent calls
cat >> /etc/security/limits.conf <<EOF
asterisk soft nofile 8192
asterisk hard nofile 16384
EOF

# Enable + start
systemctl enable asterisk
systemctl restart asterisk
sleep 2

if systemctl is-active --quiet asterisk; then
  echo "✅ Asterisk running"
else
  echo "❌ Asterisk failed to start. Check: journalctl -u asterisk"
  exit 1
fi

echo ""
echo "Done! Test: asterisk -r -x 'core show version'"
