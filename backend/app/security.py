"""비밀번호(Argon2id), JWT(HS256), TOTP(RFC 6238)."""
import base64
import hashlib
import hmac
import struct
import time
import uuid

import jwt
from argon2 import PasswordHasher

from . import config

_ph = PasswordHasher()  # Argon2id


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw_hash: str, pw: str) -> bool:
    try:
        return _ph.verify(pw_hash, pw)
    except Exception:
        return False


def make_token(sub: str, stage: str, ttl: int, lid: int | None = None) -> str:
    now = int(time.time())
    payload = {"sub": sub, "stage": stage, "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex}
    if lid is not None:
        payload["lid"] = lid
    return jwt.encode(payload, config.app_secret(), algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, config.app_secret(), algorithms=["HS256"],
                          options={"require": ["sub", "stage", "iat", "exp", "jti"]})
    except jwt.PyJWTError:
        return None


# ---- TOTP
STEP = 30
MAX_OTP_FAILS = 5
_used_steps: dict[str, set[int]] = {}
_fails: dict[str, int] = {}


def totp(secret: str, step: int) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[off:off + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def current_step(at: float | None = None) -> int:
    return int((time.time() if at is None else at) // STEP)


def otp_locked(jti: str) -> bool:
    return _fails.get(jti, 0) >= MAX_OTP_FAILS


def check_otp(emp_no: str, secret: str | None, code: str, jti: str) -> bool:
    """±1 step 허용, 같은 사용자의 이미 쓴 step은 거절. 실패 시 토큰별 카운터 증가."""
    code = (code or "").strip()
    used = _used_steps.setdefault(emp_no, set())
    if secret and len(code) == 6 and code.isdigit():
        now = current_step()
        for step in (now, now - 1, now + 1):
            if step not in used and hmac.compare_digest(totp(secret, step), code):
                used.add(step)
                return True
    _fails[jti] = _fails.get(jti, 0) + 1
    return False


def reset_state() -> None:
    _used_steps.clear()
    _fails.clear()
