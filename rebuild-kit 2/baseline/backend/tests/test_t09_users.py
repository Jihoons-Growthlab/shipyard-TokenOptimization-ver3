from app.db import one
from tests.conftest import login_token

NEW = {"last_name": "강", "first_name": "신규", "birth_date": "1992-02-02", "email": "kang@swp.co.kr",
       "phone": "010-7777-0007", "emp_no": "kang.new", "password": "password1"}


def test_usr_t01_filter(client, auth):
    h = auth("admin")
    r = client.get("/api/users", headers=h).json()
    assert r["total"] == 6 and r["pending"] == 1
    assert [u["emp_no"] for u in r["users"]] == sorted(u["emp_no"] for u in r["users"])  # 같은 가입일 → 아이디순
    p = client.get("/api/users", params={"status": "pending"}, headers=h).json()
    assert [u["emp_no"] for u in p["users"]] == ["jung.new"] and p["total"] == 1 and p["pending"] == 1
    for q, emp in (("정신", "jung.new"), ("PARK.PM@", "park.pm"), ("010-3333", "lee.dwg"), ("01044440004", "han.wk")):
        assert [u["emp_no"] for u in client.get("/api/users", params={"q": q}, headers=h).json()["users"]] == [emp], q
    u = client.get("/api/users/park.pm", headers=h).json()
    assert u["groups"] == [{"code": "PROC", "name": "공정관리자"}]
    r = client.get("/api/users/ghost", headers=h)
    assert (r.status_code, r.json()["code"], r.json()["message"]) == (404, "USER_NOT_FOUND", "사용자를 찾을 수 없습니다.")
    assert [g["code"] for g in client.get("/api/auth-groups", headers=h).json()] == ["ADMIN", "DWG", "PROC", "VIEW"]


def test_usr_t02_validation(client, auth):
    h = auth("admin")
    for patch, field, status in (({"email": "x"}, "email", 400), ({"emp_no": "a"}, "emp_no", 400),
                                 ({"password": "short"}, "password", 400), ({"status": "weird"}, "status", 400),
                                 ({"groups": ["NOPE"]}, "groups", 400), ({"emp_no": "admin"}, "emp_no", 409),
                                 ({"email": "ADMIN@swp.co.kr"}, "email", 409), ({"phone": "01011110001"}, "phone", 409)):
        r = client.post("/api/users", json={**NEW, **patch}, headers=h)
        assert (r.status_code, r.json()["details"].get("field")) == (status, field), patch
    assert client.post("/api/users", json={**NEW, "first_name": "x" * 51}, headers=h).status_code == 422
    r = client.post("/api/users", json={**NEW, "groups": ["VIEW"]}, headers=h)
    assert r.status_code == 201 and r.json()["status"] == "approved" and r.json()["groups"][0]["code"] == "VIEW"
    assert r.json()["display_name"] == "강신규"
    # 본인 이메일·전화는 중복 아님
    r = client.patch("/api/users/kang.new", json={"email": "kang@swp.co.kr", "phone": "01077770007"}, headers=h)
    assert r.status_code == 200
    r = client.patch("/api/users/kang.new", json={"email": "park.pm@swp.co.kr"}, headers=h)
    assert r.status_code == 409
    r = client.patch("/api/users/kang.new", json={"emp_no": "other"}, headers=h)
    assert (r.status_code, r.json()["message"]) == (400, "아이디는 변경할 수 없습니다.")


def test_usr_t03_empty_password_keeps_hash(client, auth, db):
    h = auth("admin")
    before = one(db, "SELECT password_hash FROM users WHERE emp_no='park.pm'")["password_hash"]
    r = client.patch("/api/users/park.pm", json={"password": "", "first_name": "공정2"}, headers=h)
    assert r.status_code == 200 and r.json()["display_name"] == "박공정2"
    assert one(db, "SELECT password_hash FROM users WHERE emp_no='park.pm'")["password_hash"] == before
    client.patch("/api/users/park.pm", json={"password": "newpass99"}, headers=h)
    assert client.post("/api/auth/login", json={"emp_no": "park.pm", "password": "newpass99"}).status_code == 200
    assert client.patch("/api/users/park.pm", json={"password": "short"}, headers=h).status_code == 400


