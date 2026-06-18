# vendor/wheels/

Pre-downloaded Python wheels for the lightweight, pure-Python dependencies
(FastAPI, Redis client, cryptography, httpx, loguru, websockets, etc.) so
they can be installed on a server with no internet access, or to speed up
deployment.

## What's NOT vendored here, and why

- **torch / transformers / peft / trl / datasets** — only needed for the
  *optional* fine-tuning step (`fine_tune_smollm.py`). These are large
  (100MB+ each) and most deployments will run the system using the
  pre-built GGUF models without ever fine-tuning, so they're left out to
  keep this package's size reasonable. Install them only if you plan to
  fine-tune: `pip install torch transformers peft trl datasets --break-system-packages`.

- **llama-cpp-python** — this package compiles a native C++ extension at
  install time (it has no simple universal pre-built wheel across CPU
  architectures, since it can optionally use AVX2/AVX-512/NEON depending
  on your CPU). Install normally at deploy time:
  `pip install llama-cpp-python --break-system-packages`
  (requires `cmake` and a C compiler — see `scripts/setup_asterisk.sh`'s
  apt-get block for the equivalent `build-essential` install on Debian/Ubuntu).

- **GGUF model weight files** (Whisper, SmolLM) — these are downloaded by
  `models/download_models.sh` from Hugging Face. They are not bundled in
  this package because they're large (~275MB combined) and are versioned,
  independently-updatable artifacts better fetched fresh at deploy time
  than baked into a code archive.

## Offline install using these wheels

```bash
pip install --no-index --find-links=vendor/wheels -r requirements.txt --break-system-packages
```

This installs everything listed here from the local `vendor/wheels/`
directory instead of reaching out to PyPI. Anything not found locally
(torch, llama-cpp-python, etc.) will need network access or a separately
prepared wheel for your target CPU architecture.
