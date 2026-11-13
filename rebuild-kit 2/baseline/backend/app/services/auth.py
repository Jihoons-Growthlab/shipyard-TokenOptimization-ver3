"""F01 인증."""
from .. import config
from ..db import one, tx
from ..errors import ApiError, unauthorized
from ..security import check_otp, hash_password, make_token, otp_locked, verify_password
from .common import now_utc
from .members import groups_of, normalize_phone, validate_member

_STATUS_ERRORS = {
    "pending": ("ACCOUNT_PENDING", "관리자 승인 대기 중인 계정입니다."),
    "rejected": ("ACCOUNT_REJECTED", "가입이 반려된 계정입니다."),
    "disabled": ("ACCOUNT_DISABLED", "사용이 중지된 계정입니다."),
}
REGISTER_MESSAGE = "가입 신청 완료. 관리자 승인 후 로그인할 수 있습니다."


def me(conn, user: dict) -> dict:
    return {"emp_no": user["emp_no"], "display_name": user["display_name"], "email": user["email"],
            "status": user["status"], "totp_enabled": bool(user["totp_enabled"]),
            "groups": groups_of(conn, user["emp_no"]), "today": config.TODAY}


def _check_status(user: dict) -> None:
    if user["status"] in _STATUS_ERRORS:
        code, msg = _STATUS_ERRORS[user["status"]]
        raise ApiError(403, code, msg)


def _start_session(conn, user: dict, ip: str | None) -> dict:
    with tx(conn):
        cur = conn.execute("INSERT INTO TB_SYS_LogAccess(UserId, LoginDt, IpAddress) VALUES (?,?,?)",
                           (user["emp_no"], now_utc(), ip))
    ttl = config.token_ttl()
    return {"otp_required": False, "access_token": make_token(user["emp_no"], "full", ttl, cur.lastrowid),
            "token_type": "bearer", "expires_in": ttl, "user": me(conn, user)}


def login(conn, emp_no: str, password: str, ip: str | None) -> dict:
    user = one(conn, "SELECT * FROM users WHERE emp_no=?", (emp_no or "").strip())
    if not user or not verify_password(user["password_hash"], password or ""):
        raise ApiError(401, "INVALID_CREDENTIALS", "아이디 또는 비밀번호가 올바르지 않습니다.")
    _check_status(user)
    if user["totp_enabled"]:
        ttl = config.otp_token_ttl()
        return {"otp_required": True, "otp_token": make_token(user["emp_no"], "otp", ttl), "expires_in": ttl}
    return _start_session(conn, user, ip)


def verify_otp(conn, payload: dict, code: str, ip: str | None) -> dict:
    if payload.get("stage") != "otp":
        raise unauthorized()
    user = one(conn, "SELECT * FROM users WHERE emp_no=?", payload["sub"])
    if not user:
        raise unauthorized()
    _check_status(user)
    if otp_locked(payload["jti"]):
        raise ApiError(429, "OTP_LOCKED", "인증 시도 횟수를 초과했습니다. 다시 로그인하세요.")
    if not check_otp(user["emp_no"], user["totp_secret"], code, payload["jti"]):
        raise ApiError(400, "OTP_INVALID", "인증 코드가 올바르지 않습니다.", {"field": "code"})
    return _start_session(conn, user, ip)


def logout(conn, user: dict) -> None:
    with tx(conn):
        conn.execute("UPDATE TB_SYS_LogAccess SET LogoutDt=? WHERE LogId=?", (now_utc(), user["lid"]))


def register(conn, d: dict) -> dict:
    d = {**d, "password_confirm": d.get("password_confirm") or ""}
    validate_member(conn, d, creating=True)
    emp_no = d["emp_no"].strip()
    last, first = d["last_name"].strip(), d["first_name"].strip()
    with tx(conn):
        conn.execute(
            "INSERT INTO users(id,email,password_hash,display_name,emp_no,status,auth_provider,last_name,first_name,"
            "birth_date,phone,totp_enabled,totp_secret,created_at) VALUES (?,?,?,?,?,'pending','local',?,?,?,?,0,NULL,?)",
            ("u-" + emp_no, d["email"].strip(), hash_password(d["password"]), last + first, emp_no, last, first,
             d["birth_date"], normalize_phone(d["phone"]), config.TODAY))
    return {"emp_no": emp_no, "status": "pending", "message": REGISTER_MESSAGE}
