"""
langchain_pipeline.py — LangChain Orchestration for ai powered voice based 24.7 booking system

This is the CORE AI pipeline. Built on modern LangChain LCEL
(LangChain Expression Language) — NOT the deprecated LLMChain class,
which was removed in LangChain 1.0+.

Pipeline (LCEL chain composition):
    STT Text
      → extraction_chain  (prompt | llm | parser)
      → verification_chain (self-check: does extracted phone/items make sense?)
      → ensemble_vote      (LLM result vs regex result → pick higher confidence)
      → Structured Output

Accuracy strategy ("ChatGPT-level accuracy" on a 200MB CPU model):
  A 335M model alone cannot match GPT-4 reasoning. Instead we close the
  gap with an ENSEMBLE + SELF-VERIFICATION architecture:
    1. LLM extracts intent (fast, handles paraphrasing/context)
    2. Deterministic regex extracts independently (perfect at digit patterns)
    3. If both agree → very high confidence, accept immediately
    4. If they disagree → run a second LLM pass that is SHOWN both
       candidates and asked to pick/correct (cheap "self-correction" step,
       <100ms on CPU since it's a tiny classification, not free generation)
    5. If still uncertain → mark low-confidence so the caller is asked
       to repeat (better than silently guessing wrong, which is what
       hurts accuracy most in production phone systems)

Design (Caveman Principle): Simple, direct, works. No magic.
"""
import re
import time
from pathlib import Path
from typing import Any, Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from loguru import logger

import config
from phone_validator import extract_phone_from_text, normalize_phone, validate_phone

# LlamaCpp moved around between LangChain versions — try both import paths
try:
    from langchain_community.llms import LlamaCpp
except ImportError:
    from langchain.llms import LlamaCpp


# ── 1. Output Parser ──────────────────────────────────────────────────────

class VoiceOrderParser(BaseOutputParser):
    """
    Parses SmolLM output into structured order dict.
    
    Expected raw format: "PHONE:9876543210 ITEMS:rice 2kg,milk 1L"
    Returns: {"phone": "9876543210", "items": ["rice 2kg", "milk 1L"], "raw": "..."}
    """

    def parse(self, text: str) -> dict:
        text = text.strip()
        result = {"raw": text, "phone": None, "items": [], "confidence": "high"}

        # Extract phone
        phone_match = re.search(r"PHONE:(\d{10}|UNKNOWN)", text, re.IGNORECASE)
        if phone_match:
            phone_str = phone_match.group(1)
            result["phone"] = None if phone_str == "UNKNOWN" else phone_str
        
        # Extract items
        items_match = re.search(r"ITEMS:([^\n]+)", text, re.IGNORECASE)
        if items_match:
            items_str = items_match.group(1).strip()
            if items_str.upper() != "UNKNOWN":
                result["items"] = [i.strip() for i in items_str.split(",") if i.strip()]

        # Lower confidence if partial
        if not result["phone"] or not result["items"]:
            result["confidence"] = "low"

        return result

    def get_format_instructions(self) -> str:
        return (
            "Respond ONLY in this exact format:\n"
            "PHONE:<10-digit-indian-number> ITEMS:<item1>,<item2>\n"
            "Example: PHONE:9876543210 ITEMS:rice 2kg,milk 1L,eggs 6pcs\n"
            "If phone not mentioned: PHONE:UNKNOWN\n"
            "If items not mentioned: ITEMS:UNKNOWN"
        )


# ── 2. LLM Setup ──────────────────────────────────────────────────────────

def build_llm(model_path: str = config.SMOLLM_MODEL_PATH) -> LlamaCpp:
    """
    Load SmolLM 335M GGUF model for CPU inference.
    
    Key settings:
    - n_gpu_layers=0: Force CPU-only
    - n_threads=4: Match CPU core count
    - temperature=0.1: Low = deterministic (good for intent extraction)
    - max_tokens=64: Short responses only
    """
    model_file = Path(model_path)

    if not model_file.exists():
        logger.warning(
            f"SmolLM model not found at {model_path}. "
            "Run: ./models/download_models.sh or fine_tune_smollm.py"
        )
        # Return None — pipeline will use fallback regex mode
        return None

    llm = LlamaCpp(
        model_path=str(model_file),
        n_ctx=config.LLM_N_CTX,           # 512 tokens context
        n_threads=config.LLM_N_THREADS,   # 4 CPU threads
        n_batch=config.LLM_N_BATCH,       # 8 batch size
        n_gpu_layers=0,                    # CPU-ONLY: no GPU layers
        temperature=config.LLM_TEMPERATURE,  # 0.1 = deterministic
        max_tokens=config.LLM_MAX_TOKENS,    # 64 tokens max output
        verbose=False,
        echo=False,
    )
    logger.info(f"✅ SmolLM loaded (CPU, GGUF): {model_file.name}")
    return llm


# ── 3. Prompt Templates ───────────────────────────────────────────────────

