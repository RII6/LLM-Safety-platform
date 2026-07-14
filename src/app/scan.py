import gc
import hashlib
import json
import threading
import time
from datetime import datetime, timezone

from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError

from src.scanner import empty_cache
from src.scanner.modules import safety_margin, refusal_direction, verdict
from src.scanner.modules import obfuscation
from src.scanner.modules import gcg_adversarial
from src.scanner.modules.prompt_injection import (
    PromptInjectionConfig,
    run as run_injection,
)
from src.scanner.modules import sampling_stability

from . import config, db, explain

_api = HfApi()
_lock = threading.Lock()

_WEIGHT_EXT = (".safetensors", ".bin")


class ScanError(Exception):

    def init(self, status, message):
        super().init(message)
        self.status = status
        self.message = message


def _read_prompts(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line)["prompt"] for line in f if line.strip()]


def _load_corpus():
    harmful = _read_prompts(config.CORPUS / "harmful.jsonl")[: config.SAMPLE]
    benign = _read_prompts(config.CORPUS / "benign.jsonl")[: config.SAMPLE]
    return harmful, benign


def _generate_for_class(cls):
    config.GEN_CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = (
        config.GEN_CACHE
        / f"{config.GEN_PROVIDER}_{cls}_n{config.GEN_N}_seed{config.GEN_SEED}.jsonl"
    )
    if cache_file.exists():
        return _read_prompts(cache_file)

    try:
        from generate import generate_variants

        seeds = _read_prompts(config.CORPUS / f"{cls}.jsonl")
        fresh = generate_variants(
            seeds,
            n=config.GEN_N,
            provider=config.GEN_PROVIDER,
            model=config.GEN_MODEL,
            seed=config.GEN_SEED,
        )
    except Exception as e:
        print(f"[scan] dynamic generation for '{cls}' failed: {e}", flush=True)
        return []

    cache_file.write_text(
        "".join(
            json.dumps({"prompt": p}, ensure_ascii=False) + "\n" for p in fresh
        ),
        encoding="utf-8",
    )
    return fresh


def _generate_dynamic():
    if config.GEN_N <= 0:
        return {"harmful": [], "benign": []}
    classes = (
        ["harmful", "benign"] if config.GEN_CLASS == "both" else [config.GEN_CLASS]
    )
    out = {"harmful": [], "benign": []}
    for cls in classes:
        out[cls] = _generate_for_class(cls)
    return out


def _model_info(repo):
    try:
        return _api.model_info(repo, files_metadata=True)
    except RepositoryNotFoundError:
        raise ScanError(
            404, f"Model repo '{repo}' not found on the Hugging Face Hub."
        )
    except Exception as e:
        raise ScanError(400, f"Could not read repo metadata: {e}")


def _check_size(info):
    params = getattr(getattr(info, "safetensors", None), "total", None)
    if params and params > config.MAX_PARAMS:
        raise ScanError(
            413,
            f"Model has ~{params / 1e6:.0f}M parameters; the cap is "
            f"{config.MAX_PARAMS / 1e6:.0f}M for this 2 GB VM.",
        )

    weight_bytes = sum(
        s.size or 0
        for s in info.siblings
        if s.rfilename.endswith(_WEIGHT_EXT) and s.size
    )
    if weight_bytes > config.MAX_WEIGHT_BYTES:
        raise ScanError(
            413,
            f"Model weights are ~{weight_bytes / 1e9:.1f} GB; the cap is "
            f"{config.MAX_WEIGHT_BYTES / 1e9:.1f} GB for this VM.",
        )
    return params, weight_bytes


def _oid(sibling):
    lfs = getattr(sibling, "lfs", None)
    if lfs is not None:
        sha = getattr(lfs, "sha256", None)
        if sha is None and isinstance(lfs, dict):
            sha = lfs.get("sha256")
        if sha:
            return sha
    return getattr(sibling, "blob_id", None) or ""
def _cache_key(info, gen=None):
    parts = sorted(
        f"{s.rfilename}:{_oid(s)}"
        for s in info.siblings
        if s.rfilename.endswith(_WEIGHT_EXT)
    )
    raw = "|".join(parts) + f"|sample={config.SAMPLE}|dtype={config.DTYPE}"
    if gen and (gen.get("harmful") or gen.get("benign")):
        blob = json.dumps(gen, ensure_ascii=False, sort_keys=True)
        raw += "|gen=" + hashlib.sha256(blob.encode()).hexdigest()[:12]
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _merge(static, generated):
    seen = {p.strip().lower() for p in static}
    extra = [p for p in generated if p.strip().lower() not in seen]
    return static + extra


