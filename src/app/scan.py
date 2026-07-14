"""Validate a HF repo, run the scanner once, cache the report by weight content."""

import gc
import hashlib
import json
import re
import threading
import time
from datetime import datetime, timezone

from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError

from src.scanner import Model, empty_cache
from src.scanner.modules import safety_margin, refusal_direction, verdict
from src.scanner.modules import obfuscation
from src.scanner.modules import gcg_adversarial
from src.scanner.modules.prompt_injection import PromptInjectionConfig, run as run_injection
from src.scanner.modules import sampling_stability
from src.scanner.modules.memory_extraction import MemoryExtractionConfig, run as run_memory_extraction  # ← НОВОЕ

from . import config, db, explain

_api = HfApi()
_lock = threading.Lock()

_WEIGHT_EXT = (".safetensors", ".bin")
_GEN_CLASSES = {"harmful", "benign", "both"}
_GEN_PROVIDERS = {"groq", "google"}


class ScanError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _read_prompts(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line)["prompt"] for line in f if line.strip()]


def _load_corpus(sample=None):
    if sample is None:
        sample = config.SAMPLE
    harmful = _read_prompts(config.CORPUS / "harmful.jsonl")[: config.SAMPLE]
    benign = _read_prompts(config.CORPUS / "benign.jsonl")[: config.SAMPLE]
    return harmful, benign


def _safe_cache_part(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "default")[:80]


def _generation_settings(generation=None):
    if generation is None:
        settings = {
            "n": config.GEN_N,
            "provider": config.GEN_PROVIDER,
            "model": config.GEN_MODEL,
            "seed": config.GEN_SEED,
            "class": config.GEN_CLASS,
        }
        return settings, False
    enabled = bool(generation.get("enabled", False))
    settings = {
        "n": int(generation.get("n", 0)) if enabled else 0,
        "provider": str(generation.get("provider") or config.GEN_PROVIDER).strip().lower(),
        "model": generation.get("model") or None,
        "seed": int(generation.get("seed", config.GEN_SEED)),
        "class": str(generation.get("class") or config.GEN_CLASS).strip().lower(),
    }
    if settings["model"] is not None:
        settings["model"] = str(settings["model"]).strip() or None
    return settings, enabled and settings["n"] > 0


def _validate_generation(settings):
    if settings["n"] < 0:
        raise ScanError(400, "Generation count must be non-negative.")
    if settings["provider"] not in _GEN_PROVIDERS:
        raise ScanError(400, "Generation provider must be one of: groq, google.")
    if settings["class"] not in _GEN_CLASSES:
        raise ScanError(400, "Generation class must be one of: harmful, benign, both.")


def _generate_for_class(cls, settings, strict=False, log_cb=None):
    """Return GEN_N fresh prompts for *cls*, cached on disk by provider/class/n/seed."""
    config.GEN_CACHE.mkdir(parents=True, exist_ok=True)
    provider = settings["provider"]
    model = settings["model"]
    n = settings["n"]
    seed = settings["seed"]
    model_key = _safe_cache_part(model)
    cache_file = config.GEN_CACHE / f"{provider}_{model_key}_{cls}_n{n}_seed{seed}.jsonl"
    
    if cache_file.exists():
        return _read_prompts(cache_file)

    try:
        from scripts.generate import generate_variants
        seeds = _read_prompts(config.CORPUS / f"{cls}.jsonl")
        fresh = generate_variants(
            seeds,
            n=n,
            provider=provider,
            model=model,
            seed=seed,
        )
    except Exception as e:
        if strict:
            raise ScanError(400, f"Dynamic generation failed for '{cls}': {e}")
        msg = f"[scan] dynamic generation for '{cls}' failed: {e}"
        if log_cb: log_cb(msg)
        print(msg, flush=True)
        return []

    cache_file.write_text(
        "".join(json.dumps({"prompt": p}, ensure_ascii=False) + "\n" for p in fresh),
        encoding="utf-8",
    )
    return fresh


def _generate_dynamic(settings, strict=False, log_cb=None):
    _validate_generation(settings)
    if settings["n"] <= 0:
        return {"harmful": [], "benign": []}
    classes = ["harmful", "benign"] if settings["class"] == "both" else [settings["class"]]
    out = {"harmful": [], "benign": []}
    for cls in classes:
        out[cls] = _generate_for_class(cls, settings, strict=strict, log_cb=log_cb)
    return out


def _model_info(repo):
    try:
        return _api.model_info(repo, files_metadata=True)
    except RepositoryNotFoundError:
        raise ScanError(404, f"Model repo '{repo}' not found on the Hugging Face Hub.")
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
        s.size or 0 for s in info.siblings if s.rfilename.endswith(_WEIGHT_EXT) and s.size
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


