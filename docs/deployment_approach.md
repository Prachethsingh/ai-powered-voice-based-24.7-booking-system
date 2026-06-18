# Deployment Approach

### Target environment

- 1 VM, 2-4 vCPU, 4-8GB RAM (e.g. AWS t3.medium, or equivalent on any provider).
- No GPU, no CUDA, no specialized hardware.
- Estimated cost: ~Rs.5,000-7,000/month depending on provider and region.
- OS: Ubuntu 22.04/24.04 LTS or any modern Linux distribution.

### Option A — Bare-metal / VM script-based (fastest to get running)

```bash
git clone <this-repo>
cd ai-powered-voice-booking

./scripts/generate_keys.sh        # creates .env with all secrets, 600 permissions
./models/download_models.sh       # downloads Whisper tiny.en + SmolLM base GGUF

pip install -r requirements.txt
cd backend/node && npm install && cd ../..
cd frontend && npm install && cd ..

sudo ./scripts/setup_asterisk.sh  # installs + configures Asterisk PBX
./scripts/start_all.sh            # starts Redis, Python AI service, Node server, dashboard
```

Dashboard: `http://<server-ip>:3000`

### Option B — Docker Compose (reproducible, recommended for handoff)

```bash
./scripts/generate_keys.sh
./models/download_models.sh
docker-compose up -d
```

This brings up Redis, the Python AI service, the Node.js telephony backend, and the
React dashboard as four containers, each with health checks and automatic restart.
Asterisk itself (telephony) still runs on the host VM, since it needs direct network
access to carrier SIP trunks.

### Fine-tuning before going to production (recommended, not required)

The base SmolLM checkpoint downloaded by `download_models.sh` works out of the box via
the regex-ensemble fallback, but accuracy on Indian grocery/retail vocabulary improves
further after fine-tuning:

```bash
python training_data/augment_data.py        # expand 100 to 1000+ training samples
python backend/python/fine_tune_smollm.py    # LoRA fine-tune, CPU, ~2-4 hours
python backend/python/quantize_model.py      # merge LoRA + quantize to Q4_K_M GGUF
```

Update `.env`: `SMOLLM_MODEL_PATH=models/smollm-finetuned.Q4_K_M.gguf`, restart services.

### Scaling beyond one VM

State lives in Redis (dedup/rate-limit) and SQLite-with-WAL (bookings), both
shareable across processes. To scale horizontally: run a second copy of the Python and
Node stack on a second VM, pointed at the same Redis instance, behind a load balancer
that distributes incoming Asterisk trunks. No application code changes required — see
docs/concurrency_and_scalability.md for the underlying math.

### Monitoring in production

- `GET /health` (Node, port 8000): process uptime, active call count, dashboard client count.
- `GET /capacity` (Python AI service, port 8001): worker pool utilization, queue depth, average wait time.
- `logs/audit.log`: append-only, rotated at 10MB, retained 90 days, phone numbers stored only as SHA-256 hashes.
- Dashboard "Security" tab: live feed of rate-limit hits, duplicate rejections, auth failures.

### Backup

- `database/bookings.sqlite`: back up nightly with `sqlite3 bookings.sqlite ".backup backup.sqlite"`. WAL mode keeps the file consistent for this command at any time.
- `.env`: back up to a password manager or secrets vault, never to source control (already in `.gitignore`).