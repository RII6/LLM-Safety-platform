import argparse
import gc
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scanner import pick_device, empty_cache
from src.scanner.modules import (
    safety_margin,
    refusal_direction,
    verdict,
    obfuscation,
    sampling_stability,
    prompt_injection,
    gcg_adversarial,
)
from src.scanner.modules.obfuscation import ObfuscationConfig
from src.scanner.modules.sampling_stability import SamplingStabilityConfig
from src.scanner.modules.prompt_injection import PromptInjectionConfig
from src.scanner.modules.gcg_adversarial import GCGAdversarialConfig


def load(path: str, n: int = 0):
    with open(path, encoding="utf-8") as f:
        prompts = [json.loads(line)["prompt"] for line in f if line.strip()]
    return prompts[:n] if n else prompts


def _cleanup_resources(device):
    if device in ["cuda", "gpu"]:
        from vllm.distributed.parallel_state import destroy_model_parallel

        try:
            destroy_model_parallel()
        except:
            pass
    gc.collect()
    empty_cache(device)


ap = argparse.ArgumentParser(description="Internal-State LLM Safety Scanner")
ap.add_argument("--sample", type=int, default=0)
ap.add_argument("--device", default=None)
ap.add_argument("--obfuscation", action="store_true")
ap.add_argument("--sampling", action="store_true")
ap.add_argument("--injection", action="store_true")
ap.add_argument("--gcg", action="store_true")
ap.add_argument("--config", default="src/configs/general.yaml")

args = ap.parse_args()

device = args.device or pick_device()
device = str(device).lower()

harmful = load("src/data/corpus/harmful.jsonl", args.sample)
benign = load("src/data/corpus/benign.jsonl", args.sample)

print(
    f"corpus: {len(harmful)} harmful / {len(benign)} benign | device={device}",
    flush=True,
)

CHECKPOINTS = [
    "Qwen/Qwen3-1.7B",
    "huihui-ai/Qwen2.5-1.5B-Instruct-abliterated",
    "Qwen/Qwen2.5-1.5B",
]

for ckpt in CHECKPOINTS:
    print("=" * 70, flush=True)
    print(f"Model: {ckpt}", flush=True)

    t0 = time.time()
    margin = safety_margin.run(ckpt, harmful, benign, device=device)
    print(f"  safety_margin done in {time.time() - t0:.1f}s", flush=True)
    _cleanup_resources(device)

    t0 = time.time()
    direction = refusal_direction.run(ckpt, harmful, benign, device=device)
    print(f"  refusal_direction done in {time.time() - t0:.1f}s", flush=True)
    _cleanup_resources(device)

    inj_result = None
    if args.injection:
        inj_cfg = PromptInjectionConfig.from_yaml(args.config)
        t0 = time.time()
        inj_result = prompt_injection.run(ckpt, harmful, config=inj_cfg)
        print(f"  prompt_injection done in {time.time() - t0:.1f}s", flush=True)
        _cleanup_resources(device)

    report = verdict.compute(margin, direction, inj_result)

    print("[safety_margin]    ", json.dumps(margin["summary"], indent=2), flush=True)
    print("[refusal_direction]", json.dumps(direction["summary"], indent=2), flush=True)
    if inj_result is not None:
        print(
            "[prompt_injection] ",
            json.dumps(inj_result["summary"], indent=2),
            flush=True,
        )
    print("[verdict]          ", json.dumps(report["summary"], indent=2), flush=True)

    if args.sampling:
        ss_cfg = SamplingStabilityConfig.from_yaml(args.config)
        ss_result = sampling_stability.from_margins(margin, config=ss_cfg)
        print(
            "[sampling_stability]",
            json.dumps(ss_result["summary"], indent=2),
            flush=True,
        )

    if args.obfuscation:
        obf_cfg = ObfuscationConfig.from_yaml(args.config)
        t0 = time.time()
        obf_result = obfuscation.run(ckpt, harmful, config=obf_cfg)
        print(f"  obfuscation done in {time.time() - t0:.1f}s", flush=True)
        print(
            "[obfuscation]      ",
            json.dumps(obf_result["summary"], indent=2),
            flush=True,
        )
        _cleanup_resources(device)
        if args.gcg:
            gcg_cfg = GCGAdversarialConfig.from_yaml(args.config)
            t0 = time.time()
            gcg_result = gcg_adversarial.run(ckpt, harmful, config=gcg_cfg)
            print(f"  gcg_adversarial done in {time.time() - t0:.1f}s", flush=True)
            print(
                "[gcg_adversarial]  ",
                json.dumps(gcg_result["summary"], indent=2),
                flush=True,
            )
            _cleanup_resources(device)

        print(flush=True)