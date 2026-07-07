from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

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
    email: str | None = Field(default=None, max_length=254)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str | None) -> str | None:
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
    email: str | None = None
    created_at: str | None = None


class AuthResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut


# ── scan models ─────────────────────────────────────────────────────────────────


class ScanRequest(BaseModel):
    repo: str
    force: bool = False


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


# ── scan routes (require a logged-in user) ──────────────────────────────────────


@app.get("/api/health")
def health():
    return {"ok": True, "demo_model": config.DEMO_MODEL, "sample": config.SAMPLE}


@app.post("/api/scan")
def run_scan(req: ScanRequest, user: dict = Depends(auth.get_current_user)):
    try:
        return scan(req.repo, force=req.force, user_id=user["id"])
    except ScanError as e:
        return JSONResponse(status_code=e.status, content={"error": e.message})


@app.get("/api/reports")
def list_reports(user: dict = Depends(auth.get_current_user)):
    return db.list_scans(user_id=user["id"])


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