def test_usr_t04_group_change_immediate(client, auth):
    h = auth("admin")
    qa = auth("choi.qa")
    assert "M22" in [m["menu_id"] for m in client.get("/api/me/menu", headers=qa).json()]
    client.patch("/api/users/choi.qa", json={"groups": ["DWG"]}, headers=h)
    menu = [m["menu_id"] for m in client.get("/api/me/menu", headers=qa).json()]
    assert "M22" not in menu and "M33" in menu
    r = client.patch("/api/users/choi.qa", json={"groups": []}, headers=h)
    assert r.json()["groups"] == [] and client.get("/api/me/menu", headers=qa).json() == []


def test_usr_t05_approve_then_login(client, auth):
    h = auth("admin")
    r = client.post("/api/users/jung.new/approve", json={"groups": []}, headers=h)
    assert (r.status_code, r.json()["message"]) == (400, "승인 시 권한 그룹을 1개 이상 지정하세요.")
    r = client.post("/api/users/jung.new/approve", json={"groups": ["VIEW"]}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert login_token(client, "jung.new")
    r = client.post("/api/users/jung.new/approve", json={"groups": ["VIEW"]}, headers=h)
    assert (r.status_code, r.json()["code"], r.json()["message"]) == (409, "INVALID_STATUS", "승인 대기 상태가 아닙니다.")
    assert client.post("/api/users/jung.new/reject", headers=h).status_code == 409


def test_usr_reject(client, auth):
    r = client.post("/api/users/jung.new/reject", headers=auth("admin"))
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    r = client.post("/api/auth/login", json={"emp_no": "jung.new", "password": "new12345"})
    assert r.json()["code"] == "ACCOUNT_REJECTED"


def test_usr_t06_self_delete(client, auth, db):
    h = auth("admin")
    r = client.delete("/api/users/admin", headers=h)
    assert (r.status_code, r.json()["code"], r.json()["message"]) == (409, "SELF_DELETE", "로그인 중인 본인 계정은 삭제할 수 없습니다.")
    assert client.delete("/api/users/park.pm", headers=h).status_code == 204
    assert one(db, "SELECT COUNT(*) n FROM TB_SYS_AuthUser WHERE EmpNo='park.pm'")["n"] == 0
    assert one(db, "SELECT COUNT(*) n FROM TB_PRC_Plan WHERE ManagerEmpNo='park.pm'")["n"] == 0
    assert one(db, "SELECT COUNT(*) n FROM TB_PRC_Plan")["n"] == 83
    assert client.delete("/api/users/park.pm", headers=h).status_code == 404


def test_usr_t07_non_admin_forbidden(client, auth):
    for emp in ("park.pm", "lee.dwg", "choi.qa"):
        h = auth(emp)
        assert client.get("/api/users", headers=h).status_code == 403
        assert client.post("/api/users", json=NEW, headers=h).status_code == 403
        assert client.post("/api/users/jung.new/approve", json={"groups": ["VIEW"]}, headers=h).status_code == 403
        assert client.get("/api/auth-groups", headers=h).status_code == 403
        assert client.get("/api/users/options", headers=h).status_code == 200


def test_usr_t08_secret_hidden_and_otp(client, auth, db):
    h = auth("admin")
    text = client.get("/api/users", headers=h).text + client.get("/api/users/admin", headers=h).text
    assert "password_hash" not in text and "totp_secret" not in text and "JBSWY3DP" not in text
    r = client.post("/api/users", json={**NEW, "totp_enabled": True}, headers=h)
    assert (r.status_code, r.json()["code"]) == (409, "OTP_NOT_ENROLLED")
    r = client.patch("/api/users/park.pm", json={"totp_enabled": True}, headers=h)
    assert (r.status_code, r.json()["code"]) == (409, "OTP_NOT_ENROLLED")
    r = client.patch("/api/users/lee.dwg", json={"totp_enabled": False}, headers=h)
    assert r.json()["totp_enabled"] is False
    assert one(db, "SELECT totp_secret FROM users WHERE emp_no='lee.dwg'")["totp_secret"]
    assert client.patch("/api/users/lee.dwg", json={"totp_enabled": True}, headers=h).json()["totp_enabled"] is True
