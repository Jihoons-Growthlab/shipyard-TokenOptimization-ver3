from app.db import scalar
from tests.helpers import make_drawing, new_plan, orphan_counts, recalc


def test_plan_t01_gantt(client, auth):
    h = auth("choi.qa")
    g = client.get("/api/hulls/8001/plans", headers=h).json()
    assert g["hull_no"] == "8001" and g["today"] == "2026-10-19" and g["hull_progress"] == 65
    plans = g["plans"]
    assert {"label", "block_cd", "pred_plan_ids", "gate_ok", "blockers", "drawing_wait", "manager_nm"} <= set(plans[0])
    cds = [p["block_cd"] for p in plans]
    nums = [int(c) for c in cds if c is not None]
    assert nums == sorted(nums)
    if None in cds:
        assert all(c is None for c in cds[cds.index(None):])
        assert next(p for p in plans if p["block_cd"] is None)["label"].startswith("[호선] ")
    assert plans[0]["label"] == f"[{plans[0]['block_cd']}] {plans[0]['proc_nm']}"
    ids = {p["plan_id"] for p in plans}
    assert all(d["plan_id"] in ids and d["pred_plan_id"] in ids for d in g["deps"])
    f = client.get("/api/hulls/8001/plans", params={"block_id": 1}, headers=h).json()
    assert {p["block_id"] for p in f["plans"]} == {1} and f["hull_progress"] == 65
    hulls = client.get("/api/plan-hulls", headers=h).json()
    assert hulls[0] == {"hull_no": "8001", "hull_nm": "SWP LNG 174K 1호", "plan_count": len(plans)}
    procs = client.get("/api/procs", headers=h).json()
    assert [p["proc_cd"] for p in procs][:2] == ["CUT", "SUBASM"]


def test_plan_t02_validation(client, auth):
    h = auth("park.pm")
    base = {"proc_cd": "CUT", "plan_start_dt": "2026-11-01", "plan_end_dt": "2026-11-14"}
    cases = [({"plan_start_dt": None}, "계획 시작/종료일을 입력하세요."),
             ({"plan_end_dt": "2026-10-01"}, "계획 종료일이 시작일보다 빠릅니다."),
             ({"block_id": 6}, "해당 호선의 블록이 아닙니다."),
             ({"proc_cd": "NOPE"}, "허용되지 않는 공정 코드입니다."),
             ({"manager_emp_no": "jung.new"}, "승인된 회원만 담당자로 지정할 수 있습니다."),
             ({"manager_emp_no": "ghost"}, "승인된 회원만 담당자로 지정할 수 있습니다.")]
    for patch, msg in cases:
        r = client.post("/api/hulls/8001/plans", json={**base, **patch}, headers=h)
        assert (r.status_code, r.json()["message"]) == (400, msg), patch
    p = new_plan(client, h, "8001", block_id=1, manager_emp_no="han.wk", remark="메모")
    assert p["plan_status"] in ("PLAN", "READY") and p["progress_rate"] == 0 and p["manager_nm"] == "한현장"
    assert p["create_user_id"] == "park.pm"
    r = client.patch(f"/api/plans/{p['plan_id']}", json={"plan_end_dt": "2026-10-01"}, headers=h)
    assert r.json()["message"] == "계획 종료일이 시작일보다 빠릅니다."


def test_plan_update_preserves_progress(client, auth):
    h = auth("park.pm")
    p = new_plan(client, h, "8004", plan_start_dt="2026-10-01", plan_end_dt="2026-11-30")
    client.put(f"/api/plans/{p['plan_id']}/progress/2026-10-05", json={"progress_rate": 30}, headers=h)
    r = client.patch(f"/api/plans/{p['plan_id']}", json={"remark": "수정", "plan_end_dt": "2026-12-31"}, headers=h).json()
    assert r["progress_rate"] == 30 and r["actual_start_dt"] == "2026-10-05" and r["remark"] == "수정"
    r = client.patch(f"/api/plans/{p['plan_id']}", json={"block_id": None}, headers=h).json()
    assert r["block_id"] is None and r["label"].startswith("[호선]")


def test_plan_t03_self_and_cycle(client, auth, db):
    h = auth("park.pm")
    r = client.put("/api/plans/2/predecessors", json={"pred_plan_ids": [2]}, headers=h)
    assert (r.status_code, r.json()["code"]) == (400, "PLAN_DEPENDENCY_SELF")
    assert r.json()["message"] == "자기 자신을 선행 공정으로 지정할 수 없습니다."
    r = client.put("/api/plans/1/predecessors", json={"pred_plan_ids": [3], "confirm_late_preds": True}, headers=h)
    assert (r.status_code, r.json()["code"], r.json()["message"]) == (400, "PLAN_DEPENDENCY_CYCLE", "선행 공정이 순환 구조를 만듭니다.")
    other = scalar(db, "SELECT PlanId FROM TB_PRC_Plan WHERE HullNo='8002' LIMIT 1")
    r = client.put("/api/plans/2/predecessors", json={"pred_plan_ids": [other]}, headers=h)
    assert r.json()["message"] == "선행 공정은 같은 호선의 공정이어야 합니다."