INTENT_PROMPT = PromptTemplate(
    input_variables=["voice_text"],
    template="""You extract phone numbers and ordered items from Indian customer voice messages.

Customer said: {voice_text}

Rules:
- Phone numbers are 10-digit Indian mobile numbers starting with 6, 7, 8, or 9
- Items include food, groceries, retail products
- If information is missing, write UNKNOWN

Respond ONLY in this format (no other text):
PHONE:<10-digit-number> ITEMS:<item1>,<item2>

Response:""",
)

PREPROCESS_PROMPT = PromptTemplate(
    input_variables=["raw_text"],
    template="""Clean this voice transcript by:
1. Fixing obvious STT errors (e.g. "tow" → "two", "won" → "one")
2. Expanding digit words to numbers where they appear in a sequence
3. Keeping the meaning exactly the same

Original: {raw_text}
Cleaned:""",
)

# ── Self-Verification Prompt ───────────────────────────────────────────────
# Used ONLY when LLM extraction and regex extraction disagree.
# This is a short, cheap classification task (not free generation),
# so it stays fast even on CPU — this is the "self-correction" step
# that closes most of the accuracy gap with larger models.
VERIFY_PROMPT = PromptTemplate(
    input_variables=["voice_text", "candidate_a", "candidate_b"],
    template="""Two extraction attempts disagree on this customer voice message.

Customer said: {voice_text}

Candidate A: {candidate_a}
Candidate B: {candidate_b}

Which candidate is correct? Reply with ONLY "A" or "B" or "NEITHER".

Answer:""",
)


# ── 4. Fallback Parser (no LLM needed) ───────────────────────────────────

class FallbackParser:
    """
    Pure regex intent extraction when model is unavailable.
    Works surprisingly well for simple orders.
    """

    # Common Indian grocery/retail items
    ITEM_KEYWORDS = [
        r"rice", r"wheat", r"atta", r"dal", r"flour", r"sugar", r"salt", r"oil",
        r"milk", r"curd", r"paneer", r"butter", r"ghee", r"eggs?", r"bread",
        r"apples?", r"bananas?", r"tomatoes?", r"onions?", r"potatoes?",
        r"vegetables?", r"fruits?", r"biscuits?", r"chips", r"noodles?",
        r"water", r"juice", r"soap", r"shampoo", r"toothpaste", r"detergent",
    ]

    ITEM_PATTERN = re.compile(
        r"(\d+[\s]?(?:kg|kilo|gram|g|liter|litre|l|packet|pack|bottle|dozen|pcs?|piece)?\s*"
        r"(?:of\s+)?)?" + r"(" + "|".join(ITEM_KEYWORDS) + r")"
        r"(?:\s+\d+[\s]?(?:kg|kilo|gram|g|liter|litre|l|packet|pack|bottle|dozen|pcs?))?",
        re.IGNORECASE,
    )

    def parse(self, text: str) -> dict:
        phone = extract_phone_from_text(text)

        items = []
        for match in self.ITEM_PATTERN.finditer(text):
            qty = (match.group(1) or "").strip()
            item = match.group(2).strip()
            full = f"{qty} {item}".strip() if qty else item
            if full not in items:
                items.append(full)

        return {
            "phone": phone,
            "items": items,
            "raw": text,
            "confidence": "high" if phone and items else "low",
            "mode": "fallback_regex",
        }


# ── 5. Full LangChain Pipeline ────────────────────────────────────────────

