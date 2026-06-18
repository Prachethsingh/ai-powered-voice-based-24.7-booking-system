"""
fine_tune_smollm.py — Fine-tune SmolLM 335M for Indian Voice Ordering

Method: LoRA (Low-Rank Adaptation) on CPU
- Does NOT require GPU
- ~2-4 hours on a modern CPU for 1000 samples
- Uses PEFT + TRL SFTTrainer
- Output: models/smollm-finetuned/ (HuggingFace format)
  Then run quantize_model.py to get .Q4_K_M.gguf

Run: python fine_tune_smollm.py
"""
import json
import os
import sys
from pathlib import Path

import torch
from datasets import Dataset
from loguru import logger
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
)
from trl import SFTTrainer

# ── Config ─────────────────────────────────────────────────────────────────
BASE_MODEL    = "HuggingFaceTB/SmolLM-360M-Instruct"   # 360M ≈ 335M
OUTPUT_DIR    = Path("models/smollm-finetuned")
GGUF_DIR      = Path("models")
DATASET_PATH  = Path("training_data/samples.json")
NUM_EPOCHS    = 3       # 3 epochs enough for intent extraction
BATCH_SIZE    = 2       # CPU: small batch
LR            = 2e-4
MAX_SEQ_LEN   = 256     # Short prompts only

# LoRA config (memory-efficient fine-tuning on CPU)
LORA_CONFIG = LoraConfig(
    r=8,                            # Rank
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type=TaskType.CAUSAL_LM,
)


# ── Dataset ────────────────────────────────────────────────────────────────

def load_dataset() -> Dataset:
    """Load training samples from JSON file."""
    if not DATASET_PATH.exists():
        logger.warning(f"Dataset not found at {DATASET_PATH}. Using built-in samples.")
        samples = _get_builtin_samples()
    else:
        with open(DATASET_PATH) as f:
            samples = json.load(f)
        logger.info(f"Loaded {len(samples)} training samples")

    # Format as instruction-following
    formatted = []
    for s in samples:
        text = (
            f"### Instruction:\n"
            f"Extract phone number and items from this voice message.\n\n"
            f"### Input:\n{s['input']}\n\n"
            f"### Response:\n{s['output']}"
        )
        formatted.append({"text": text})

    return Dataset.from_list(formatted)


