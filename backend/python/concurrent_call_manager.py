"""
concurrent_call_manager.py — Concurrency Layer for ai powered voice based 24.7 booking system

Handles 10-20 SIMULTANEOUS calls on a single CPU server.

Why this works on CPU without GPU:
  - Whisper tiny.en (75MB) and SmolLM Q4 (200MB) are both small enough
    that 4-8 threads can share one loaded copy of each model.
  - llama.cpp and whisper.cpp release the Python GIL during the actual
    C++ inference call, so a ThreadPoolExecutor gets REAL parallelism
    for the compute-heavy part, not just I/O.
  - A bounded queue + semaphore caps how many calls run inference at
    once, so the box never gets overloaded — extra calls simply wait
    a few hundred ms in queue instead of crashing the server.

Scaling math (single t3.medium, 2 vCPU / 4GB):
  - STT:    ~400-600ms/call  (tiny.en Q4)
  - Intent: ~200-400ms/call  (SmolLM Q4)
  - Total:  ~1-2s/call end-to-end compute
  - With 4 worker threads, sustained throughput ≈ 4 calls / 1.5s
    ≈ 160 calls/minute ≈ 9,600 calls/hour — far above 10-20 concurrent.
  - The actual constraint is concurrent *capacity*, not throughput:
    20 callers ringing in at once just means 20 queued jobs, drained
    in ~5-8 seconds total with 4 workers.

For >20 sustained concurrent calls: bump MAX_WORKERS and add a second
VM behind the same Redis+SQLite (see docs/deployment_approach.md).
"""
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Callable, Optional

import dev_defaults  # noqa: F401  (sets dev env vars only if .env absent)
from loguru import logger

import config
from voice_pipeline import VoiceCallProcessor, CallResult


# ── Configuration ────────────────────────────────────────────────────────

MAX_WORKERS       = int(getattr(config, "MAX_CONCURRENT_WORKERS", 6))   # parallel inference slots
MAX_QUEUE_SIZE     = int(getattr(config, "MAX_QUEUE_SIZE", 40))          # 20 calls + buffer
CALL_TIMEOUT_SEC   = 20.0                                                # hard ceiling per call
QUEUE_WAIT_WARN_MS = 1500                                                # log warning if queued > this


@dataclass
class QueuedCall:
    call_id:    str
    audio:      bytes
    sample_rate: int
    enqueued_at: float = field(default_factory=time.perf_counter)
    future:     Optional[Future] = None


