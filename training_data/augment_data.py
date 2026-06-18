"""
training_data/augment_data.py — Expand training samples to 1000+

Techniques:
1. Phone number substitution  — swap phone numbers across samples
2. Item quantity variation    — change quantities (1kg→2kg, etc.)
3. Language mixing            — insert Hindi/Tamil words randomly
4. Noise injection            — add filler words (um, uh, please, etc.)
5. Order shuffling            — reorder items in sentence
6. Spoken phone expansion     — convert digits to words

Run: python training_data/augment_data.py
Output: training_data/samples_augmented.json (~1000 samples)
"""
import json
import random
import re
from pathlib import Path
from copy import deepcopy

ROOT = Path(__file__).parent

# ── Phone pool for substitution ────────────────────────────────────────────
PHONE_POOL = [
    "9876543210", "8765432109", "7654321098", "9123456789",
    "8234567890", "6543210987", "9988776655", "9012345678",
    "9871234560", "9861234570", "9851234580", "9841234590",
    "9831234500", "9821234510", "9811234520", "9801234530",
    "9791234540", "9781234550", "9771234560", "9761234570",
]

# ── Spoken phone word map ──────────────────────────────────────────────────
DIGIT_WORDS = {"0":"zero","1":"one","2":"two","3":"three","4":"four",
               "5":"five","6":"six","7":"seven","8":"eight","9":"nine"}

def to_spoken(phone: str) -> str:
    return " ".join(DIGIT_WORDS[d] for d in phone)

# ── Filler words for noise injection ──────────────────────────────────────
FILLERS = ["um", "uh", "please", "actually", "so", "like", "yeah", "I mean"]

HINDI_CONNECTORS = [
    "bhai", "ji", "please", "yaar", "aur",
]

# ── Quantity variants ─────────────────────────────────────────────────────
QTY_VARIANTS = {
    "1kg":    ["1 kilo", "one kilo", "one kilogram", "1 kilogram"],
    "2kg":    ["2 kilo", "two kilos", "2 kilograms"],
    "500g":   ["half kilo", "500 grams", "half a kilo"],
    "1L":     ["one litre", "one liter", "1 litre"],
    "2L":     ["two litres", "2 litres", "2 liters"],
    "1 packet": ["one packet", "a packet", "single packet"],
    "2 packets": ["two packets", "a couple of packets"],
}

# ── Templates for generating new samples ──────────────────────────────────
TEMPLATES = [
    "I want {items}, my number is {phone}",
    "Please send {items}, call me at {phone}",
    "Order {items} to my number {phone}",
    "I need {items}, phone {phone}",
    "Book {items} for me, number {phone}",
    "Send me {items}, contact {phone}",
    "Can you deliver {items}, my mobile is {phone}",
    "{items} please, my number is {phone}",
    "I'd like to order {items}, you can call me at {phone}",
    "Deliver {items}, phone number {phone}",
    "Get me {items}, my contact is {phone}",
    "I want to order {items}, reach me at {phone}",
]

HINDI_TEMPLATES = [
    "Mujhe {items} chahiye, number {phone}",
    "{items} bhejo, mera number {phone} hai",
    "Please {items} order karo, phone {phone}",
    "{items} chahiye bhai, number hai {phone}",
]

TAMIL_TEMPLATES = [
    "{items} venam, en number {phone}",
    "Oru {items} order panna, number {phone}",
    "{items} anupunga, phone number {phone}",
]


def augment(samples: list, target: int = 1000) -> list:
    augmented = list(samples)  # Start with original samples
    original_count = len(samples)
    random.seed(42)

    print(f"Starting with {original_count} samples, targeting {target}...")

    while len(augmented) < target:
        technique = random.choice([
            "phone_swap", "phone_spoken", "filler_inject",
            "template_gen", "qty_vary", "duplicate_shuffle"
        ])

        src = random.choice(samples)

        if technique == "phone_swap":
            # Swap phone number with a different one
            new_phone = random.choice([p for p in PHONE_POOL if p != src.get("output", "")[:12]])
            new_inp = re.sub(r'[6-9]\d{9}', new_phone, src["input"])
            new_out = re.sub(r'PHONE:\d{10}', f'PHONE:{new_phone}', src["output"])
            if new_inp != src["input"]:
                augmented.append({"input": new_inp, "output": new_out})

        elif technique == "phone_spoken":
            # Convert numeric phone to spoken words
            phone_match = re.search(r'([6-9]\d{9})', src["input"])
            if phone_match:
                phone = phone_match.group(1)
                spoken = to_spoken(phone)
                new_inp = src["input"].replace(phone, spoken)
                augmented.append({"input": new_inp, "output": src["output"]})

        elif technique == "filler_inject":
            # Insert a filler word somewhere in the sentence
            words = src["input"].split()
            if len(words) > 3:
                pos = random.randint(1, len(words) - 1)
                filler = random.choice(FILLERS)
                words.insert(pos, filler)
                augmented.append({"input": " ".join(words), "output": src["output"]})

        elif technique == "template_gen":
            # Generate from template using items extracted from output
            out = src["output"]
            phone_m = re.search(r'PHONE:(\d{10})', out)
            items_m = re.search(r'ITEMS:(.+)', out)
            if phone_m and items_m:
                phone = phone_m.group(1)
                items_str = items_m.group(1)
                items_words = items_str.replace(",", " and ")
                tmpl = random.choice(TEMPLATES + HINDI_TEMPLATES)
                new_inp = tmpl.format(items=items_words, phone=phone)
                augmented.append({"input": new_inp, "output": out})

        elif technique == "qty_vary":
            # Replace quantity strings with variants
            new_inp = src["input"]
            for qty, variants in QTY_VARIANTS.items():
                if qty in new_inp:
                    new_inp = new_inp.replace(qty, random.choice(variants), 1)
                    break
            if new_inp != src["input"]:
                augmented.append({"input": new_inp, "output": src["output"]})

        elif technique == "duplicate_shuffle":
            # Shuffle item order in the input sentence (when multiple items)
            out = src["output"]
            items_m = re.search(r'ITEMS:(.+)', out)
            if items_m:
                items_list = [i.strip() for i in items_m.group(1).split(",")]
                if len(items_list) >= 2:
                    random.shuffle(items_list)
                    new_out = re.sub(r'ITEMS:.+', f'ITEMS:{",".join(items_list)}', out)
                    augmented.append({"input": src["input"], "output": new_out})

    # Deduplicate by input text
    seen = set()
    unique = []
    for s in augmented:
        key = s["input"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    unique = unique[:target]
    print(f"Final dataset: {len(unique)} samples ({len(unique) - original_count} augmented)")
    return unique


def main():
    input_path  = ROOT / "samples.json"
    output_path = ROOT / "samples_augmented.json"

    with open(input_path) as f:
        samples = json.load(f)

    augmented = augment(samples, target=1000)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(augmented, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved {len(augmented)} samples → {output_path}")
    print("   Use this file for fine-tuning:")
    print("   Update DATASET_PATH in fine_tune_smollm.py:")
    print(f"   DATASET_PATH = Path('{output_path}')")


if __name__ == "__main__":
    main()
