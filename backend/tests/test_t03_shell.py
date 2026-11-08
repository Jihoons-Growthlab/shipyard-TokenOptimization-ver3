from app.db import scalar
from app.services import shell


def test_shell_t01_menu_by_group(client, auth):
    menu = client.get("/api/me/menu", headers=auth("park.pm")).json()
    ids = [m["menu_id"] for m in menu]
    assert ids == ["M00", "M10", "M11", "M20", "M21", "M22", "M30", "M31"]
    m11 = next(m for m in menu if m["menu_id"] == "M11")
    assert m11 == {"menu_id": "M11", "parent_id": "M10", "title": "호선 목록", "token": "hull-list", "seq": 3,
                   "level": 2, "auth_gbn": "Write", "can_write": True}
    qa = {m["menu_id"]: m for m in client.get("/api/me/menu", headers=auth("choi.qa")).json()}
    assert "M91" not in qa and qa["M11"]["can_write"] is False
    dwg = [m["menu_id"] for m in client.get("/api/me/menu", headers=auth("lee.dwg")).json()]
    assert "M22" not in dwg and "M33" in dwg
    admin = [m["menu_id"] for m in client.get("/api/me/menu", headers=auth("admin")).json()]
    assert len(admin) == 11


def test_shell_t01_hidden_parent_hides_child(client, auth, db):
    db.execute("UPDATE TB_SYS_MenuInfo SET UseYN=0 WHERE MenuId='M20'")
    ids = [m["menu_id"] for m in client.get("/api/me/menu", headers=auth("park.pm")).json()]
    assert "M21" not in ids and "M22" not in ids


def test_shell_t01_menu_access_log_and_403(client, auth, db):
    r = client.post("/api/me/menu-access", json={"menu_id": "M91"}, headers=auth("park.pm"))
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN" and r.json()["details"]["menu_id"] == "M91"
    assert client.post("/api/me/menu-access", json={"menu_id": "M21"}, headers=auth("park.pm")).status_code == 204
    assert scalar(db, "SELECT COUNT(*) FROM TB_SYS_LogMenuAccess WHERE MenuId='M21'") == 1


def test_permission_change_immediate(client, auth, db):
    h = auth("choi.qa")
    assert client.post("/api/me/menu-access", json={"menu_id": "M91"}, headers=h).status_code == 403
    db.execute("INSERT INTO TB_SYS_AuthUser(AuthCd, EmpNo) VALUES ('ADMIN','choi.qa')")
    assert client.post("/api/me/menu-access", json={"menu_id": "M91"}, headers=h).status_code == 204


def test_codes(client, auth):
    c = client.get("/api/codes", headers=auth("park.pm")).json()
    assert [x["code"] for x in c["PLANSTAT"]] == ["PLAN", "READY", "WORK", "DONE", "DELAY"]
    assert c["DWGDISC"][0] == {"code": "HULL", "name": "선체"}
    assert client.get("/api/codes").status_code == 401


def test_weather_t01_regions(client, auth):
    h = auth("park.pm")
    for region, temp, cond in (("울산", 17.6, "맑음"), ("거제", 18.9, "구름조금"), ("목포", 16.2, "흐림")):
        w = client.get("/api/weather", params={"region": region}, headers=h).json()
        assert (w["region"], w["tempC"], w["condition"], w["source"]) == (region, temp, cond, "SAMPLE")
        assert w["error"]
    assert client.get("/api/weather", headers=h).json()["region"] == "울산"
    r = client.get("/api/weather", params={"region": "서울"}, headers=h)
    assert r.status_code == 400 and r.json()["details"]["field"] == "region"
    assert client.get("/api/weather").status_code == 401


def test_weather_t02_fallback_and_live(client, auth, monkeypatch):
    h = auth("park.pm")
    monkeypatch.setenv("WEATHER_PROVIDER", "missing")
    w = client.get("/api/weather", headers=h).json()
    assert w["source"] == "SAMPLE" and "missing" in w["error"]

    def boom(region):
        raise RuntimeError("timeout")
    monkeypatch.setitem(shell.PROVIDERS, "boom", boom)
    monkeypatch.setenv("WEATHER_PROVIDER", "boom")
    w = client.get("/api/weather", headers=h).json()
    assert w["source"] == "SAMPLE" and "timeout" in w["error"]
    monkeypatch.setitem(shell.PROVIDERS, "boom", lambda r: {"tempC": "x"})
    assert client.get("/api/weather", headers=h).json()["source"] == "SAMPLE"
    monkeypatch.setitem(shell.PROVIDERS, "boom", lambda r: {"obsDt": "2026-10-19 09:00", "tempC": 10.0,
                                                             "condition": "비", "humidity": 90, "windMs": 2.0})
    w = client.get("/api/weather", headers=h).json()
    assert w["source"] == "LIVE" and w["condition"] == "비" and w["error"] is None


def test_user_options(client, auth):
    opts = client.get("/api/users/options", headers=auth("lee.dwg")).json()
    assert "jung.new" not in [o["emp_no"] for o in opts] and set(opts[0]) == {"emp_no", "display_name"}
