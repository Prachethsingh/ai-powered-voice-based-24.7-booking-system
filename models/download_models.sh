#!/usr/bin/env bash
# models/download_models.sh — Download pre-quantized models
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL_DIR="$ROOT/models"
mkdir -p "$MODEL_DIR"

echo "================================"
echo " ai powered voice based 24.7 booking system — Model Download"
echo "================================"

# ── Whisper tiny.en (75MB, English-only STT) ─────────────────────────────
WHISPER_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin"
WHISPER_OUT="$MODEL_DIR/tiny.en.Q4_K_M.gguf"

if [ -f "$WHISPER_OUT" ]; then
  echo "✅ Whisper model already exists: $WHISPER_OUT"
else
  echo "Downloading Whisper tiny.en (~75MB)..."
  if command -v wget &>/dev/null; then
    wget -q --show-progress -O "$WHISPER_OUT" "$WHISPER_URL"
  else
    curl -L --progress-bar -o "$WHISPER_OUT" "$WHISPER_URL"
  fi
  echo "✅ Whisper downloaded: $WHISPER_OUT"
fi

# ── SmolLM 335M GGUF Q4 (200MB, intent extraction) ───────────────────────
# Use TheBloke's quantized version (widely available)
SMOLLM_URL="https://huggingface.co/bartowski/SmolLM2-360M-Instruct-GGUF/resolve/main/SmolLM2-360M-Instruct-Q4_K_M.gguf"
SMOLLM_OUT="$MODEL_DIR/smollm-335m-finetuned.Q4_K_M.gguf"

if [ -f "$SMOLLM_OUT" ]; then
  echo "✅ SmolLM model already exists: $SMOLLM_OUT"
else
  echo "Downloading SmolLM 360M Q4_K_M (~200MB)..."
  echo "(This is the BASE model. For best results, fine-tune with fine_tune_smollm.py)"
  if command -v wget &>/dev/null; then
    wget -q --show-progress -O "$SMOLLM_OUT" "$SMOLLM_URL"
  else
    curl -L --progress-bar -o "$SMOLLM_OUT" "$SMOLLM_URL"
  fi
  echo "✅ SmolLM downloaded: $SMOLLM_OUT"
fi

echo ""
echo "Models ready:"
ls -lh "$MODEL_DIR"/*.gguf 2>/dev/null || ls -lh "$MODEL_DIR"/*.bin 2>/dev/null || echo "  (checking...)"
echo ""
echo "Next steps:"
echo "  1. For better accuracy: python backend/python/fine_tune_smollm.py"
echo "  2. Start system:        ./scripts/start_all.sh"