def _get_builtin_samples() -> list:
    """100 built-in samples for quick testing (load samples.json for full 1000+)."""
    return [
        # English ordering patterns
        {"input": "I want 2 kilos of rice and one liter milk, my phone is 9876543210",
         "output": "PHONE:9876543210 ITEMS:rice 2kg,milk 1L"},
        {"input": "Please send me bread and eggs, number is 8765432109",
         "output": "PHONE:8765432109 ITEMS:bread,eggs"},
        {"input": "Order 5 kg wheat flour and 2 packets salt my number 7654321098",
         "output": "PHONE:7654321098 ITEMS:wheat flour 5kg,salt 2 packets"},
        {"input": "I need one dozen eggs and 500 grams butter contact 9123456789",
         "output": "PHONE:9123456789 ITEMS:eggs 1 dozen,butter 500g"},
        {"input": "Two liters cooking oil and one kilo sugar please, call nine eight seven six five four three two one zero",
         "output": "PHONE:9876543210 ITEMS:cooking oil 2L,sugar 1kg"},
        {"input": "Send me tomatoes onions and potatoes my mobile is 8234567890",
         "output": "PHONE:8234567890 ITEMS:tomatoes,onions,potatoes"},
        {"input": "I want to buy toothpaste and shampoo, phone number eight seven six five four three two one zero nine",
         "output": "PHONE:8765432109 ITEMS:toothpaste,shampoo"},
        {"input": "5 packets biscuits and 2 bottles water, number is 6543210987",
         "output": "PHONE:6543210987 ITEMS:biscuits 5 packets,water 2 bottles"},
        {"input": "Please book one kilo paneer and half liter curd, my number is 9988776655",
         "output": "PHONE:9988776655 ITEMS:paneer 1kg,curd 500ml"},
        {"input": "I need 3 kg basmati rice and 1 liter refined oil, call me at 9012345678",
         "output": "PHONE:9012345678 ITEMS:basmati rice 3kg,refined oil 1L"},
        # Mixed Hindi-English (code switching)
        {"input": "Ek kilo chawal aur do packet namak chahiye, number hai 9876543210",
         "output": "PHONE:9876543210 ITEMS:rice 1kg,salt 2 packets"},
        {"input": "Mujhe bread aur milk chahiye, mera number hai 8765432109",
         "output": "PHONE:8765432109 ITEMS:bread,milk"},
        {"input": "Teen kilo aata aur ek packet chai, phone 7654321098",
         "output": "PHONE:7654321098 ITEMS:wheat flour 3kg,tea 1 packet"},
        {"input": "Do litre tel aur ek kilo cheeni bhejo, number 9123456789",
         "output": "PHONE:9123456789 ITEMS:oil 2L,sugar 1kg"},
        {"input": "Paneer aur dahi order karna hai, mobile 8234567890",
         "output": "PHONE:8234567890 ITEMS:paneer,curd"},
        # Tamil-English mix patterns
        {"input": "Oru kilo arisi venum, en phone number 9876543210",
         "output": "PHONE:9876543210 ITEMS:rice 1kg"},
        {"input": "Rendu liter paal and bread venumi, number 8765432109",
         "output": "PHONE:8765432109 ITEMS:milk 2L,bread"},
        {"input": "Thakkali onion potatoes order panna number 7654321098",
         "output": "PHONE:7654321098 ITEMS:tomatoes,onions,potatoes"},
        # Noisy/informal speech
        {"input": "umm I want rice like 2 kg and also uh milk please number is 9876543210",
         "output": "PHONE:9876543210 ITEMS:rice 2kg,milk"},
        {"input": "ya so I need bread eggs and um butter my number nine eight seven six five",
         "output": "PHONE:UNKNOWN ITEMS:bread,eggs,butter"},
        {"input": "order please sugar one kilo and tea two packets nine eight seven six five four three two one zero",
         "output": "PHONE:9876543210 ITEMS:sugar 1kg,tea 2 packets"},
        # Spoken digit phone numbers
        {"input": "Send rice and dal, my number is nine eight seven six five four three two one zero",
         "output": "PHONE:9876543210 ITEMS:rice,dal"},
        {"input": "I want milk and curd, number eight seven six five four three two one zero nine",
         "output": "PHONE:8765432109 ITEMS:milk,curd"},
        # Retail products
        {"input": "I want to order 2 soaps and one shampoo bottle, number 9876543210",
         "output": "PHONE:9876543210 ITEMS:soap 2 pieces,shampoo 1 bottle"},
        {"input": "Send me toothpaste and a face wash, my phone 8765432109",
         "output": "PHONE:8765432109 ITEMS:toothpaste,face wash"},
        {"input": "I need washing powder 2 kg and dish soap, call 7654321098",
         "output": "PHONE:7654321098 ITEMS:washing powder 2kg,dish soap"},
        # Quantity variations
        {"input": "Half kilo ghee and one packet coffee, number 9876543210",
         "output": "PHONE:9876543210 ITEMS:ghee 500g,coffee 1 packet"},
        {"input": "Quarter kilo black pepper and 100 grams turmeric, phone 8765432109",
         "output": "PHONE:8765432109 ITEMS:black pepper 250g,turmeric 100g"},
        {"input": "Six eggs and a loaf of bread please, call me at 7654321098",
         "output": "PHONE:7654321098 ITEMS:eggs 6,bread 1 loaf"},
        # No phone (model should handle gracefully)
        {"input": "I want to order rice and milk",
         "output": "PHONE:UNKNOWN ITEMS:rice,milk"},
        {"input": "Send me eggs please",
         "output": "PHONE:UNKNOWN ITEMS:eggs"},
    ]


# ── Fine-Tuning ─────────────────────────────────────────────────────────────

def fine_tune():
    logger.info("=" * 60)
    logger.info("ai powered voice based 24.7 booking system — SmolLM Fine-Tuning")
    logger.info(f"Base model : {BASE_MODEL}")
    logger.info(f"Output     : {OUTPUT_DIR}")
    logger.info(f"Device     : CPU (no GPU required)")
    logger.info("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load tokenizer
    logger.info("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    tokenizer.pad_token = tokenizer.eos_token

    # Load base model (CPU, float32)
    logger.info("Loading base model (this may take a few minutes)...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float32,  # CPU: float32
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = False   # Required for gradient checkpointing

    # Apply LoRA
    logger.info("Applying LoRA adapter...")
    model = get_peft_model(model, LORA_CONFIG)
    model.print_trainable_parameters()

    # Load dataset
    logger.info("Loading training dataset...")
    dataset = load_dataset()
    logger.info(f"Dataset size: {len(dataset)} samples")

    # Training arguments (CPU-optimized)
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=4,
        learning_rate=LR,
        fp16=False,          # CPU: no FP16
        bf16=False,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        report_to="none",    # No wandb/tensorboard
        dataloader_num_workers=0,
        no_cuda=True,        # Force CPU
        optim="adamw_torch",
    )

    # SFT Trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        args=training_args,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LEN,
        packing=False,
    )

    # Train
    logger.info(f"Starting training ({NUM_EPOCHS} epochs on CPU)...")
    trainer.train()

    # Save model + tokenizer
    logger.info(f"Saving model to {OUTPUT_DIR}...")
    trainer.model.save_pretrained(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))

    logger.info("✅ Fine-tuning complete!")
    logger.info(f"Next step: python quantize_model.py")
    logger.info(f"  Input : {OUTPUT_DIR}")
    logger.info(f"  Output: {GGUF_DIR}/smollm-finetuned.Q4_K_M.gguf")
    return str(OUTPUT_DIR)


if __name__ == "__main__":
    fine_tune()
