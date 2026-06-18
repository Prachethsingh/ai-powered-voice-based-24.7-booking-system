# Workflow Documentation
## End-to-End Order Flow, Mapped to the 7-Phase Roadmap

### Phase 1 — Business Flow Understanding

**Traditional process:** customer calls → staff answers → customer lists items verbally →
staff writes them down → staff re-enters into Excel/POS → staff confirms verbally.

**Pain points this creates:** limited to working hours, transcription errors, 5-10 minutes
per order, no centralized record, no visibility into demand patterns.

**This system's response:** every step from "phone rings" to "order saved" is automated,
with a human only re-entering the loop for fulfillment (packing/delivery), not data entry.

| Metric | Traditional | This System |
|---|---|---|
| Availability | Working hours only | 24/7 |
| Time per order | 5-10 minutes | ~1-2 seconds compute + queue wait |
| Data entry errors | Human transcription risk | Ensemble-validated extraction, low-confidence → re-ask |
| Order visibility | Scattered paper/Excel | Centralized SQLite + live dashboard |

### Phase 2 — Voice-Based Order Reception

1. Customer dials the business number.
2. Asterisk PBX (`asterisk/extensions.conf`) routes the call into the `booking-system` Stasis app.
3. `ari_handler.js` answers instantly, plays a greeting, and starts recording
   (silence-terminated, max 10s per utterance, max 2 minutes per call).
4. The recorded WAV is handed to the Python AI service.

### Phase 3 — Order Understanding Engine

1. `stt_engine.py` transcribes the recording with Whisper `tiny.en` (CPU, ~0.5s).
2. The transcript enters the LangChain pipeline (`langchain_pipeline.py` /
   `advanced_pipeline.py`): a chain-of-thought prompt asks SmolLM to restate what it
   heard, then extract `PHONE:` and `ITEMS:` in a fixed format.
3. A parallel regex extractor (`FallbackParser`) independently extracts the same fields.
4. The two are cross-checked; phone numbers default to the regex result when they
   disagree (closed format — more reliable than generation), items default to the LLM
   result (open vocabulary — generalizes better).

### Phase 4 — Order Validation and Confirmation

`order_validator.py` runs four checks before anything is written to storage:
1. Phone format (Indian 10-digit, starts 6-9).
2. Item list sanity (non-empty, capped at 20 items per call).
3. Duplicate check (same phone number within the last 5 minutes → rejected).
4. Rate limit (max 5 orders/hour per phone number).

Each outcome produces a spoken confirmation string ready for TTS playback —
e.g. *"Thank you! Your order for rice 2kg and milk 1L has been confirmed."*

### Phase 5 — Digital Order Management

`secure_db.py` writes the validated order to SQLite:
- Phone numbers are encrypted (AES-128-CBC / Fernet) before storage — never stored in
  plaintext.
- A `users` table tracks repeat customers and total order count.
- Booking status moves `pending → confirmed → fulfilled` (or `cancelled`), updatable
  from the dashboard.

### Phase 6 — Dashboard and Monitoring

The React dashboard (`frontend/`) connects over a JWT/origin-checked WebSocket and shows:
- **Live Calls** — calls currently being processed.
- **Bookings** — full order table with status-update buttons.
- **Metrics** — hourly order volume chart, status distribution, pipeline latency targets.
- **Security** — audit event feed (rate limits hit, duplicates rejected, auth failures),
  with phone numbers shown only as a one-way SHA-256 hash, never in plaintext.

### Phase 7 — External System Integration

`external_integration.py` provides three optional paths, all off by default:
1. **Webhook** — POST each confirmed booking to an ERP/POS endpoint (`WEBHOOK_URL` in `.env`).
2. **CSV export** — `/export/csv` endpoint, for shops that import orders into Excel/Tally.
3. **JSON export** — `/export/json` endpoint, for custom downstream integrations.

### Total Time Budget (per call, compute only)

| Step | Target latency |
|---|---|
| STT (Whisper tiny.en, Q4) | ~400-600ms |
| Intent extraction (ensemble, 2 LLM passes + regex) | ~600-900ms |
| Validation + DB write | ~50-100ms |
| **Total compute** | **~1.5-2s** |
| Queue wait at 10-20 concurrent callers, 6 workers | typically <2s additional |
