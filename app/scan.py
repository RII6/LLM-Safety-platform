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


def _load_corpus():
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


def _generate_for_class(cls, settings, strict=False):
    """Return n fresh prompts for *cls*, cached on disk by provider/model/class/n/seed."""
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
        from generate import generate_variants

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
        print(f"[scan] dynamic generation for '{cls}' failed: {e}", flush=True)
        return []

    cache_file.write_text(
        "".join(json.dumps({"prompt": p}, ensure_ascii=False) + "\n" for p in fresh),
        encoding="utf-8",
    )
    return fresh


def _generate_dynamic(settings, strict=False):
    """Generate the scan-time prompt mix-in: {'harmful': [...], 'benign': [...]}."""
    _validate_generation(settings)
    if settings["n"] <= 0:
        return {"harmful": [], "benign": []}
    classes = ["harmful", "benign"] if settings["class"] == "both" else [settings["class"]]
    out = {"harmful": [], "benign": []}
    for cls in classes:
        out[cls] = _generate_for_class(cls, settings, strict=strict)
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
    """Content id of a file: LFS sha256 for weight blobs, git blob id otherwise."""
    lfs = getattr(sibling, "lfs", None)
    if lfs is not None:
        sha = getattr(lfs, "sha256", None)
        if sha is None and isinstance(lfs, dict):
            sha = lfs.get("sha256")
        if sha:
            return sha
    return getattr(sibling, "blob_id", None) or ""


def _cache_key(info, gen=None):
    """Hash over weight-file contents plus the scan params that change the verdict.

    Generated prompts are folded in (by content) so a dynamic scan stays
    reproducible: same model + same generated set -> cache hit; a new set ->
    a fresh report rather than a stale cached one.
    """
    parts = sorted(
        f"{s.rfilename}:{_oid(s)}" for s in info.siblings if s.rfilename.endswith(_WEIGHT_EXT)
    )
    raw = "|".join(parts) + f"|sample={config.SAMPLE}|dtype={config.DTYPE}"
    if gen and (gen.get("harmful") or gen.get("benign")):
        blob = json.dumps(gen, ensure_ascii=False, sort_keys=True)
        raw += "|gen=" + hashlib.sha256(blob.encode()).hexdigest()[:12]
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _merge(static, generated):
    """Static corpus first, then de-duplicated dynamic prompts appended."""
    seen = {p.strip().lower() for p in static}
    extra = [p for p in generated if p.strip().lower() not in seen]
    return static + extra


def _run_scan(repo, params, weight_bytes, gen, generation_settings):
    harmful, benign = _load_corpus()
    harmful = _merge(harmful, gen.get("harmful", []))
    benign = _merge(benign, gen.get("benign", []))
    t0 = time.time()
    model = Model(repo, device=config.DEVICE, dtype=config.DTYPE)
    try:
        margin = safety_margin.run(model, harmful, benign)
        direction = refusal_direction.run(model, harmful, benign)
    finally:
        del model
        gc.collect()
        empty_cache(config.DEVICE)

    report = verdict.compute(margin, direction)
    meta = {
        "params": params,
        "weight_bytes": weight_bytes,
        "sample": config.SAMPLE,
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
    }
    return explain.build(repo, margin, direction, report, meta)


def scan(repo, force=False, user_id=None, generation=None):
    repo = repo.strip()
    if not repo or repo.count("/") != 1:
        raise ScanError(400, "Enter a repo id like 'owner/model'.")

    info = _model_info(repo)
    params, weight_bytes = _check_size(info)
    generation_settings, strict_generation = _generation_settings(generation)
    gen = _generate_dynamic(generation_settings, strict=strict_generation)
    key = _cache_key(info, gen)

    if not force:
        cached = db.get_cached(key)
        if cached is not None:
            if user_id is not None:
                db.record_user_scan_by_key(user_id, key)  # add to this user's history
            cached["from_cache"] = True
            return cached

    if not _lock.acquire(blocking=False):
        raise ScanError(429, "A scan is already running. Try again in a moment.")
    try:
        result = _run_scan(repo, params, weight_bytes, gen, generation_settings)
    finally:
        _lock.release()

    scan_id = db.save_scan(repo, key, result)
    if user_id is not None:
        db.record_user_scan(user_id, scan_id)  # add to this user's history
    result["from_cache"] = False
    return result
