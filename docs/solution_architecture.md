# Solution Architecture
## AI-Powered 24/7 Call Ordering System — ai powered voice based 24.7 booking system

### 1. Problem Mapping

| Challenge from brief | How this solution addresses it |
|---|---|
| Orders only via phone, no digital workflow | Every call is transcribed and written to a structured database automatically — no manual re-entry |
| Miscommunication → wrong quantities | LangChain ensemble pipeline cross-validates phone numbers via regex + LLM voting; low-confidence extractions trigger a spoken clarification instead of guessing |
| Staff time spent on order-taking | Fully automated intake; staff only handle fulfillment, not transcription |
| Business tied to working hours | Asterisk PBX answers 24/7; no human required to be on shift |
| No centralized monitoring | Live React dashboard with WebSocket updates, booking history, and customer analytics |

### 2. Constraint Compliance

| Constraint | Compliance |
|---|---|
| No high-GPU models | `n_gpu_layers=0` everywhere; Whisper tiny.en (75MB) + SmolLM 335M-360M Q4 (200MB) run entirely on CPU |
| Cost-effective deployment | Single ~₹5-7k/month VM (2-4 vCPU, 4-8GB RAM) handles the full pipeline + dashboard |
| Standard computing resources | No specialized hardware, no CUDA, no custom silicon — runs on any Linux VM |
| Efficient architecture over brute force | Ensemble voting (regex + 2x small-LLM passes) substitutes for a single giant model — see `docs/accuracy_approach.md` |
| Scalability & maintainability | Stateless worker pool (`concurrent_call_manager.py`) + Docker Compose; horizontal scaling = add another VM pointed at the same Redis/SQLite |

### 3. End-to-End Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Customer 📞 │────▶│  Asterisk    │────▶│ Whisper.cpp  │────▶│ Concurrent   │
│  (any phone) │     │  PBX + ARI   │     │  STT (CPU)   │     │ Call Manager │
└──────────────┘     └──────────────┘     └──────────────┘     │ (6 workers,  │
                            │                                    │ 40-deep queue)│
                            │                                    └──────┬───────┘
                            │                                           ▼
                            │                                  ┌──────────────────┐
                            │                                  │ LangChain Pipeline │
                            │                                  │ (CoT prompt +      │
                            │                                  │  regex ensemble)   │
                            │                                  └──────┬─────────────┘
                            │                                         ▼
                            │                                  ┌──────────────────┐
                            │                                  │ Order Validator    │
                            │                                  │ (Phase 4: phone    │
                            │                                  │  format, dedup,    │
                            │                                  │  rate limit)       │
                            │                                  └──────┬─────────────┘
                            │                                         ▼
                            │                                  ┌──────────────────┐
                            │                                  │ Secure DB          │
                            │                                  │ (SQLite + Redis,   │
                            │                                  │  AES-128 phones)   │
                            │                                  └──────┬─────────────┘
                            │                                         ▼
                  ┌─────────▼─────────┐                      ┌──────────────────┐
                  │   TTS Response     │◀─────────────────────│  WebSocket Bridge │
                  │   back to caller   │                      │  → Live Dashboard │
                  └────────────────────┘                      └────────┬─────────┘
                                                                         ▼
                                                              ┌──────────────────┐
                                                              │ External Sync      │
                                                              │ (Phase 7: webhook, │
                                                              │  CSV/JSON export)  │
                                                              └────────────────────┘
```

### 4. Component Responsibilities

- **Asterisk PBX + ARI** (`asterisk/`, `backend/node/ari_handler.js`): answers calls, records utterances, plays TTS responses, enforces a 2-minute max call duration.
- **Concurrent Call Manager** (`backend/python/concurrent_call_manager.py`): bounded `ThreadPoolExecutor` (default 6 workers, 40-slot queue) so 10-20 simultaneous callers are queued and drained safely instead of overloading the CPU.
- **LangChain Pipeline** (`backend/python/langchain_pipeline.py`, `advanced_pipeline.py`): `PromptTemplate` → `LlamaCpp` (SmolLM GGUF) → custom `BaseOutputParser`, with a parallel regex extractor for ensemble voting.
- **Order Validator** (`backend/python/order_validator.py`): Phase 4 — phone format check, duplicate detection (5-min Redis window), rate limiting (5/hr), builds the spoken confirmation string.
- **Secure DB** (`backend/python/secure_db.py`): Phase 5 — SQLite (WAL mode) with AES-128 (Fernet) encrypted phone numbers, parameterized queries only.
- **Live Dashboard** (`frontend/`): Phase 6 — React + WebSocket, shows active calls, booking table, hourly chart, security event log.
- **External Integration** (`backend/python/external_integration.py`): Phase 7 — optional webhook POST to an ERP/POS, plus CSV/JSON export for legacy systems.

### 5. Why This Is "Efficient Architecture, Not Brute Force"

Rather than reaching for a large hosted LLM, accuracy is recovered through **structure**, not parameter count:
1. Chain-of-thought prompting forces the small model to reason before answering.
2. Two inference passes at different temperatures are cross-checked for self-consistency.
3. A deterministic regex extractor validates the LLM's phone number output (phone numbers are a closed format — regex is *more* reliable here than a generative model).
4. Low-confidence results are routed back to the caller for clarification instead of silently guessing.

Full rationale: see `docs/accuracy_approach.md`.
