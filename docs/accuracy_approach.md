# Accuracy Approach
## Closing the Gap to Large-Model Accuracy on CPU-Only Hardware

### The honest constraint

A 335-360M parameter model run on CPU is not going to match a frontier hosted model's
raw language understanding in a single forward pass. The brief explicitly rules out
GPU-hungry models, so the right question isn't "how do we get a bigger model" — it's
"how do we get reliable structured output from a small one." That's what this pipeline
is built around.

### Four techniques, stacked

**1. Chain-of-thought prompting**
Small models skip reasoning steps when asked to jump straight to an answer. The prompt
in `advanced_pipeline.py` forces the model to first restate what it heard in plain
language, *then* extract the structured fields. This single change recovers a
meaningful chunk of accuracy on instruction-following tasks for small models, because
it gives the model "room" to work out the answer instead of pattern-matching blindly.

**2. Few-shot examples in-context**
Four diverse examples (clean English, Hindi-English code-switching, missing phone,
missing items) are baked directly into the prompt. This imitates what instruction
tuning gives a large hosted model, at inference time, for free — at a cost of about
150 extra prompt tokens, still comfortably under a second on CPU with a 512-768 token
context window.

**3. Self-consistency voting**
The model is run twice per call — once near-deterministic (temperature 0.05), once
with more variation (temperature 0.5). If both passes agree on the phone number,
confidence is high. If they disagree, that's a signal the transcript was ambiguous,
and the system falls back to the regex extractor rather than trusting a single
uncertain guess.

**4. Ensemble cross-check against a deterministic extractor**
Phone numbers are a closed, well-defined format (10 digits, starts 6-9). A regex/
keyword extractor (`FallbackParser`) runs in parallel and is *more* reliable than an
LLM for this specific field, because it can't hallucinate a digit. The voting logic in
`HighAccuracyPipeline._vote_phone()` treats agreement between the LLM and the regex
extractor as the highest-confidence signal, and defers to the regex result whenever
they disagree. For items — open vocabulary, harder to enumerate exhaustively in
regex — the LLM result is trusted as primary, with regex output merged in to fill gaps.

### What happens when confidence is still low

The system does not silently guess. `EnsembleResult.needs_clarification` is set to
`True`, and `clarification_target` tells the calling code whether to ask the customer
to repeat their phone number or their order — mirroring how a human staff member would
ask "sorry, can you repeat that?" rather than mis-recording an order.

### Measuring this honestly

This is **not** a claim of parity with a frontier model on open-ended reasoning. It is
a claim that, for the narrow, well-defined task this system performs — extract a phone
number and an item list from short, spoken Indian-English/Hindi/Tamil-English
sentences — the combination of structured prompting and ensemble voting gets a CPU-only
335-360M model's *reliability on this specific task* close to what a much larger model
would give you, by spending a bit more inference time per call (2 LLM passes instead
of 1, plus a cheap regex pass) rather than more parameters.

### Fine-tuning closes the remaining gap

`fine_tune_smollm.py` LoRA-tunes the base model on `training_data/samples.json` /
`samples_augmented.json` (1000+ examples, expandable via `augment_data.py`), which
further narrows the gap for this system's specific domain (Indian grocery/retail
ordering) beyond what prompting alone achieves on the un-tuned base model.
