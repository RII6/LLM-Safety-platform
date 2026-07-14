from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional
import threading
import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as _HTTPExc
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import auth, config, db
from .scan import ScanError, scan

STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()  # create the scans, users and user_scans tables if they don't exist yet
    if config.AUTH_SECRET == "dev-insecure-change-me":
        print("[auth] WARNING: using the default AUTH_SECRET — set AUTH_SECRET before deploying.", flush=True)
    yield


app = FastAPI(title="LLM Safety Scanner", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.AUTH_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── auth models ─────────────────────────────────────────────────────────────────


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    email: Optional[str] = Field(default=None, max_length=254)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("invalid email address")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    created_at: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut


# ── scan models ─────────────────────────────────────────────────────────────────

class GenerationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = False
    n: int = Field(default=5, ge=0, le=50)
    provider: Literal["groq", "google"] = "groq"
    model: Optional[str] = Field(default=None, max_length=100)
    seed: int = Field(default=0, ge=0)
    class_name: Literal["harmful", "benign", "both"] = Field(default="harmful", alias="class")

    @field_validator("model")
    @classmethod
    def _normalize_model(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None


class ScanRequest(BaseModel):
    repo: str
    force: bool = False
    modules: list[str] = Field(default_factory=lambda: ["general"])
    sample: Optional[int] = None
    generation: Optional[GenerationRequest] = None

    @field_validator('sample')
    @classmethod
    def validate_sample(cls, v):
        if v is not None and (v < 1 or v > 200):
            raise ValueError('Sample size must be between 1 and 200')
        return v

# ── auth routes ─────────────────────────────────────────────────────────────────


@app.post("/api/auth/signup", response_model=AuthResponse, status_code=201)
def signup(req: SignupRequest):
    try:
        user = db.create_user(req.username, req.email, auth.hash_password(req.password))
    except db.UserExists:
        raise HTTPException(status_code=409, detail="Username or email is already taken.")
    token = auth.create_token(user["id"], user["username"])
    return {"token": token, "user": user}


@app.post("/api/auth/login", response_model=AuthResponse)
def login(req: LoginRequest):
    user = db.get_user_by_username(req.username)
    if user is None or not auth.verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = auth.create_token(user["id"], user["username"])
    return {"token": token, "user": user}


@app.get("/api/auth/me", response_model=UserOut)
def me(user: dict = Depends(auth.get_current_user)):
    return user


# ── async scan jobs ─────────────────────────────────────────────────────────────
# A scan takes minutes on this CPU-only host. Running it synchronously makes the
# reverse proxy time out and return an HTML error page, which the frontend can't
# JSON.parse. So POST /api/scan starts the scan in a background thread and returns
# a job id immediately; the client polls GET /api/scan/status/{job_id} for the
# verdict. scan()'s own lock still serialises the actual compute.

_JOBS: dict = {}
_JOBS_LOCK = threading.Lock()
_MAX_JOBS = 200


def _set_job(job_id: str, value: dict) -> None:
    with _JOBS_LOCK:
        if job_id not in _JOBS:
            _JOBS[job_id] = {}
        _JOBS[job_id].update(value)
        if len(_JOBS) > _MAX_JOBS:  # bound memory: drop oldest
            for k in list(_JOBS)[: len(_JOBS) - _MAX_JOBS]:
                _JOBS.pop(k, None)


def _run_job(job_id: str, repo: str, force: bool, modules: list, user_id, sample=None, generation=None) -> None:
    def log_cb(msg):
        with _JOBS_LOCK:
            if job_id in _JOBS:
                if "logs" not in _JOBS[job_id]:
                    _JOBS[job_id]["logs"] = []
                _JOBS[job_id]["logs"].append(msg)

    try:
        result = scan(
            repo,
            force=force,
            modules=modules,
            user_id=user_id,
            sample=sample,
            generation=generation,
            log_cb=log_cb,
        )
        _set_job(job_id, {"status": "done", "result": result})
    except ScanError as e:
        _set_job(job_id, {"status": "error", "error": e.message, "code": e.status})
    except Exception as e:  # never leave a job stuck on "running"
        _set_job(job_id, {"status": "error", "error": str(e), "code": 500})


@app.get("/api/health")
def health():
    return {"ok": True, "demo_model": config.DEMO_MODEL, "sample": config.SAMPLE}


@app.post("/api/scan", status_code=202)
def run_scan(req: ScanRequest, user: Optional[dict] = Depends(auth.get_current_user_optional)):
    user_id = user["id"] if user else None
    generation = req.generation.model_dump(by_alias=True) if req.generation else None
    job_id = uuid.uuid4().hex
    _set_job(job_id, {"status": "running", "logs": []})
    threading.Thread(
        target=_run_job,
        args=(job_id, req.repo, req.force, req.modules, user_id, req.sample, generation),
        daemon=True,
    ).start()
    return {"job_id": job_id, "status": "running"}


@app.get("/api/scan/status/{job_id}")
def scan_status(job_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"error": "Unknown or expired job."})
    return job


@app.get("/api/reports")
def list_reports(user: dict = Depends(auth.get_current_user)):
    return db.list_scans(user_id=user["id"])


@app.get("/api/reports/{scan_id}")
def get_scan(scan_id: int):
    report = db.get_scan_by_id(scan_id)
    if report is None:
        return JSONResponse(status_code=404, content={"error": "Scan not found"})
    report["id"] = scan_id
    return report


class _SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except _HTTPExc as exc:
            if exc.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise


app.mount("/", _SPAStaticFiles(directory=STATIC, html=True), name="static")
