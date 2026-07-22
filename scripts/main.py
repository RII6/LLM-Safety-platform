import argparse
import gc
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scanner import Model, pick_device, empty_cache
from src.scanner.modules import (
    safety_margin,
    refusal_direction,
    verdict,
    obfuscation,
    sampling_stability,
    prompt_injection,
    gcg_adversarial,
    memory_extraction
)

from src.scanner.modules.obfuscation import ObfuscationConfig
from src.scanner.modules.sampling_stability import SamplingStabilityConfig
from src.scanner.modules.prompt_injection import PromptInjectionConfig
from src.scanner.modules.gcg_adversarial import GCGAdversarialConfig
from src.scanner.modules.memory_extraction import MemoryExtractionConfig

def load(path: str, n: int = 0):
    with open(path, encoding="utf-8") as f:
        prompts = [json.loads(line)["prompt"] for line in f if line.strip()]
    return prompts[:n] if n else prompts

ap = argparse.ArgumentParser(description="Internal-State LLM Safety Scanner")
ap.add_argument("--sample", type=int, default=0,
                help="per-class prompt cap for fast dev runs (0 = full corpus)")
ap.add_argument("--device", default=None,
                help="cuda / mps / cpu (default: auto-detect)")

ap.add_argument("--obfuscation", action="store_true", help="run obfuscation attack battery")
ap.add_argument("--sampling", action="store_true", help="run sampling stability analysis")
ap.add_argument("--injection", action="store_true", help="run prompt injection detection")
ap.add_argument("--gcg", action="store_true", help="run GCG adversarial suffix attack")
ap.add_argument("--memory-extraction", action="store_true", help="run memory extraction attack (PII leakage)")

ap.add_argument("--config", default="src/configs/general.yaml",
                help="path to YAML config (default: src/configs/general.yaml)")

args = ap.parse_args()

device = args.device or pick_device()
harmful = load("src/data/corpus/harmful.jsonl", args.sample)
benign = load("src/data/corpus/benign.jsonl", args.sample)

print(f"corpus: {len(harmful)} harmful / {len(benign)} benign | device={device}", flush=True)

CHECKPOINTS = [
    "Qwen/Qwen3-1.7B",
    "huihui-ai/Qwen2.5-1.5B-Instruct-abliterated",
    "Qwen/Qwen2.5-1.5B",
]

for ckpt in CHECKPOINTS:
    print("=" * 70, flush=True)
    print(f"Model: {ckpt}", flush=True)
    t0 = time.time()
    model = Model(ckpt, device)
    print(f"  loaded in {time.time() - t0:.1f}s", flush=True)

    margin = safety_margin.run(model, harmful, benign)
    direction = refusal_direction.run(model, harmful, benign)

    inj_result = None
    if args.injection:
        inj_cfg = PromptInjectionConfig.from_yaml(args.config)
        inj_result = prompt_injection.run(model, harmful, config=inj_cfg)

    report = verdict.compute(margin, direction, inj_result)

    print("[safety_margin]    ", json.dumps(margin["summary"], indent=2), flush=True)
    print("[refusal_direction]", json.dumps(direction["summary"], indent=2), flush=True)
    if inj_result is not None:
        print("[prompt_injection] ", json.dumps(inj_result["summary"], indent=2), flush=True)
    print("[verdict]          ", json.dumps(report["summary"], indent=2), flush=True)

    if args.sampling:
        ss_cfg = SamplingStabilityConfig.from_yaml(args.config)
        ss_result = sampling_stability.from_margins(margin, config=ss_cfg)
        print("[sampling_stability]", json.dumps(ss_result["summary"], indent=2), flush=True)

    if args.obfuscation:
        obf_cfg = ObfuscationConfig.from_yaml(args.config)
        obf_result = obfuscation.run(model, harmful, config=obf_cfg)
        print("[obfuscation]      ", json.dumps(obf_result["summary"], indent=2), flush=True)

    if args.gcg:
        gcg_cfg = GCGAdversarialConfig.from_yaml(args.config)
        gcg_result = gcg_adversarial.run(model, harmful, config=gcg_cfg)
        print("[gcg_adversarial]  ", json.dumps(gcg_result["summary"], indent=2), flush=True)

    if args.memory_extraction:
        mem_cfg = MemoryExtractionConfig.from_yaml(args.config)
        mem_result = memory_extraction.run(model, config=mem_cfg)
        print("[memory_extraction]", json.dumps(mem_result.get("summary", {}), indent=2), flush=True)

    print(flush=True)

    if hasattr(model, "vllm_engine") and model.vllm_engine is not None:
        try:
            from vllm.distributed.parallel_state import destroy_model_parallel
            destroy_model_parallel()
        except Exception:
            pass
        del model.vllm_engine

    del model
    gc.collect()
    empty_cache(device)