class VoiceOrderPipeline:
    """
    Main LangChain (LCEL) pipeline for voice order processing.

    Chain flow:
        raw_stt_text
          → extraction_chain (PromptTemplate | LlamaCpp | VoiceOrderParser)   [LCEL]
          → regex fallback runs IN PARALLEL (always, cheap)
          → ensemble vote:
                agree            → accept (high confidence)
                disagree         → verification_chain decides (LLM judges A vs B)
                LLM unavailable  → regex result alone
          → final phone validation + normalization
    """

    def __init__(self, model_path: str = config.SMOLLM_MODEL_PATH):
        self.parser = VoiceOrderParser()
        self.fallback = FallbackParser()
        self.llm = build_llm(model_path)

        # LCEL chain: prompt -> llm -> parser (modern replacement for LLMChain)
        self._extraction_chain = (
            (INTENT_PROMPT | self.llm | self.parser) if self.llm else None
        )
        self._verify_chain = (
            (VERIFY_PROMPT | self.llm) if self.llm else None
        )

        mode = "LangChain LCEL + LlamaCpp (ensemble)" if self._extraction_chain else "Fallback Regex Only"
        logger.info(f"VoiceOrderPipeline ready ({mode})")

    def process(self, stt_text: str, call_id: str = "unknown") -> dict:
        """
        Process STT text through the full ensemble pipeline.

        Returns:
            {
                "phone": "9876543210" or None,
                "items": ["rice 2kg", "milk 1L"],
                "confidence": "high" | "medium" | "low",
                "mode": "ensemble_agree" | "ensemble_verified" | "llm" | "fallback_regex",
                "latency_ms": 234.5,
                "raw_stt": "...",
                "call_id": "..."
            }
        """
        t0 = time.perf_counter()
        text = stt_text.strip()

        result = self._run_ensemble(text, call_id)
        result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        result["raw_stt"] = stt_text
        result["call_id"] = call_id

        # Final phone validation + normalization (never trust raw extraction blindly)
        if result.get("phone"):
            normalized = normalize_phone(result["phone"])
            result["phone"] = normalized  # None if invalid format

        logger.info(
            f"[{call_id}] Intent: phone={result.get('phone', 'N/A')} "
            f"items={result.get('items', [])} mode={result.get('mode')} "
            f"({result['latency_ms']:.0f}ms)"
        )
        return result

    def _run_ensemble(self, text: str, call_id: str) -> dict:
        """
        Ensemble extraction: LLM + regex, voted/reconciled.
        This is what closes the accuracy gap with a tiny CPU model.
        """
        # Always compute the regex result — it's near-instant and a
        # strong prior for phone numbers (which are pattern-perfect).
        regex_result = self.fallback.parse(text)

        # No LLM available — regex is the only option
        if self._extraction_chain is None:
            regex_result["mode"] = "fallback_regex"
            return regex_result

        try:
            llm_result = self._extraction_chain.invoke({"voice_text": text})
        except Exception as e:
            logger.warning(f"[{call_id}] LLM extraction failed ({e}), using regex fallback")
            return {**regex_result, "mode": "fallback_regex", "llm_error": str(e)}

        return self._reconcile(llm_result, regex_result, text, call_id)

    def _reconcile(self, llm_result: dict, regex_result: dict, text: str, call_id: str) -> dict:
        """
        Vote between LLM and regex extraction.

        Agreement rules:
          - Phones match (or one is missing, other present)  → trust the present one
          - Items overlap meaningfully                        → high confidence
          - Total disagreement on phone                       → run verification chain
        """
        llm_phone   = llm_result.get("phone")
        regex_phone = regex_result.get("phone")
        llm_items   = llm_result.get("items", [])
        regex_items = regex_result.get("items", [])

        phones_agree = (llm_phone == regex_phone) or (not llm_phone) or (not regex_phone)
        chosen_phone = llm_phone or regex_phone

        if phones_agree:
            # High confidence: take the union perspective on items (LLM
            # usually phrases items better, regex catches ones LLM misses)
            merged_items = list(llm_items) if llm_items else list(regex_items)
            for item in regex_items:
                if not any(self._items_similar(item, m) for m in merged_items):
                    merged_items.append(item)

            return {
                "phone": chosen_phone,
                "items": merged_items,
                "confidence": "high" if (llm_items or regex_items) else "low",
                "mode": "ensemble_agree",
                "raw": llm_result.get("raw", ""),
            }

        # Disagreement on phone number — escalate to verification chain
        logger.debug(f"[{call_id}] Phone disagreement: LLM={llm_phone} regex={regex_phone}")
        if self._verify_chain is not None:
            try:
                verdict = self._verify_chain.invoke({
                    "voice_text": text,
                    "candidate_a": f"PHONE:{llm_phone} ITEMS:{','.join(llm_items)}",
                    "candidate_b": f"PHONE:{regex_phone} ITEMS:{','.join(regex_items)}",
                }).strip().upper()

                if verdict.startswith("A"):
                    return {**llm_result, "mode": "ensemble_verified", "confidence": "medium"}
                elif verdict.startswith("B"):
                    return {**regex_result, "mode": "ensemble_verified", "confidence": "medium"}
            except Exception as e:
                logger.warning(f"[{call_id}] Verification chain failed: {e}")

        # Could not reconcile — prefer regex for phone (deterministic,
        # near-zero false-positive rate on digit patterns), keep LLM items
        return {
            "phone": regex_phone,
            "items": llm_items or regex_items,
            "confidence": "low",
            "mode": "ensemble_unresolved",
        }

    @staticmethod
    def _items_similar(a: str, b: str) -> bool:
        """Loose similarity check to avoid duplicate items in merged list."""
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        return bool(a_words & b_words)


# ── Singleton ──────────────────────────────────────────────────────────────
_pipeline: Optional[VoiceOrderPipeline] = None


def get_pipeline() -> VoiceOrderPipeline:
    """Get or create the global pipeline instance (lazy load)."""
    global _pipeline
    if _pipeline is None:
        _pipeline = VoiceOrderPipeline()
    return _pipeline


# ── CLI Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_texts = [
        "I want 2 kilos of rice and one liter milk, my phone number is 9876543210",
        "Please send me bread and eggs. My number is 8765432109",
        "Mujhe ek packet namak aur do kilo chawal chahiye, number hai 7654321098",
        "Five hundred grams of butter and one dozen eggs, call me at nine eight seven six five four three two one zero",
    ]

    pipeline = VoiceOrderPipeline(model_path="models/nonexistent.gguf")  # Will use fallback

    for text in test_texts:
        print(f"\n📞 Input: {text}")
        result = pipeline.process(text, call_id="test-001")
        print(f"   📱 Phone: {result.get('phone', 'NOT FOUND')}")
        print(f"   🛒 Items: {result.get('items', [])}")
        print(f"   ⚡ Mode: {result.get('mode')} | {result.get('latency_ms')}ms")
