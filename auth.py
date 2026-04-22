# auth.py — Autentikasi untuk BatikCraft / Risena
# ─────────────────────────────────────────────────────
# File BARU — tidak mengubah kode yang sudah ada
# ─────────────────────────────────────────────────────
import hashlib
import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ─────────────────────────────────────────────────────
# KONFIGURASI USER
# Tambah / ubah user di sini, format: username → sha256(password)
# Default: admin / admin123
# ─────────────────────────────────────────────────────
def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

_USERS: dict[str, str] = {
    "admin": _hash("admin123"),
    # "risena": _hash("passwordku"),  # tambah user lain di sini
}

# Token aktif disimpan in-memory (reset saat server restart)
_active_tokens: dict[str, str] = {}   # token → username


# ─────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────
class LoginIn(BaseModel):
    username: str
    password: str


# ─────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────
@router.post("/login")
def login(body: LoginIn) -> dict:
    """Verifikasi kredensial dan kembalikan token sesi."""
    pw_hash = _hash(body.password)
    if _USERS.get(body.username.strip()) != pw_hash:
        raise HTTPException(status_code=401, detail="Username atau password salah")
    token = secrets.token_hex(32)
    _active_tokens[token] = body.username.strip()
    return {"token": token, "username": body.username.strip()}


@router.post("/logout")
def logout(token: str = "") -> dict:
    """Hapus token sesi (logout)."""
    _active_tokens.pop(token, None)
    return {"ok": True}


@router.get("/check")
def check_token(token: str = "") -> dict:
    """Cek apakah token masih valid."""
    username = _active_tokens.get(token)
    if not username:
        raise HTTPException(status_code=401, detail="Sesi tidak valid atau sudah habis")
    return {"ok": True, "username": username}