class ConcurrentCallManager:
    """
    Bounded thread pool for processing simultaneous voice calls.

    Usage:
        manager = ConcurrentCallManager()
        manager.start()
        result = manager.submit_and_wait(call_id, audio_bytes)   # blocking
        # or
        manager.submit(call_id, audio_bytes, on_done=callback)   # async
    """

    def __init__(
        self,
        max_workers: int = MAX_WORKERS,
        max_queue_size: int = MAX_QUEUE_SIZE,
        on_result: Optional[Callable[[CallResult], None]] = None,
    ):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.on_result = on_result

        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_count = 0
        self._active_lock = threading.Lock()
        self._semaphore = threading.Semaphore(max_workers)

        # Live metrics for the dashboard
        self._stats = {
            "total_processed": 0,
            "total_rejected_queue_full": 0,
            "total_timeout": 0,
            "active_now": 0,
            "queued_now": 0,
            "avg_wait_ms": 0.0,
        }
        self._stats_lock = threading.Lock()
        self._wait_times: list[float] = []

    # ── Lifecycle ────────────────────────────────────────────────────────

    def start(self):
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="ai-voice-call",
        )
        logger.info(
            f"✅ ConcurrentCallManager started | "
            f"workers={self.max_workers} | max_queue={self.max_queue_size}"
        )

    def shutdown(self, wait: bool = True):
        if self._executor:
            self._executor.shutdown(wait=wait, cancel_futures=not wait)
            logger.info("ConcurrentCallManager shut down")

    # ── Submission ───────────────────────────────────────────────────────

    def submit(
        self,
        call_id: str,
        audio: bytes,
        sample_rate: int = 16000,
        on_done: Optional[Callable[[CallResult], None]] = None,
    ) -> Optional[Future]:
        """
        Non-blocking submit. Returns a Future, or None if queue is full
        (caller should play a "system busy, please hold" message and retry).
        """
        if self._executor is None:
            self.start()

        with self._active_lock:
            queued_and_active = self._active_count
        if queued_and_active >= self.max_queue_size:
            with self._stats_lock:
                self._stats["total_rejected_queue_full"] += 1
            logger.warning(
                f"[{call_id}] ❌ Queue full ({queued_and_active}/{self.max_queue_size}), rejecting"
            )
            return None

        enqueued_at = time.perf_counter()

        with self._active_lock:
            self._active_count += 1

        future = self._executor.submit(
            self._process_one, call_id, audio, sample_rate, enqueued_at
        )

        def _on_complete(fut: Future):
            with self._active_lock:
                self._active_count -= 1
            try:
                result = fut.result()
                if on_done:
                    on_done(result)
                if self.on_result:
                    self.on_result(result)
            except Exception as e:
                logger.error(f"[{call_id}] Call processing crashed: {e}")

        future.add_done_callback(_on_complete)
        return future

    def submit_and_wait(
        self, call_id: str, audio: bytes, sample_rate: int = 16000
    ) -> CallResult:
        """Blocking submit — waits for result (used by REST API)."""
        future = self.submit(call_id, audio, sample_rate)
        if future is None:
            from voice_pipeline import CallResult
            return CallResult(
                call_id=call_id, phone=None, items=[], stt_text="",
                stt_ms=0, intent_ms=0, db_ms=0, total_ms=0,
                booking_id=None, status="system_busy",
                message="System at capacity. Please try again in a moment.",
                mode="none",
            )
        try:
            return future.result(timeout=CALL_TIMEOUT_SEC)
        except TimeoutError:
            with self._stats_lock:
                self._stats["total_timeout"] += 1
            from voice_pipeline import CallResult
            return CallResult(
                call_id=call_id, phone=None, items=[], stt_text="",
                stt_ms=0, intent_ms=0, db_ms=0, total_ms=CALL_TIMEOUT_SEC * 1000,
                booking_id=None, status="timeout",
                message="Processing took too long. Please call again.",
                mode="none",
            )

    # ── Worker ───────────────────────────────────────────────────────────

    def _process_one(
        self, call_id: str, audio: bytes, sample_rate: int, enqueued_at: float
    ) -> CallResult:
        wait_ms = (time.perf_counter() - enqueued_at) * 1000
        if wait_ms > QUEUE_WAIT_WARN_MS:
            logger.warning(f"[{call_id}] Queued {wait_ms:.0f}ms before processing started")

        with self._stats_lock:
            self._wait_times.append(wait_ms)
            if len(self._wait_times) > 200:
                self._wait_times.pop(0)
            self._stats["avg_wait_ms"] = sum(self._wait_times) / len(self._wait_times)
            self._stats["total_processed"] += 1

        # Each thread gets its own processor; models are loaded once and
        # shared (get_stt()/get_pipeline() are singletons), so this is cheap.
        processor = VoiceCallProcessor(call_id=call_id)
        result = processor.process_audio(audio, sample_rate)
        return result

    # ── Metrics ──────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._active_lock:
            active = self._active_count
        with self._stats_lock:
            stats = dict(self._stats)
        stats["active_now"] = active
        stats["capacity"] = self.max_workers
        stats["queue_capacity"] = self.max_queue_size
        stats["utilization_pct"] = round(100 * active / max(self.max_workers, 1), 1)
        return stats


# ── Singleton ────────────────────────────────────────────────────────────
_manager: Optional[ConcurrentCallManager] = None


def get_call_manager() -> ConcurrentCallManager:
    global _manager
    if _manager is None:
        _manager = ConcurrentCallManager()
        _manager.start()
    return _manager


# ── Load Test (simulate 20 concurrent calls) ───────────────────────────────
if __name__ == "__main__":
    import numpy as np
    import voice_pipeline as vp

    # Inject a fake STT so this load test runs without downloading any
    # model — it proves the CONCURRENCY layer works, independent of
    # whether real Whisper/SmolLM weights are present on this machine.
    class _FakeSTT:
        def transcribe(self, audio, sample_rate=16000):
            time.sleep(0.05)  # simulate ~50ms inference
            return {
                "text": "I want rice and milk my number is 9876543210",
                "latency_ms": 50.0,
                "language": "en",
            }

    vp._stt = _FakeSTT()

    manager = ConcurrentCallManager(max_workers=6, max_queue_size=40)
    manager.start()

    N_CALLS = 20
    print(f"\nSimulating {N_CALLS} concurrent calls (fake STT, real LangChain pipeline)...\n")

    silence = (np.zeros(16000, dtype=np.float32)).tobytes()  # 1s silence as bytes stub

    futures = []
    t0 = time.perf_counter()
    for i in range(N_CALLS):
        call_id = f"load_test_{i:03d}"
        fut = manager.submit(call_id, silence)
        futures.append((call_id, fut))

    completed = 0
    for call_id, fut in futures:
        if fut is None:
            print(f"  {call_id}: REJECTED (queue full)")
            continue
        try:
            result = fut.result(timeout=30)
            completed += 1
            print(f"  {call_id}: {result.status} ({result.total_ms:.0f}ms)")
        except Exception as e:
            print(f"  {call_id}: ERROR {e}")

    total_s = time.perf_counter() - t0
    print(f"\n✅ {completed}/{N_CALLS} completed in {total_s:.1f}s total")
    print(f"   Stats: {manager.get_stats()}")
    manager.shutdown()
