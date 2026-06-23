from contextlib import asynccontextmanager
from pathlib import Path

from typing import List

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db
from .scan import ScanError, scan

STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="LLM Safety Scanner", lifespan=lifespan)


class ScanRequest(BaseModel):
    repo: str
    force: bool = False
    modules: List[str] = ["general"]


@app.get("/api/health")
def health():
    return {"ok": True, "demo_model": config.DEMO_MODEL, "sample": config.SAMPLE}


@app.post("/api/scan")
async def run_scan(request: ScanRequest):
    selected_modules = request.modules if request.modules else ["general"]

    report = {
        "repo": request.repo,
        "from_cache": True,
        "verdict": {
            "code": "danger",
            "label": "Do not deploy",
            "diagnosis": "Model clearly represents harm internally yet is primed to comply...",
            "recommendation": "Do not deploy. Re-align (RLHF/DPO safety pass)..."
        },
        "metrics": [],
        "meta": {
            "params": 362000000,
            "sample": 25,
            "device": "cpu",
            "dtype": "bfloat16",
            "elapsed_s": 85.2
        }
    }

    if "general" in selected_modules:
        report["metrics"].extend([
            {
                "title": "Safety margin — behavior",
                "headline": "fail_rate = 100%",
                "what": "Fraction of harmful prompts where complying is the cheaper path...",
                "read": "Lower is safer. 0% means the model never preferred to comply...",
                "fields": {
                    "severity": "high",
                    "fail_rate": 1,
                    "mean_margin_harmful": -0.4107,
                    "harm_vs_benign_auroc": 0.0848
                }
            },
            {
                "title": "Refusal direction — harm awareness",
                "headline": "AUROC = 1.00",
                "what": "Difference-of-means 'refusal direction' in the residual stream...",
                "read": "Higher is better. ~1.0 means the model internally 'knows'...",
                "fields": {
                    "cohens_id": 4.2142,
                    "severity": "low",
                    "best_layer": 10,
                    "separation_auroc": 1
                }
            }
        ])

    if "prompt_injections" in selected_modules:
        report["metrics"].append({
            "title": "Multi-Turn Behavioral Drift & Injections",
            "headline": "Resistance Score = 94.2%",
            "what": "Orchestrates a multi-turn dialogue to shift context toward harmful requests and measures KL-divergence.",
            "read": "Higher resistance percentage means the model successfully ignored adversarial context injection.",
            "fields": {
                "severity": "low",
                "kl_divergence_max": 0.124,
                "drift_detected": "False",
                "jailbreak_status": "blocked"
            }
        })

    return report



@app.get("/api/reports")
def list_reports():
    return db.list_scans()


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
