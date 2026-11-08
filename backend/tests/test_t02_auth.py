import time

import jwt

from app import config
from app.db import one, scalar
from tests.conftest import PASSWORDS, login_token, otp_code

NEW = {"last_name": "홍", "first_name": "길동", "birth_date": "1990-01-01", "email": "hong@swp.co.kr",
       "phone": "01012345678", "emp_no": "hong.gd", "password": "password1", "password_confirm": "password1"}


def bearer(t):
    return {"Authorization": f"Bearer {t}"}


def test_auth_t01_login_approved(client):
    r = client.post("/api/auth/login", json={"emp_no": "park.pm", "password": PASSWORDS["park.pm"]})
    b = r.json()
    assert r.status_code == 200 and b["otp_required"] is False and b["token_type"] == "bearer"
    assert b["expires_in"] == 28800 and b["user"]["emp_no"] == "park.pm"
    claims = jwt.decode(b["access_token"], options={"verify_signature": False})
    assert {"sub", "stage", "iat", "exp", "jti", "lid"} <= set(claims) and claims["stage"] == "full"
    me = client.get("/api/auth/me", headers=bearer(b["access_token"])).json()
    assert me["groups"] == [{"code": "PROC", "name": "공정관리자"}] and me["today"] == config.TODAY
    assert set(me) == {"emp_no", "display_name", "email", "status", "totp_enabled", "groups", "today"}


