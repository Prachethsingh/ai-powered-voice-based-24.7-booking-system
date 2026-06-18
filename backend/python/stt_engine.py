"""
stt_engine.py — Whisper STT Engine (CPU-only)

Uses whisper.cpp via ctypes binding (fastest CPU STT).
Falls back to openai-whisper Python if whisper.cpp not available.

Target: <0.5s for 5-second audio clip with tiny.en Q4_K_M (75MB)
"""
import io
import os
import struct
import time
import wave
from pathlib import Path
from typing import Optional, Union

import numpy as np
from loguru import logger

import config


class WhisperSTT:
    """
    CPU-only Whisper STT wrapper.
    
    Automatically uses whispercpp if available, falls back to
    openai-whisper Python (slower but easier to install).
    """

    def __init__(self, model_path: str = config.WHISPER_MODEL_PATH):
        self.model_path = Path(model_path)
        self.language = config.WHISPER_LANGUAGE
        self._model = None
        self._backend = None
        self._load_model()

    def _load_model(self):
        """Load Whisper model. Try whispercpp first, then openai-whisper."""
        if not self.model_path.exists():
            logger.warning(
                f"Whisper model not found at {self.model_path}. "
                f"Run: ./models/download_models.sh"
            )

        # Try whispercpp (fastest)
        try:
            from whispercpp import Whisper
            self._model = Whisper.from_pretrained(
                str(self.model_path),
                n_threads=config.LLM_N_THREADS,
            )
            self._backend = "whispercpp"
            logger.info(f"✅ Whisper loaded (whispercpp backend): {self.model_path.name}")
            return
        except ImportError:
            logger.debug("whispercpp not installed, trying openai-whisper")

        # Fallback: openai-whisper
        try:
            import whisper
            # For openai-whisper, model_path is the model name or file path
            model_name = "tiny.en" if "tiny.en" in str(self.model_path) else "tiny"
            self._model = whisper.load_model(model_name, device="cpu")
            self._backend = "openai-whisper"
            logger.info(f"✅ Whisper loaded (openai-whisper backend): {model_name}")
            return
        except ImportError:
            pass

        raise RuntimeError(
            "No Whisper backend found. Install one of:\n"
            "  pip install whispercpp        # (faster, recommended)\n"
            "  pip install openai-whisper    # (fallback)"
        )

    def transcribe(
        self,
        audio: Union[bytes, np.ndarray, str],
        sample_rate: int = 16000,
    ) -> dict:
        """
        Transcribe audio to text.

        Args:
            audio: Raw PCM bytes, numpy float32 array, or file path
            sample_rate: Sample rate (Whisper needs 16kHz)

        Returns:
            {"text": "...", "latency_ms": 123.4, "language": "en"}
        """
        t0 = time.perf_counter()

        # Convert input to numpy float32
        audio_array = self._prepare_audio(audio, sample_rate)

        # Transcribe
        if self._backend == "whispercpp":
            text = self._transcribe_whispercpp(audio_array)
        else:
            text = self._transcribe_openai(audio_array)

        latency_ms = (time.perf_counter() - t0) * 1000
        text = text.strip()

        logger.debug(f"STT ({latency_ms:.0f}ms): '{text[:80]}'")
        return {
            "text": text,
            "latency_ms": latency_ms,
            "language": self.language,
        }

    def _transcribe_whispercpp(self, audio: np.ndarray) -> str:
        result = self._model.transcribe(audio)
        return result.get("text", "")

    def _transcribe_openai(self, audio: np.ndarray) -> str:
        result = self._model.transcribe(
            audio,
            language=self.language if self.language != "auto" else None,
            fp16=False,   # CPU: must use FP32
            beam_size=1,  # Greedy — faster on CPU
        )
        return result.get("text", "")

    def _prepare_audio(
        self, audio: Union[bytes, np.ndarray, str], sample_rate: int
    ) -> np.ndarray:
        """Convert any audio input to float32 numpy array at 16kHz."""
        if isinstance(audio, str):
            # File path
            import soundfile as sf
            data, sr = sf.read(audio, dtype="float32")
            if sr != 16000:
                data = self._resample(data, sr, 16000)
            return data

        if isinstance(audio, np.ndarray):
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            return audio

        if isinstance(audio, bytes):
            # Raw PCM bytes (16-bit signed int, mono)
            audio_int16 = np.frombuffer(audio, dtype=np.int16)
            audio_f32 = audio_int16.astype(np.float32) / 32768.0
            if sample_rate != 16000:
                audio_f32 = self._resample(audio_f32, sample_rate, 16000)
            return audio_f32

        raise TypeError(f"Unsupported audio type: {type(audio)}")

    @staticmethod
    def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Simple linear interpolation resample."""
        if orig_sr == target_sr:
            return audio
        target_length = int(len(audio) * target_sr / orig_sr)
        indices = np.linspace(0, len(audio) - 1, target_length)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    def transcribe_demo(self, text_override: str = "") -> dict:
        """Demo mode: skip STT, return hardcoded text (for testing without model)."""
        demo_text = text_override or (
            "I want 2 kilos of rice and one liter milk, "
            "my phone number is 9876543210"
        )
        return {"text": demo_text, "latency_ms": 0.0, "language": "en", "demo": True}
