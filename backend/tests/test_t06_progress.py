from app.db import scalar
from tests.helpers import new_plan


def test_prog_t01_targets(client, auth):
    h = auth("park.pm")
    ph = client.get("/api/progress-hulls", headers=h).json()
    assert ph["default_hull_no"] == "8001" and ph["hulls"][0]["hull_status"] == "BUILD"
    t = client.get("/api/hulls/8001/progress-targets", headers=h).json()
    assert t["today"] == "2026-10-19" and t["plans"]
    assert {p["plan_status"] for p in t["plans"]} <= {"READY", "WORK", "DELAY"}
    full = client.get("/api/hulls/8001/progress-targets", params={"include_done": "true"}, headers=h).json()
    assert len(full["plans"]) > len(t["plans"]) and "DONE" in {p["plan_status"] for p in full["plans"]}
    assert set(full["plans"][0]) == {"plan_id", "label", "plan_start_dt", "plan_end_dt", "actual_start_dt",
                                     "actual_end_dt", "progress_rate", "plan_status", "manager_emp_no",
                                     "manager_nm", "drawing_wait"}


def test_prog_t02_same_day_upsert(client, auth, db):
    h = auth("park.pm")
    p = new_plan(client, h, "8004", plan_start_dt="2026-10-01", plan_end_dt="2026-11-30")
    url = f"/api/plans/{p['plan_id']}/progress/2026-10-10"
    client.put(url, json={"progress_rate": 20, "man_hour": 8, "worker_cnt": 2, "worker_emp_no": "han.wk"}, headers=h)
    r = client.put(url, json={"progress_rate": 25, "man_hour": 10, "worker_emp_no": "han.wk", "remark": "수정"}, headers=h)
    assert r.status_code == 200
    hist = r.json()["history"]
    assert len(hist) == 1 and hist[0]["progress_rate"] == 25 and hist[0]["worker_nm"] == "한현장"
    assert scalar(db, "SELECT COUNT(*) FROM TB_PRC_Progress WHERE PlanId=?", p["plan_id"]) == 1


def test_prog_t03_last_day_rate(client, auth):
    h = auth("park.pm")
    p = new_plan(client, h, "8004", plan_start_dt="2026-10-01", plan_end_dt="2026-11-30")
    base = f"/api/plans/{p['plan_id']}/progress/"
    client.put(base + "2026-10-05", json={"progress_rate": 30}, headers=h)
    client.put(base + "2026-10-12", json={"progress_rate": 50}, headers=h)
    r = client.put(base + "2026-10-08", json={"progress_rate": 90}, headers=h).json()
    assert r["plan"]["progress_rate"] == 50 and r["plan"]["actual_start_dt"] == "2026-10-05"
    assert [x["work_dt"] for x in r["history"]] == ["2026-10-12", "2026-10-08", "2026-10-05"]
    # 역행·음수 공수 허용
    r = client.put(base + "2026-10-15", json={"progress_rate": 10, "man_hour": -2}, headers=h)
    assert r.status_code == 200 and r.json()["plan"]["progress_rate"] == 10


def test_prog_t04_validation(client, auth):
    h = auth("park.pm")
    p = new_plan(client, h, "8004", plan_start_dt="2026-10-01", plan_end_dt="2026-11-30")
    base = f"/api/plans/{p['plan_id']}/progress/"
    cases = [("2026-10-20", {"progress_rate": 10}, "미래 일자의 실적은 입력할 수 없습니다."),
             ("2026-13-01", {"progress_rate": 10}, "작업일을 입력하세요."),
             ("2026-10-10", {"progress_rate": 101}, "진척률은 0~100 사이로 입력하세요."),
             ("2026-10-10", {"progress_rate": -1}, "진척률은 0~100 사이로 입력하세요."),
             ("2026-10-10", {}, "진척률은 0~100 사이로 입력하세요."),
             ("2026-10-10", {"progress_rate": 5, "worker_emp_no": "jung.new"}, "승인된 회원만 작업자로 지정할 수 있습니다.")]
    for dt, body, msg in cases:
        r = client.put(base + dt, json=body, headers=h)
        assert (r.status_code, r.json()["message"]) == (400, msg), (dt, body)
    assert client.put("/api/plans/99999/progress/2026-10-10", json={"progress_rate": 1}, headers=h).status_code == 404


def test_prog_t05_done_and_revert(client, auth, db):
    h = auth("park.pm")
    p = new_plan(client, h, "8004", plan_start_dt="2026-10-01", plan_end_dt="2026-11-30")
    base = f"/api/plans/{p['plan_id']}/progress/"
    client.put(base + "2026-10-05", json={"progress_rate": 40}, headers=h)
    r = client.put(base + "2026-10-18", json={"progress_rate": 100}, headers=h).json()
    assert r["plan"]["plan_status"] == "DONE" and r["plan"]["actual_end_dt"] == "2026-10-18"
    last = r["history"][0]["progress_id"]
    r = client.delete(f"/api/progress/{last}", headers=h).json()
    assert r["plan"]["plan_status"] == "WORK" and r["plan"]["actual_end_dt"] is None and r["plan"]["progress_rate"] == 40
    r = client.delete(f"/api/progress/{r['history'][0]['progress_id']}", headers=h).json()
    assert r["plan"]["progress_rate"] == 0 and r["plan"]["actual_start_dt"] is None and r["history"] == []
    assert r["plan"]["plan_status"] in ("PLAN", "READY")
    r = client.delete(f"/api/progress/{last}", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "PROGRESS_NOT_FOUND"


def test_prog_t06_view_forbidden(client, auth):
    h = auth("choi.qa")
    assert client.get("/api/progress-hulls", headers=h).status_code == 200
    assert client.get("/api/plans/10/progress", headers=h).status_code == 200
    r = client.put("/api/plans/10/progress/2026-10-18", json={"progress_rate": 70}, headers=h)
    assert r.status_code == 403 and r.json()["details"]["menu_id"] == "M22"
    assert client.delete("/api/progress/1", headers=h).status_code == 403
    assert client.get("/api/progress-hulls", headers=auth("lee.dwg")).status_code == 403
