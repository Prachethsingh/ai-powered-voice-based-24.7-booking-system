# models/

Model weight files (.gguf) go here. They are NOT bundled in this zip because:
- They're large binary files (75MB Whisper + 200MB SmolLM = ~275MB)
- They're publicly downloadable, versioned artifacts — bundling them would
  bloat the repo and make updates painful

## Get them

```bash
./download_models.sh
```

This downloads:
- `tiny.en.Q4_K_M.gguf` (~75MB) — Whisper English speech-to-text, CPU-only
- `smollm-335m-finetuned.Q4_K_M.gguf` (~200MB) — base SmolLM for intent extraction

## Want better accuracy on Indian grocery/retail vocabulary?

Fine-tune on the included training data instead of using the raw base model:

```bash
python ../training_data/augment_data.py        # 100 -> 1000+ samples
python ../backend/python/fine_tune_smollm.py     # LoRA fine-tune, CPU, 2-4 hrs
python ../backend/python/quantize_model.py       # -> smollm-finetuned.Q4_K_M.gguf
```

Then point `.env`'s `SMOLLM_MODEL_PATH` at the fine-tuned file.

## Running without any model at all

The system still works without downloading anything — `langchain_pipeline.py`
and `advanced_pipeline.py` both fall back to a pure regex/keyword extractor
when no `.gguf` file is found at the configured path. This is what
`call_simulator.py` uses by default for fast offline testing.