def test_plan_t04_late_predecessor(client, auth, db):
    h = auth("park.pm")
    a = new_plan(client, h, "8004", plan_start_dt="2026-11-01", plan_end_dt="2026-11-20")
    body = {"proc_cd": "SUBASM", "plan_start_dt": "2026-11-10", "plan_end_dt": "2026-11-30", "pred_plan_ids": [a["plan_id"]]}
    before = scalar(db, "SELECT COUNT(*) FROM TB_PRC_Plan")
    r = client.post("/api/hulls/8004/plans", json=body, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "PRED_LATE_CONFIRM_REQUIRED"
    assert r.json()["details"]["late_pred_plan_ids"] == [a["plan_id"]]
    assert scalar(db, "SELECT COUNT(*) FROM TB_PRC_Plan") == before  # 취소 시 변경 없음
    r = client.post("/api/hulls/8004/plans", json={**body, "confirm_late_preds": True}, headers=h)
    assert r.status_code == 201 and r.json()["pred_plan_ids"] == [a["plan_id"]]
    assert scalar(db, "SELECT LagDays FROM TB_PRC_PlanDep WHERE PlanId=?", r.json()["plan_id"]) == 0
    b = new_plan(client, h, "8004", plan_start_dt="2026-11-05", plan_end_dt="2026-11-06")
    r = client.put(f"/api/plans/{b['plan_id']}/predecessors", json={"pred_plan_ids": [a["plan_id"]]}, headers=h)
    assert r.status_code == 409
    r = client.put(f"/api/plans/{b['plan_id']}/predecessors", json={"pred_plan_ids": [a["plan_id"]], "confirm_late_preds": True}, headers=h)
    assert r.status_code == 200
    r = client.put(f"/api/plans/{b['plan_id']}/predecessors", json={"pred_plan_ids": []}, headers=h)
    assert r.json()["pred_plan_ids"] == []


def test_plan_t05_t06_ready_gate(client, auth, db):
    h = auth("park.pm")
    a = new_plan(client, h, "8004", plan_start_dt="2026-10-01", plan_end_dt="2026-10-30")
    b = new_plan(client, h, "8004", proc_cd="SUBASM", plan_start_dt="2026-11-01", plan_end_dt="2026-11-20",
                 pred_plan_ids=[a["plan_id"]])
    assert b["plan_status"] == "PLAN"
    client.put(f"/api/plans/{a['plan_id']}/progress/2026-10-19", json={"progress_rate": 100}, headers=h)
    assert client.get(f"/api/plans/{b['plan_id']}", headers=h).json()["plan_status"] == "READY"
    draft = make_drawing(db, "8004", "8004-T-DRAFT")
    r = client.post(f"/api/plans/{b['plan_id']}/drawings", json={"drawing_id": draft, "required": True}, headers=h)
    assert r.status_code == 201 and r.json()["blockers"][0]["drawing_no"] == "8004-T-DRAFT"
    assert r.json()["links"][0]["need_dt"] == "2026-11-01" and r.json()["links"][0]["has_issued"] is False
    p = client.get(f"/api/plans/{b['plan_id']}", headers=h).json()
    assert p["plan_status"] == "PLAN" and p["drawing_wait"] is True and p["gate_ok"] is False
    # APPROVED만으로는 통과하지 못한다
    db.execute("UPDATE TB_DWG_Revision SET RevStatus='APPROVED' WHERE DrawingId=?", (draft,))
    db.execute("UPDATE TB_DWG_Drawing SET DwgStatus='APPROVED' WHERE DrawingId=?", (draft,))
    recalc("8004")
    assert client.get(f"/api/plans/{b['plan_id']}", headers=h).json()["plan_status"] == "PLAN"
    db.execute("UPDATE TB_DWG_Revision SET RevStatus='ISSUED', IssueDt='2026-10-19' WHERE DrawingId=?", (draft,))
    db.execute("UPDATE TB_DWG_Drawing SET DwgStatus='ISSUED' WHERE DrawingId=?", (draft,))
    recalc("8004")
    p = client.get(f"/api/plans/{b['plan_id']}", headers=h).json()
    assert p["plan_status"] == "READY" and p["gate_ok"] is True
    # 과거 ISSUED가 있으면 최신이 DRAFT여도 통과
    db.execute("INSERT INTO TB_DWG_Revision(DrawingId, RevNo, RevStatus) VALUES (?,1,'DRAFT')", (draft,))
    db.execute("UPDATE TB_DWG_Drawing SET DwgStatus='DRAFT' WHERE DrawingId=?", (draft,))
    recalc("8004")
    assert client.get(f"/api/plans/{b['plan_id']}", headers=h).json()["plan_status"] == "READY"


def test_plan_status_rules(client, auth):
    h = auth("park.pm")
    late = new_plan(client, h, "8004", plan_start_dt="2026-09-01", plan_end_dt="2026-10-10")
    assert late["plan_status"] == "DELAY"
    client.put(f"/api/plans/{late['plan_id']}/progress/2026-10-01", json={"progress_rate": 40}, headers=h)
    assert client.get(f"/api/plans/{late['plan_id']}", headers=h).json()["plan_status"] == "DELAY"
    work = new_plan(client, h, "8004", plan_start_dt="2026-10-01", plan_end_dt="2026-10-19")
    client.put(f"/api/plans/{work['plan_id']}/progress/2026-10-02", json={"progress_rate": 0}, headers=h)
    assert client.get(f"/api/plans/{work['plan_id']}", headers=h).json()["plan_status"] == "WORK"


def test_plan_t07_delete_no_orphans(client, auth, db):
    h = auth("park.pm")
    assert scalar(db, "SELECT COUNT(*) FROM TB_PRC_Progress WHERE PlanId=1") > 0
    assert client.delete("/api/plans/1", headers=h).status_code == 204
    for t, c in (("TB_PRC_Progress", "PlanId"), ("TB_PRC_PlanDep", "PlanId"), ("TB_PRC_PlanDep", "PredPlanId"),
                 ("TB_DWG_PlanLink", "PlanId")):
        assert scalar(db, f"SELECT COUNT(*) FROM {t} WHERE {c}=1") == 0
    assert sum(orphan_counts(db).values()) == 0
    r = client.delete("/api/plans/1", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "PLAN_NOT_FOUND"


def test_plan_t08_link_unlink_recalc(client, auth, db):
    h = auth("park.pm")
    a = new_plan(client, h, "8004", plan_start_dt="2026-11-01", plan_end_dt="2026-11-20")
    assert a["plan_status"] == "READY"
    dwg = make_drawing(db, "8004", "8004-T-LINK")
    other = make_drawing(db, "8001", "8001-T-OTHER")
    pd = client.get(f"/api/plans/{a['plan_id']}/drawings", headers=h).json()
    assert dwg in [x["drawing_id"] for x in pd["available"]] and other not in [x["drawing_id"] for x in pd["available"]]
    r = client.post(f"/api/plans/{a['plan_id']}/drawings", json={"drawing_id": other}, headers=h)
    assert r.json()["message"] == "같은 호선의 도면만 연계할 수 있습니다."
    assert client.post(f"/api/plans/{a['plan_id']}/drawings", json={"drawing_id": 99999}, headers=h).json()["code"] == "DRAWING_NOT_FOUND"
    client.post(f"/api/plans/{a['plan_id']}/drawings", json={"drawing_id": dwg, "required": True}, headers=h)
    r = client.post(f"/api/plans/{a['plan_id']}/drawings", json={"drawing_id": dwg}, headers=h)
    assert (r.status_code, r.json()["message"]) == (409, "이미 연계된 도면입니다.")
    assert client.get(f"/api/plans/{a['plan_id']}", headers=h).json()["plan_status"] == "PLAN"
    assert client.delete(f"/api/plans/{a['plan_id']}/drawings/{dwg}", headers=h).status_code == 204
    assert client.get(f"/api/plans/{a['plan_id']}", headers=h).json()["plan_status"] == "READY"
    r = client.delete(f"/api/plans/{a['plan_id']}/drawings/{dwg}", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "LINK_NOT_FOUND"
    # 참고(필수 아님) 연계는 게이트에 영향 없음
    client.post(f"/api/plans/{a['plan_id']}/drawings", json={"drawing_id": dwg, "required": False}, headers=h)
    assert client.get(f"/api/plans/{a['plan_id']}", headers=h).json()["plan_status"] == "READY"


def test_plan_t09_view_forbidden(client, auth):
    for emp in ("choi.qa", "lee.dwg"):
        h = auth(emp)
        assert client.post("/api/hulls/8001/plans", json={}, headers=h).status_code == 403
        assert client.patch("/api/plans/1", json={}, headers=h).status_code == 403
        assert client.delete("/api/plans/1", headers=h).status_code == 403
        assert client.put("/api/plans/1/predecessors", json={"pred_plan_ids": []}, headers=h).status_code == 403
        assert client.post("/api/plans/1/drawings", json={"drawing_id": 1}, headers=h).status_code == 403
        assert client.delete("/api/plans/1/drawings/1", headers=h).status_code == 403
        assert client.get("/api/plans/1/drawings", headers=h).status_code == 200
