# Concurrency & Scalability
## Handling 10-20 Simultaneous Calls on CPU-Only Hardware

### The model

`concurrent_call_manager.py` wraps a bounded `ThreadPoolExecutor`:

- **Workers** (`MAX_CONCURRENT_WORKERS`, default 6): the number of calls actively
  running inference (STT + LLM) at once.
- **Queue** (`MAX_QUEUE_SIZE`, default 40): calls beyond the active worker count wait
  here instead of being dropped or crashing the process.
- **Per-call timeout** (20s): a runaway call can't starve the queue forever.

```
20 callers ring in at once
        │
        ▼
┌───────────────────┐
│  Bounded Queue     │   capacity 40 — comfortably covers 10-20 concurrent callers
│  (FIFO)            │   with headroom for bursts
└─────────┬──────────┘
          │ drains into
          ▼
┌───────────────────┐
│  6 Worker Threads  │   each runs: STT (~0.5s) → ensemble intent (~0.7s)
│  (ThreadPoolExecutor)│  → validate → DB write (~0.1s)
└───────────────────┘
```

### Why threads, not processes, work here

`llama.cpp` and `whisper.cpp` (the underlying C++ inference engines behind
`llama-cpp-python` and the Whisper bindings) release the Python GIL during the actual
compute call. That means a `ThreadPoolExecutor` gets **real parallelism** for the
expensive part of the work, while still sharing one loaded copy of each model across
all threads — avoiding the multi-GB memory blowup you'd get from spawning 6-20 separate
model-loading processes.

### Sustained throughput math (single 2-4 vCPU VM)

| Step | Latency per call |
|---|---|
| STT (Whisper tiny.en Q4) | ~400-600ms |
| Intent (ensemble: 2 LLM passes + regex) | ~600-900ms |
| Validate + DB write | ~50-100ms |
| **Total compute per call** | **~1.5-2s** |

With 6 worker threads draining a queue at that rate:
- Throughput ≈ 6 calls / 1.75s ≈ **~200 calls/minute** sustained.
- 20 callers arriving at the same instant: queue drains in roughly 20/6 × 1.75s ≈ **~6
  seconds** worst case for the last caller — acceptable for a "please hold" UX, and well
  inside the `MAX_QUEUE_SIZE=40` capacity so nothing gets rejected.

### What happens under real overload

If the queue genuinely fills (sustained load far beyond 10-20 concurrent, e.g. a flash
sale with 60+ simultaneous callers), `submit()` returns `None` and the caller hears a
"system is busy, please try again shortly" message rather than the request silently
hanging or the process crashing. This is a deliberate design choice: **predictable
degradation, not silent failure.**

### Scaling beyond one VM

Because state lives in Redis (dedup/rate-limit) and SQLite-with-WAL (bookings), scaling
out is just running a second copy of the Python+Node stack pointed at the same Redis
instance and a shared SQLite file (or swapping SQLite for Postgres at that point) behind
a load balancer that distributes incoming Asterisk trunks across VMs. No code changes
are required in the call-processing logic — `concurrent_call_manager.py`,
`secure_db.py`, and `langchain_pipeline.py` are all stateless per-call.

### Tuning knobs (`.env`)

```
MAX_CONCURRENT_WORKERS=6   # raise on a bigger VM (rule of thumb: vCPU count - 1)
MAX_QUEUE_SIZE=40          # 2x your expected peak concurrent callers
LLM_N_THREADS=4            # threads PER inference call (llama.cpp internal)
```

Note `LLM_N_THREADS` and `MAX_CONCURRENT_WORKERS` both consume CPU — on a 4-vCPU box,
`6 workers × 4 internal threads` would oversubscribe the CPU. A safe starting point on
a 4-vCPU VM is `MAX_CONCURRENT_WORKERS=4` and `LLM_N_THREADS=2`; tune upward while
watching `GET /capacity` and server CPU usage.
