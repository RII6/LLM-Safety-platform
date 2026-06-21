"""Build the harmful/benign corpus from public datasets.

Scales the hand-written seed corpus (~20 each) up to a real evaluation set by
pulling established safety datasets and merging them with whatever is already in
data/corpus/. Non-destructive: existing curated prompts are kept and deduped
against the new ones.

Sources:
  harmful  <- walledai/AdvBench   (the canonical jailbreak/GCG behavior set)
  benign   <- tatsu-lab/alpaca    (standalone instructions, input-free)

Both are imperative-style ("Write...", "Explain...", "Give..."), which controls
for the prompt-format confound that contaminated the earlier questions-vs-
imperatives split (see the refusal-direction / coupling notes).

Optionally augments a class with model-generated test cases (see generate.py),
turning the fixed corpus into one we can grow with our own dynamic cases. The
generator model is never analysed — it only writes prompts. Needs an API key in
the environment (GROQ_API_KEY or GEMINI_API_KEY).

Usage:
    uv run python build_corpus.py                        # default: 500 per class
    uv run python build_corpus.py --n 1000
    uv run python build_corpus.py --augment groq --aug-n 100               # +100 harmful
    uv run python build_corpus.py --augment google --aug-n 100 --aug-class both
"""
import argparse
import csv
import io
import json
import random
import urllib.request
from pathlib import Path

from datasets import load_dataset

# Canonical AdvBench behaviors from the GCG repo (ungated; the HF mirror is gated).
ADVBENCH_CSV = "https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/data/advbench/harmful_behaviors.csv"

CORPUS = Path("data/corpus")
HARMFUL = CORPUS / "harmful.jsonl"
BENIGN = CORPUS / "benign.jsonl"


def _read_existing(path):
    if not path.exists():
        return []
    return [json.loads(line)["prompt"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _norm(p):
    return " ".join(p.lower().split())


def _dedup(prompts):
    seen, out = set(), []
    for p in prompts:
        p = p.strip()
        key = _norm(p)
        if p and key not in seen:
            seen.add(key)
            out.append(p)
    return out


def load_advbench():
    with urllib.request.urlopen(ADVBENCH_CSV) as resp:
        text = resp.read().decode("utf-8")
    rows = csv.DictReader(io.StringIO(text))
    return [r["goal"] for r in rows]


def load_alpaca():
    ds = load_dataset("tatsu-lab/alpaca", split="train")
    # Keep only standalone instructions (no separate input the prompt refers to).
    return [r["instruction"] for r in ds if not r["input"].strip()]


def build(path, fetched, n, seed):
    existing = _read_existing(path)
    pool = _dedup(existing + fetched)
    # Existing curated prompts always survive; fill the rest from the dataset.
    keep = existing + [p for p in pool if p not in existing]
    rng = random.Random(seed)
    rng.shuffle(keep)
    if n:
        keep = keep[:n]
    path.write_text("".join(json.dumps({"prompt": p}, ensure_ascii=False) + "\n" for p in keep), encoding="utf-8")
    return len(existing), len(keep)


def augment(path, provider, n, model, seed):
    """Append n model-generated variants of the existing prompts; dedup; rewrite.

    Existing prompts seed the generation, so new cases stay on-distribution.
    Returns the number of fresh prompts actually added after de-duplication.
    """
    from generate import generate_variants  # lazy: only import openai when augmenting

    existing = _read_existing(path)
    fresh = generate_variants(existing, n=n, provider=provider, model=model, seed=seed)
    merged = _dedup(existing + fresh)
    path.write_text(
        "".join(json.dumps({"prompt": p}, ensure_ascii=False) + "\n" for p in merged),
        encoding="utf-8",
    )
    return len(merged) - len(existing)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500, help="prompts per class (0 = all available)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--augment", choices=["groq", "google"], default=None,
                    help="after building, append model-generated test cases via this provider")
    ap.add_argument("--aug-n", type=int, default=0, help="how many prompts to generate per augmented class")
    ap.add_argument("--aug-class", choices=["harmful", "benign", "both"], default="harmful",
                    help="which class(es) to augment (default: harmful)")
    ap.add_argument("--aug-model", default=None, help="override generator model id (else provider default / GEN_MODEL)")
    args = ap.parse_args()

    CORPUS.mkdir(parents=True, exist_ok=True)

    print("fetching AdvBench (harmful)...", flush=True)
    h_old, h_new = build(HARMFUL, load_advbench(), args.n, args.seed)
    print(f"  harmful: {h_old} seed -> {h_new} total -> {HARMFUL}", flush=True)

    print("fetching Alpaca (benign)...", flush=True)
    b_old, b_new = build(BENIGN, load_alpaca(), args.n, args.seed)
    print(f"  benign:  {b_old} seed -> {b_new} total -> {BENIGN}", flush=True)

    if args.augment and args.aug_n:
        targets = {"harmful": HARMFUL, "benign": BENIGN}
        if args.aug_class != "both":
            targets = {args.aug_class: targets[args.aug_class]}
        for name, path in targets.items():
            print(f"augmenting {name} via {args.augment} (+{args.aug_n} requested)...", flush=True)
            added = augment(path, args.augment, args.aug_n, args.aug_model, args.seed)
            print(f"  {name}: +{added} new after dedup -> {path}", flush=True)


if __name__ == "__main__":
    main()