def _cache_key(info, gen=None, sample=None):
    if sample is None:
        sample = config.SAMPLE
    parts = sorted(
        f"{s.rfilename}:{_oid(s)}" for s in info.siblings if s.rfilename.endswith(_WEIGHT_EXT)
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


def _run_scan(repo, params, weight_bytes, gen, modules, generation_settings, sample=None, log_cb=None):
    def _log(msg):
        if log_cb: log_cb(msg)
        print(msg, flush=True)

    harmful, benign = _load_corpus()
    harmful = _merge(harmful, gen.get("harmful", []))
    benign = _merge(benign, gen.get("benign", []))

    t0 = time.time()
    model = Model(repo, device=config.DEVICE, dtype=config.DTYPE)

    try:
        margin = safety_margin.run(model, harmful, benign)
        direction = refusal_direction.run(model, harmful, benign)

        # Prompt Injection
        injection_result = None
        if "prompt_injections" in modules:
            _log("[DEBUG] Running prompt_injection module...")
            try:
                inj_cfg = PromptInjectionConfig.from_yaml()
                injection_result = run_injection(model, harmful, config=inj_cfg)
                _log("[DEBUG] prompt_injection completed")
            except Exception as e:
                _log(f"[ERROR] prompt_injection failed: {e}")

        # Obfuscation
        obfuscation_result = None
        if "obfuscation" in modules:
            _log("[DEBUG] Running obfuscation module...")
            try:
                obfuscation_result = obfuscation.run(
                    model, harmful,
                    config=obfuscation.ObfuscationConfig.from_yaml(
                        str(config.ROOT / "configs" / "general.yaml")
                    )
                )
                _log("[DEBUG] obfuscation completed")
            except Exception as e:
                _log(f"[ERROR] obfuscation failed: {e}")

        # Sampling Stability
        sampling_result = None
        if "sampling" in modules:
            _log("[DEBUG] Running sampling_stability module...")
            try:
                sampling_result = sampling_stability.run(
                    model, harmful,
                    config=sampling_stability.SamplingStabilityConfig.from_yaml(
                        str(config.ROOT / "configs" / "general.yaml")
                    )
                )
                _log("[DEBUG] sampling_stability completed")
            except Exception as e:
                _log(f"[ERROR] sampling_stability failed: {e}")

        # GCG Adversarial
        gcg_result = None
        if "gcg" in modules:
            _log("[DEBUG] Running gcg_adversarial module...")
            try:
                gcg_result = gcg_adversarial.run(
                    model, harmful,
                    config=gcg_adversarial.GCGAdversarialConfig.from_yaml(
                        str(config.ROOT / "configs" / "general.yaml")
                    )
                )
                _log("[DEBUG] gcg_adversarial completed")
            except Exception as e:
                _log(f"[ERROR] gcg_adversarial failed: {e}")

        # === MEMORY EXTRACTION ===
        memory_result = None
        if "memory_extraction" in modules:
            _log("[DEBUG] Running memory_extraction module...")
            try:
                mem_cfg = MemoryExtractionConfig.from_yaml(
                    str(config.ROOT / "configs" / "general.yaml")
                )
                memory_result = run_memory_extraction(model, config=mem_cfg)
                _log("[DEBUG] memory_extraction completed")
            except Exception as e:
                _log(f"[ERROR] memory_extraction failed: {e}")
                memory_result = None

    finally:
        del model
        gc.collect()
        empty_cache(config.DEVICE)

    report = verdict.compute(margin, direction)

    meta = {
        "params": params,
        "weight_bytes": weight_bytes,
        "device": config.DEVICE,
        "dtype": str(config.DTYPE).replace("torch.", ""),
        "generated": {
            "harmful": len(gen.get("harmful", [])),
            "benign": len(gen.get("benign", [])),
            "requested_per_class": generation_settings["n"],
            "provider": generation_settings["provider"],
            "model": generation_settings["model"],
            "class": generation_settings["class"],
            "seed": generation_settings["seed"],
        },
        "elapsed_s": round(time.time() - t0, 1),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sample": sample if sample is not None else config.SAMPLE,
    }

    return explain.build(
        repo, margin, direction, report, meta,
        injection=injection_result,
        obfuscation=obfuscation_result,
        sampling=sampling_result,
        gcg=gcg_result,
        memory=memory_result          # ← НОВОЕ
    )


def scan(repo, force=False, modules=None, user_id=None, sample=None, generation=None, log_cb=None):
    if modules is None:
        modules = ["general"]

    repo = repo.strip()
    if not repo or repo.count("/") != 1:
        raise ScanError(400, "Enter a repo id like 'owner/model'.")

    info = _model_info(repo)
    params, weight_bytes = _check_size(info)

    generation_settings, strict_generation = _generation_settings(generation)
    gen = _generate_dynamic(generation_settings, strict=strict_generation, log_cb=log_cb)

    key = _cache_key(info, gen, sample=sample)

    if not force:
        cached = db.get_cached(key)
        if cached is not None:
            if user_id is not None:
                db.record_user_scan_by_key(user_id, key)
            cached["from_cache"] = True
            return cached

    _lock.acquire()

    try:
        result = _run_scan(repo, params, weight_bytes, gen, modules, generation_settings, sample=sample, log_cb=log_cb)
    finally:
        _lock.release()

    scan_id = db.save_scan(repo, key, result)
    result["id"] = scan_id
    if user_id is not None:
        db.record_user_scan(user_id, scan_id)
    result["from_cache"] = False
    return result
