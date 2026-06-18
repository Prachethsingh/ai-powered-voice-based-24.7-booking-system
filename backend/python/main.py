"""
main.py — Python AI Service Entry Point (FastAPI)

Exposes REST API consumed by the Node.js backend:
  POST /process-audio   — Transcribe + extract intent
  POST /process-text    — Text-only intent extraction (for testing)
  GET  /stats           — DB stats for dashboard
  GET  /health          — Health check

Run: uvicorn main:app --host 0.0.0.0 --port 8001 --workers 1
"""
import time
import base64
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

import config
from security import api_rate_limiter, ws_jwt
from voice_pipeline import VoiceCallProcessor
from langchain_pipeline import get_pipeline
from concurrent_call_manager import get_call_manager
from secure_db import db
from audit_logger import audit

# ── App Setup ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="ai powered voice based 24.7 booking system — AI Service",
    description="CPU-only voice ordering AI pipeline",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Rate Limiting Dependency ───────────────────────────────────────────────

async def check_rate_limit(request: Request):
    client_ip = request.client.host
    if not api_rate_limiter.is_allowed(client_ip):
        audit.auth_failed(client_ip, "rate_limit_exceeded")
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return client_ip


# ── Request/Response Models ───────────────────────────────────────────────

class AudioRequest(BaseModel):
    call_id: str
    audio_b64: str            # Base64-encoded raw PCM bytes
    sample_rate: int = 16000


class TextRequest(BaseModel):
    call_id: str
    text: str


class ProcessResponse(BaseModel):
    call_id:    str
    phone:      str | None
    items:      list[str]
    status:     str
    message:    str
    stt_text:   str
    mode:       str
    latency:    dict          # {stt_ms, intent_ms, db_ms, total_ms}
    booking_id: int | None


# ── Startup ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Warm up models on startup (avoid cold-start latency on first call)."""
    logger.info("🚀 ai powered voice based 24.7 booking system AI Service starting...")
    Path("logs").mkdir(exist_ok=True)

    # Warm up LangChain pipeline
    pipeline = get_pipeline()
    logger.info("✅ LangChain pipeline ready")

    # Start concurrent call manager (handles 10-20 simultaneous calls)
    manager = get_call_manager()
    logger.info(
        f"✅ Concurrency layer ready: {manager.max_workers} workers, "
        f"queue capacity {manager.max_queue_size}"
    )

    # Verify DB
    stats = db.get_stats()
    logger.info(f"✅ Database ready: {stats['total_bookings']} bookings")

    logger.info(f"🌐 Listening on port {config.PYTHON_API_PORT}")


@app.on_event("shutdown")
async def shutdown():
    get_call_manager().shutdown(wait=True)


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ai-powered-voice-booking",
        "timestamp": time.time(),
    }


@app.get("/stats")
async def get_stats(_: str = Depends(check_rate_limit)):
    return db.get_stats()


@app.get("/bookings")
async def get_bookings(limit: int = 20, _: str = Depends(check_rate_limit)):
    return {"bookings": db.get_recent_bookings(limit=min(limit, 100))}


@app.post("/process-text", response_model=ProcessResponse)
async def process_text(req: TextRequest, _: str = Depends(check_rate_limit)):
    """
    Text-only processing (no STT). Used for:
    - Testing the intent extraction pipeline
    - When caller input is already transcribed
    """
    pipeline = get_pipeline()
    intent   = pipeline.process(req.text, req.call_id)

    phone = intent.get("phone")
    items = intent.get("items", [])

    if phone and items:
        db_result = db.store_booking(phone, items, req.call_id)
    else:
        db_result = {"success": False, "reason": "incomplete_intent"}

    status = "success" if db_result.get("success") else db_result.get("reason", "error")
    return ProcessResponse(
        call_id=req.call_id,
        phone=phone,
        items=items,
        status=status,
        message=db_result.get("message", ""),
        stt_text=req.text,
        mode=intent.get("mode", "unknown"),
        latency={"intent_ms": intent.get("latency_ms", 0), "total_ms": intent.get("latency_ms", 0)},
        booking_id=db_result.get("booking_id"),
    )


@app.post("/process-audio", response_model=ProcessResponse)
async def process_audio(req: AudioRequest, _: str = Depends(check_rate_limit)):
    """
    Full audio processing pipeline: STT → intent → DB.
    Audio should be base64-encoded raw PCM (16-bit mono, 16kHz).

    Routed through the concurrent call manager so that 10-20 callers
    hitting this endpoint at once are queued and processed by a
    bounded worker pool instead of overloading the CPU.
    """
    try:
        audio_bytes = base64.b64decode(req.audio_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio")

    manager = get_call_manager()
    result = manager.submit_and_wait(req.call_id, audio_bytes, req.sample_rate)

    if result.status == "system_busy":
        raise HTTPException(status_code=503, detail=result.message)

    return ProcessResponse(
        call_id=result.call_id,
        phone=result.phone,
        items=result.items,
        status=result.status,
        message=result.message,
        stt_text=result.stt_text,
        mode=result.mode,
        latency={
            "stt_ms":    result.stt_ms,
            "intent_ms": result.intent_ms,
            "db_ms":     result.db_ms,
            "total_ms":  result.total_ms,
        },
        booking_id=result.booking_id,
    )


@app.get("/capacity")
async def get_capacity():
    """Live concurrency stats for the dashboard (active calls, queue, etc.)."""
    return get_call_manager().get_stats()


@app.post("/export/csv")
async def export_csv(_: str = Depends(check_rate_limit)):
    """Phase 7: export all bookings to CSV for ERP/POS/legacy systems."""
    from external_integration import external_integration
    bookings = db.get_recent_bookings(limit=1000)
    path = external_integration.export_csv(bookings)
    return {"success": True, "path": path, "count": len(bookings)}


@app.post("/export/json")
async def export_json(_: str = Depends(check_rate_limit)):
    """Phase 7: export all bookings to JSON for custom integrations."""
    from external_integration import external_integration
    bookings = db.get_recent_bookings(limit=1000)
    path = external_integration.export_json(bookings)
    return {"success": True, "path": path, "count": len(bookings)}


@app.put("/bookings/{booking_id}/status")
async def update_status(
    booking_id: int,
    body: dict,
    _: str = Depends(check_rate_limit),
):
    status = body.get("status", "")
    success = db.update_booking_status(booking_id, status)
    if not success:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    return {"success": True, "booking_id": booking_id, "status": status}


# ── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.PYTHON_API_PORT,
        workers=1,       # Single worker for model sharing
        log_level=config.LOG_LEVEL.lower(),
    )
