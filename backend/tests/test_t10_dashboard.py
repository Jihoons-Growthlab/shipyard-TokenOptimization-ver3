from app.db import one
from tests.helpers import make_drawing, new_plan


def get(client, h):
    r = client.get("/api/dashboard/summary", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_dash_seed_values(client, auth):
    s = get(client, auth("choi.qa"))
    assert s["today"] == "2026-10-19"
    assert {k: v["value"] for k, v in s["kpi"].items()} == {"active_hulls": 4, "delay_plans": 1, "waiting_plans": 8,
                                                             "pending_drawings": 6}
    assert [h["progress"] for h in s["hull_progress"]] == [65, 17, 0, 0, 94]
    assert s["plan_status"] == [{"status": "PLAN", "count": 39}, {"status": "READY", "count": 0},
                                {"status": "WORK", "count": 7}, {"status": "DONE", "count": 36},
                                {"status": "DELAY", "count": 1}]
    assert s["waiting_list"]["count"] == 8 and all(i["blockers"] for i in s["waiting_list"]["items"])
    starts = [i["plan_start_dt"] for i in s["waiting_list"]["items"]]
    assert starts == sorted(starts)
    discs = [d["discipline"] for d in s["drawing_disciplines"]]
    order = ["HULL", "MACH", "ELEC", "PIPE", "OUTFIT"]
    assert discs == [c for c in order if c in discs] and all(d["total"] > 0 for d in s["drawing_disciplines"])


def test_dash_t01_progress_100_updates(client, auth, db):
    h = auth("park.pm")
    before = get(client, h)
    pid = one(db, "SELECT PlanId FROM TB_PRC_Plan WHERE HullNo='8001' AND PlanStatus='WORK' LIMIT 1")["PlanId"]
    client.put(f"/api/plans/{pid}/progress/2026-10-19", json={"progress_rate": 100}, headers=h)
    after = get(client, h)
    b, a = ({x["status"]: x["count"] for x in s["plan_status"]} for s in (before, after))
    assert a["DONE"] == b["DONE"] + 1 and sum(a.values()) == sum(b.values())
    assert one(db, "SELECT PlanStatus FROM TB_PRC_Plan WHERE PlanId=?", pid)["PlanStatus"] == "DONE"
    assert after["hull_progress"][0]["progress"] >= before["hull_progress"][0]["progress"]


def test_dash_t02_waiting_changes(client, auth, db):
    h = auth("park.pm")
    base = get(client, h)["kpi"]["waiting_plans"]["value"]
    p = new_plan(client, h, "8004", plan_start_dt="2026-11-01", plan_end_dt="2026-11-20")
    did = make_drawing(db, "8004", "8004-DASH-01")
    client.post(f"/api/plans/{p['plan_id']}/drawings", json={"drawing_id": did, "required": True}, headers=h)
    s = get(client, h)
    assert s["kpi"]["waiting_plans"]["value"] == base + 1
    assert any(i["plan_id"] == p["plan_id"] and i["blockers"] == ["8004-DASH-01"] for i in s["waiting_list"]["items"]) \
        or s["waiting_list"]["count"] > 6
    w = auth("lee.dwg")
    client.post(f"/api/drawings/{did}/revisions/0/request-approval",
                json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=w)
    for emp in ("lee.dwg", "admin"):
        a = next(x for x in client.get("/api/approvals/inbox", headers=auth(emp)).json()["waiting"] if x["drawing_id"] == did)
        client.post(f"/api/approvals/{a['approval_id']}/decision", json={"result": "APPROVE"}, headers=auth(emp))
    client.post(f"/api/drawings/{did}/revisions/0/issue", headers=w)
    assert get(client, h)["kpi"]["waiting_plans"]["value"] == base


def test_dash_t03_impact_window(client, auth, db):
    h = auth("choi.qa")
    items = get(client, h)["impact_list"]
    for i in items["items"]:
        assert "2026-09-19" <= i["issue_dt"] <= "2026-10-19" and i["rev_no"] >= 1
        assert i["plan_status"] in ("WORK", "DONE", "DELAY") and i["link"]["screen"] == "drawing"
    did = make_drawing(db, "8001", "8001-IMP-T", rev_status="ISSUED")
    db.execute("UPDATE TB_DWG_Revision SET RevStatus='OBSOLETE' WHERE DrawingId=?", (did,))
    db.execute("INSERT INTO TB_DWG_Revision(DrawingId, RevNo, RevStatus, ChangeDesc, IssueDt) VALUES (?,1,'ISSUED','개정',?)",
               (did, "2026-09-18"))
    work = one(db, "SELECT PlanId FROM TB_PRC_Plan WHERE HullNo='8001' AND PlanStatus='WORK' LIMIT 1")["PlanId"]
    plan_ = one(db, "SELECT PlanId FROM TB_PRC_Plan WHERE HullNo='8001' AND PlanStatus='PLAN' LIMIT 1")["PlanId"]
    db.execute("INSERT INTO TB_DWG_PlanLink(DrawingId, PlanId, RequiredYN) VALUES (?,?,0)", (did, work))
    db.execute("INSERT INTO TB_DWG_PlanLink(DrawingId, PlanId, RequiredYN) VALUES (?,?,0)", (did, plan_))
    assert get(client, h)["impact_list"]["count"] == items["count"]  # 31일 전: 제외
    db.execute("UPDATE TB_DWG_Revision SET IssueDt='2026-09-19' WHERE DrawingId=? AND RevNo=1", (did,))
    s = get(client, h)["impact_list"]
    assert s["count"] == items["count"] + 1  # WORK만 포함, PLAN 제외


def test_dash_t04_deliveries(client, auth, db):
    s = get(client, auth("choi.qa"))
    months = [d["month"] for d in s["deliveries"]]
    assert months == sorted(months)
    expected = {}
    for r in db.execute("SELECT HullNo, DeliveryDt FROM TB_MST_Hull WHERE UseYN=1 AND DeliveryDt IS NOT NULL"):
        expected.setdefault(r[1][:7], []).append(r[0])
    assert {d["month"]: d["hull_nos"] for d in s["deliveries"]} == expected
    assert all(d["count"] == len(d["hull_nos"]) for d in s["deliveries"])
    db.execute("UPDATE TB_MST_Hull SET UseYN=0 WHERE HullNo='8005'")
    s2 = get(client, auth("choi.qa"))
    assert "8005" not in [h["hull_no"] for h in s2["hull_progress"]]
    assert sum(d["count"] for d in s2["deliveries"]) == sum(d["count"] for d in s["deliveries"]) - 1


def test_dash_t05_links(client, auth):
    s = get(client, auth("choi.qa"))
    assert [s["kpi"][k]["link"]["screen"] for k in ("active_hulls", "delay_plans", "waiting_plans", "pending_drawings")] \
        == ["hull-list", "plan-gantt", "plan-gantt", "dwg-approval"]
    assert all(h["link"] == {"screen": "plan-gantt", "param": h["hull_no"]} for h in s["hull_progress"])
    for i in s["delay_list"]["items"] + s["waiting_list"]["items"]:
        assert i["link"] == {"screen": "plan-gantt", "param": i["hull_no"]} and i["label"].startswith("[")


def test_dash_t06_list_cap(client, auth):
    h = auth("park.pm")
    for i in range(7):
        new_plan(client, h, "8004", plan_start_dt="2026-09-01", plan_end_dt=f"2026-10-0{i + 1}")
    s = get(client, h)
    assert s["delay_list"]["count"] == 8 and len(s["delay_list"]["items"]) == 6
    assert s["kpi"]["delay_plans"]["value"] == 8


def test_dash_permission(client, auth, db):
    db.execute("DELETE FROM TB_SYS_AuthMenu WHERE MenuId='M00' AND AuthCd='VIEW'")
    assert client.get("/api/dashboard/summary", headers=auth("choi.qa")).status_code == 403