def _cleanup_resources(device):
    if device in ["cuda", "gpu"]:
        from vllm.distributed.parallel_state import destroy_model_parallel

        try:
            destroy_model_parallel()
        except:
            pass
    gc.collect()
    empty_cache(device)


def _run_scan(repo, params, weight_bytes, gen, modules):
    harmful, benign = _load_corpus()
    harmful = _merge(harmful, gen.get("harmful", []))
    benign = _merge(benign, gen.get("benign", []))
    t0 = time.time()
    dev = str(config.DEVICE).lower()

    try:
        margin = safety_margin.run(repo, harmful, benign, device=dev)
        _cleanup_resources(dev)

        direction = refusal_direction.run(repo, harmful, benign, device=dev)
        _cleanup_resources(dev)

        injection_result = None
        if "prompt_injections" in modules:
            try:
                inj_cfg = PromptInjectionConfig.from_yaml()
                injection_result = run_injection(repo, harmful, config=inj_cfg)
            except Exception as e:
                print(f"[ERROR] prompt_injection failed: {e}", flush=True)
                injection_result = None
            _cleanup_resources(dev)

        obfuscation_result = None
        if "obfuscation" in modules:
            obfuscation_result = obfuscation.run(
                repo,
                harmful,
                config=obfuscation.ObfuscationConfig.from_yaml(
                    str(config.ROOT / "configs" / "general.yaml")
                ),
            )
            _cleanup_resources(dev)

        sampling_result = None
        if "sampling" in modules:
            try:
                sampling_result = sampling_stability.run(
                    repo,
                    harmful,
                    config=sampling_stability.SamplingStabilityConfig.from_yaml(
                        str(config.ROOT / "configs" / "general.yaml")
                    ),
                )
            except Exception as e:
                print(f"[ERROR] sampling_stability failed: {e}", flush=True)
                sampling_result = None
            _cleanup_resources(dev)

        gcg_result = None
        if "gcg" in modules:
            try:
                gcg_result = gcg_adversarial.run(
                    repo,
                    harmful,
                    config=gcg_adversarial.GCGAdversarialConfig.from_yaml(
                        str(config.ROOT / "configs" / "general.yaml")
                    ),
                )
            except Exception as e:
                print(f"[ERROR] gcg_adversarial failed: {e}", flush=True)
                gcg_result = None
            _cleanup_resources(dev)
    finally:
        _cleanup_resources(dev)

    report = verdict.compute(margin, direction)

    meta = {
        "params": params,
        "weight_bytes": weight_bytes,
        "sample": config.SAMPLE,
        "device": dev,
        "dtype": "float32" if dev == "cpu" else str(config.DTYPE).replace("torch.", ""),
        "generated": {
            "harmful": len(gen.get("harmful", [])),
            "benign": len(gen.get("benign", [])),
        },
        "elapsed_s": round(time.time() - t0, 1),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return explain.build(
        repo,
        margin,
        direction,
        report,
        meta,
        injection=injection_result,
        obfuscation=obfuscation_result,
        sampling=sampling_result,
        gcg=gcg_result,
    )
def scan(repo, force=False, modules=None, user_id=None):
        if modules is None:
            modules = ["general"]

        repo = repo.strip()
        if not repo or repo.count("/") != 1:
            raise ScanError(400, "Enter a repo id like 'owner/model'.")

        info = _model_info(repo)
        params, weight_bytes = _check_size(info)
        gen = _generate_dynamic()
        key = _cache_key(info, gen)

        if not force:
            cached = db.get_cached(key)
            if cached is not None:
                if user_id is not None:
                    db.record_user_scan_by_key(user_id, key)
                cached["from_cache"] = True
                return cached

        if not _lock.acquire(blocking=False):
            raise ScanError(429, "A scan is already running. Try again in a moment.")
        try:
            result = _run_scan(repo, params, weight_bytes, gen, modules)
        finally:
            _lock.release()

        scan_id = db.save_scan(repo, key, result)
        result["id"] = scan_id
        if user_id is not None:
            db.record_user_scan(user_id, scan_id)
        result["from_cache"] = False
        return result