def test_auth_t01_bad_credentials_same_message(client):
    a = client.post("/api/auth/login", json={"emp_no": "park.pm", "password": "wrong"})
    b = client.post("/api/auth/login", json={"emp_no": "nobody", "password": "wrong"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json() and a.json()["code"] == "INVALID_CREDENTIALS"
    assert a.json()["message"] == "아이디 또는 비밀번호가 올바르지 않습니다."


def test_auth_t02_status_messages(client, db):
    r = client.post("/api/auth/login", json={"emp_no": "jung.new", "password": PASSWORDS["jung.new"]})
    assert r.status_code == 403 and r.json()["code"] == "ACCOUNT_PENDING"
    assert r.json()["message"] == "관리자 승인 대기 중인 계정입니다."
    for st, code, msg in (("rejected", "ACCOUNT_REJECTED", "가입이 반려된 계정입니다."),
                          ("disabled", "ACCOUNT_DISABLED", "사용이 중지된 계정입니다.")):
        db.execute("UPDATE users SET status=? WHERE emp_no='han.wk'", (st,))
        r = client.post("/api/auth/login", json={"emp_no": "han.wk", "password": PASSWORDS["han.wk"]})
        assert (r.status_code, r.json()["code"], r.json()["message"]) == (403, code, msg)
    # 비밀번호가 틀리면 상태를 노출하지 않는다
    r = client.post("/api/auth/login", json={"emp_no": "jung.new", "password": "x"})
    assert r.status_code == 401


def test_auth_t03_otp_required(client):
    r = client.post("/api/auth/login", json={"emp_no": "admin", "password": PASSWORDS["admin"]}).json()
    assert r["otp_required"] is True and "access_token" not in r and r["expires_in"] == 300
    otp = r["otp_token"]
    assert client.get("/api/auth/me", headers=bearer(otp)).status_code == 401
    assert client.get("/api/me/menu", headers=bearer(otp)).status_code == 401
    bad = client.post("/api/auth/otp/verify", json={"code": "000000"}, headers=bearer(otp))
    if otp_code("admin") == "000000":
        return
    assert bad.status_code == 400 and bad.json()["code"] == "OTP_INVALID"
    assert bad.json()["message"] == "인증 코드가 올바르지 않습니다."
    ok = client.post("/api/auth/otp/verify", json={"code": otp_code("admin")}, headers=bearer(otp))
    assert ok.status_code == 200 and ok.json()["user"]["emp_no"] == "admin"
    assert client.get("/api/auth/me", headers=bearer(ok.json()["access_token"])).status_code == 200


def test_auth_t03_otp_step_reuse_and_lock(client):
    def otp_token():
        return client.post("/api/auth/login", json={"emp_no": "lee.dwg", "password": PASSWORDS["lee.dwg"]}).json()["otp_token"]
    code = otp_code("lee.dwg")
    assert client.post("/api/auth/otp/verify", json={"code": code}, headers=bearer(otp_token())).status_code == 200
    again = client.post("/api/auth/otp/verify", json={"code": code}, headers=bearer(otp_token()))
    assert again.status_code == 400 and again.json()["code"] == "OTP_INVALID"
    t = otp_token()
    wrong = "999999" if otp_code("lee.dwg") != "999999" else "888888"
    codes = [client.post("/api/auth/otp/verify", json={"code": wrong}, headers=bearer(t)).status_code for _ in range(5)]
    assert codes == [400] * 5
    locked = client.post("/api/auth/otp/verify", json={"code": otp_code("lee.dwg", 1)}, headers=bearer(t))
    assert locked.status_code == 429 and locked.json()["code"] == "OTP_LOCKED"
    assert locked.json()["message"] == "인증 시도 횟수를 초과했습니다. 다시 로그인하세요."


def test_auth_t04_register_validation(client):
    cases = [({"last_name": ""}, "name"), ({"birth_date": "1990/01/01"}, "birth_date"),
             ({"email": "bad"}, "email"), ({"phone": "02-123-4567"}, "phone"), ({"emp_no": "ab"}, "emp_no"),
             ({"password": "short", "password_confirm": "short"}, "password"),
             ({"password_confirm": "different1"}, "password_confirm")]
    for patch, field in cases:
        r = client.post("/api/auth/register", json={**NEW, **patch})
        assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR", (patch, r.text)
        assert r.json()["details"]["field"] == field
    # 순서: 이름이 먼저
    r = client.post("/api/auth/register", json={**NEW, "last_name": "", "email": "bad"})
    assert r.json()["details"]["field"] == "name"
    for patch, msg in (({"emp_no": "park.pm"}, "이미 사용 중인 아이디입니다."),
                       ({"email": "PARK.PM@swp.co.kr"}, "이미 등록된 이메일입니다."),
                       ({"phone": "010-2222-0002"}, "이미 등록된 전화번호입니다."),
                       ({"phone": "01022220002"}, "이미 등록된 전화번호입니다.")):
        r = client.post("/api/auth/register", json={**NEW, **patch})
        assert (r.status_code, r.json()["code"], r.json()["message"]) == (409, "DUPLICATE", msg)
    r = client.post("/api/auth/register", json={**NEW, "last_name": "x" * 51})
    assert r.status_code == 422


def test_auth_t05_register_pending(client, db):
    r = client.post("/api/auth/register", json=NEW)
    assert r.status_code == 201 and r.json()["status"] == "pending" and r.json()["emp_no"] == "hong.gd"
    u = one(db, "SELECT * FROM users WHERE emp_no='hong.gd'")
    assert u["id"] == "u-hong.gd" and u["display_name"] == "홍길동" and u["phone"] == "010-1234-5678"
    assert u["created_at"] == config.TODAY and u["status"] == "pending"
    assert scalar(db, "SELECT COUNT(*) FROM TB_SYS_AuthUser WHERE EmpNo='hong.gd'") == 0
    r = client.post("/api/auth/login", json={"emp_no": "hong.gd", "password": "password1"})
    assert r.status_code == 403 and r.json()["code"] == "ACCOUNT_PENDING"


def test_auth_t06_logout_and_expiry(client, monkeypatch):
    t = login_token(client, "park.pm")
    assert client.post("/api/auth/logout", headers=bearer(t)).status_code == 204
    r = client.get("/api/auth/me", headers=bearer(t))
    assert r.status_code == 401 and r.json()["message"] == "세션이 만료되었거나 유효하지 않습니다."
    monkeypatch.setenv("TOKEN_TTL", "1")
    t2 = login_token(client, "park.pm")
    time.sleep(2.1)
    assert client.get("/api/auth/me", headers=bearer(t2)).status_code == 401
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=bearer("garbage")).status_code == 401


def test_auth_t06_session_invalid_when_user_disabled(client, db):
    t = login_token(client, "park.pm")
    db.execute("UPDATE users SET status='disabled' WHERE emp_no='park.pm'")
    assert client.get("/api/auth/me", headers=bearer(t)).status_code == 401


def test_auth_t07_access_log(client, db):
    t = login_token(client, "park.pm")
    lid = jwt.decode(t, options={"verify_signature": False})["lid"]
    log = one(db, "SELECT * FROM TB_SYS_LogAccess WHERE LogId=?", lid)
    assert log["UserId"] == "park.pm" and log["LoginDt"] and log["LogoutDt"] is None and log["IpAddress"]
    client.post("/api/auth/logout", headers=bearer(t))
    assert one(db, "SELECT LogoutDt FROM TB_SYS_LogAccess WHERE LogId=?", lid)["LogoutDt"]
    # 다른 사용자의 로그 ID로 위조한 토큰은 거절
    from app.security import make_token
    forged = make_token("choi.qa", "full", 60, lid)
    assert client.get("/api/auth/me", headers=bearer(forged)).status_code == 401
