"""
quantize_model.py — Convert fine-tuned SmolLM → GGUF Q4_K_M

Steps:
  1. Merge LoRA weights into base model
  2. Convert to GGUF (FP16 intermediate)
  3. Quantize to Q4_K_M (4-bit, ~200MB)

Run AFTER fine_tune_smollm.py:
  python quantize_model.py

Requirements:
  - llama.cpp built from source (or installed via pip install llama-cpp-python)
  - fine-tuned model at models/smollm-finetuned/
"""
import os
import subprocess
import sys
from pathlib import Path

from loguru import logger
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer

# Paths
FINETUNED_DIR = Path("models/smollm-finetuned")
MERGED_DIR    = Path("models/smollm-merged")
GGUF_F16      = Path("models/smollm-finetuned.f16.gguf")
GGUF_Q4       = Path("models/smollm-finetuned.Q4_K_M.gguf")
LLAMA_CPP_DIR = Path("llama.cpp")


def step1_merge_lora():
    """Merge LoRA adapter weights into base model."""
    logger.info("[1/3] Merging LoRA weights into base model...")

    if not FINETUNED_DIR.exists():
        logger.error(f"Fine-tuned model not found at {FINETUNED_DIR}")
        logger.error("Run: python fine_tune_smollm.py first")
        sys.exit(1)

    MERGED_DIR.mkdir(parents=True, exist_ok=True)

    import torch
    model = AutoPeftModelForCausalLM.from_pretrained(
        str(FINETUNED_DIR),
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
    )
    merged = model.merge_and_unload()
    merged.save_pretrained(str(MERGED_DIR))

    tokenizer = AutoTokenizer.from_pretrained(str(FINETUNED_DIR))
    tokenizer.save_pretrained(str(MERGED_DIR))

    logger.info(f"✅ Merged model saved: {MERGED_DIR}")


def step2_install_llama_cpp():
    """Clone and build llama.cpp if not present."""
    if LLAMA_CPP_DIR.exists() and (LLAMA_CPP_DIR / "build" / "bin" / "llama-quantize").exists():
        logger.info("[2/3] llama.cpp already built, skipping")
        return

    logger.info("[2/3] Setting up llama.cpp...")

    # Try pip install first (easier)
    try:
        import llama_cpp
        logger.info("llama-cpp-python already installed via pip")
        return
    except ImportError:
        pass

    # Clone and build from source
    if not LLAMA_CPP_DIR.exists():
        subprocess.run(
            ["git", "clone", "--depth=1", "https://github.com/ggerganov/llama.cpp"],
            check=True,
        )

    build_dir = LLAMA_CPP_DIR / "build"
    build_dir.mkdir(exist_ok=True)

    subprocess.run(
        ["cmake", "..", "-DLLAMA_AVX2=ON", "-DCMAKE_BUILD_TYPE=Release"],
        cwd=str(build_dir), check=True,
    )
    subprocess.run(
        ["cmake", "--build", ".", "--config", "Release", f"-j{os.cpu_count()}"],
        cwd=str(build_dir), check=True,
    )
    logger.info("✅ llama.cpp built")


def step3_convert_and_quantize():
    """Convert merged model to GGUF then quantize to Q4_K_M."""
    logger.info("[3/3] Converting and quantizing...")

    if not MERGED_DIR.exists():
        logger.error("Merged model not found. Run step1 first.")
        sys.exit(1)

    # Find conversion script
    convert_script = None
    candidates = [
        LLAMA_CPP_DIR / "convert_hf_to_gguf.py",
        LLAMA_CPP_DIR / "convert.py",
        Path("llama.cpp/convert_hf_to_gguf.py"),
    ]
    for c in candidates:
        if c.exists():
            convert_script = c
            break

    if convert_script is None:
        # Try using llama-cpp-python's convert utility
        logger.warning("llama.cpp convert script not found.")
        logger.warning("Install llama.cpp: git clone https://github.com/ggerganov/llama.cpp")
        logger.warning(
            "Alternative: use HuggingFace GGUF converter:\n"
            "  pip install gguf\n"
            f"  python -c \"from llama_cpp import llama_cpp; "
            f"llama_cpp.llama_model_save_file(...)\""
        )
        return

    # Step 3a: Convert to GGUF FP16
    logger.info(f"Converting {MERGED_DIR} → {GGUF_F16}...")
    subprocess.run(
        [sys.executable, str(convert_script),
         str(MERGED_DIR),
         "--outfile", str(GGUF_F16),
         "--outtype", "f16"],
        check=True,
    )

    # Step 3b: Quantize to Q4_K_M
    quantize_bin = LLAMA_CPP_DIR / "build" / "bin" / "llama-quantize"
    if not quantize_bin.exists():
        quantize_bin = LLAMA_CPP_DIR / "llama-quantize"  # Old path

    if quantize_bin.exists():
        logger.info(f"Quantizing {GGUF_F16} → {GGUF_Q4}...")
        subprocess.run(
            [str(quantize_bin), str(GGUF_F16), str(GGUF_Q4), "Q4_K_M"],
            check=True,
        )
        size_mb = GGUF_Q4.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Quantized model: {GGUF_Q4} ({size_mb:.0f}MB)")

        # Cleanup intermediate
        GGUF_F16.unlink(missing_ok=True)
        logger.info(f"Cleaned up intermediate: {GGUF_F16}")
    else:
        logger.warning(
            f"llama-quantize not found. You have the FP16 GGUF at {GGUF_F16}.\n"
            "Manually quantize with:\n"
            f"  ./llama.cpp/llama-quantize {GGUF_F16} {GGUF_Q4} Q4_K_M"
        )


def main():
    logger.info("=" * 60)
    logger.info("ai powered voice based 24.7 booking system — Model Quantization Pipeline")
    logger.info("Input : models/smollm-finetuned/ (LoRA fine-tuned)")
    logger.info("Output: models/smollm-finetuned.Q4_K_M.gguf")
    logger.info("=" * 60)

    step1_merge_lora()
    step2_install_llama_cpp()
    step3_convert_and_quantize()

    logger.info("")
    logger.info("🎉 Done! Update your .env:")
    logger.info(f"   SMOLLM_MODEL_PATH={GGUF_Q4}")


if __name__ == "__main__":
    main()
