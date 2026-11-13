from app import config
from app.db import scalar

BODY = {"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}


def requested(client, auth, no="8004-APV-T01"):
    h = auth("lee.dwg")
    d = client.post("/api/drawings", json={"drawing_no": no, "drawing_nm": "결재 시험", "hull_no": "8004"}, headers=h).json()
    client.post(f"/api/drawings/{d['drawing_id']}/revisions/0/request-approval", json=BODY, headers=h)
    return d["drawing_id"]


def mine(client, h, did):
    return [x for x in client.get("/api/approvals/inbox", headers=h).json()["waiting"] if x["drawing_id"] == did]


def test_apv_t01_step_order(client, auth):
    did = requested(client, auth)
    assert mine(client, auth("admin"), did) == []
    step1 = mine(client, auth("lee.dwg"), did)
    assert len(step1) == 1 and step1[0]["step_no"] == 1 and step1[0]["change_desc"] == "최초 작성"
    step2_id = step1[0]["approval_id"] + 1
    r = client.post(f"/api/approvals/{step2_id}/decision", json={"result": "APPROVE"}, headers=auth("admin"))
    assert (r.status_code, r.json()["code"]) == (409, "NOT_CURRENT_STEP")
    r = client.post(f"/api/approvals/{step1[0]['approval_id']}/decision", json={"result": "APPROVE", "comment": ""},
                    headers=auth("lee.dwg"))
    assert r.status_code == 200 and set(r.json()) == {"approval_id", "result", "waiting", "ready"}
    assert [x["step_no"] for x in mine(client, auth("admin"), did)] == [2]


def test_apv_t02_not_assigned(client, auth):
    did = requested(client, auth)
    a = mine(client, auth("lee.dwg"), did)[0]
    r = client.post(f"/api/approvals/{a['approval_id']}/decision", json={"result": "APPROVE"}, headers=auth("admin"))
    assert (r.status_code, r.json()["code"], r.json()["message"]) == (403, "NOT_ASSIGNED_APPROVER", "본인에게 지정된 결재 건이 아닙니다.")


def test_apv_order_of_checks(client, auth):
    h = auth("lee.dwg")
    r = client.post("/api/approvals/99999/decision", json={"result": "MAYBE"}, headers=h)
    assert (r.status_code, r.json()["message"]) == (400, "결재 결과는 APPROVE 또는 REJECT 이어야 합니다.")
    r = client.post("/api/approvals/99999/decision", json={"result": "REJECT", "comment": " "}, headers=h)
    assert (r.status_code, r.json()["message"]) == (400, "반려 시 의견을 입력하세요.")
    r = client.post("/api/approvals/99999/decision", json={"result": "APPROVE"}, headers=h)
    assert (r.status_code, r.json()["code"]) == (404, "APPROVAL_NOT_FOUND")
    r = client.post("/api/approvals/1/decision", json={"result": "APPROVE"}, headers=h)  # 시드: 이미 처리
    assert (r.status_code, r.json()["code"], r.json()["message"]) == (409, "ALREADY_DECIDED", "이미 처리된 결재 건입니다.")


def test_apv_t03_reject(client, auth, db):
    did = requested(client, auth)
    a = mine(client, auth("lee.dwg"), did)[0]
    r = client.post(f"/api/approvals/{a['approval_id']}/decision", json={"result": "REJECT"}, headers=auth("lee.dwg"))
    assert r.status_code == 400
    r = client.post(f"/api/approvals/{a['approval_id']}/decision", json={"result": "REJECT", "comment": "치수 누락"},
                    headers=auth("lee.dwg"))
    assert r.status_code == 200
    d = client.get(f"/api/drawings/{did}", headers=auth("lee.dwg")).json()
    assert d["dwg_status"] == "DRAFT" and d["revisions"][0]["rev_status"] == "DRAFT"
    assert [(x["step_no"], x["result"], x["comment"]) for x in d["approvals"]] == [(1, "REJECT", "치수 누락")]
    assert scalar(db, "SELECT COUNT(*) FROM TB_DWG_Approval WHERE DrawingId=? AND Result='WAIT'", did) == 0
    act = d["approvals"][0]["act_dt"]
    assert act.startswith(config.TODAY + " ") and len(act) == 16
    # 재요청 시 기존 결재행을 지우고 새로 만든다
    client.post(f"/api/drawings/{did}/revisions/0/request-approval", json=BODY, headers=auth("lee.dwg"))
    assert scalar(db, "SELECT COUNT(*) FROM TB_DWG_Approval WHERE DrawingId=?", did) == 2


def test_apv_t04_t05_approve_and_issue(client, auth):
    did = requested(client, auth)
    a1 = mine(client, auth("lee.dwg"), did)[0]
    client.post(f"/api/approvals/{a1['approval_id']}/decision", json={"result": "APPROVE"}, headers=auth("lee.dwg"))
    assert client.get(f"/api/drawings/{did}", headers=auth("lee.dwg")).json()["dwg_status"] == "REVIEW"
    a2 = mine(client, auth("admin"), did)[0]
    r = client.post(f"/api/approvals/{a2['approval_id']}/decision", json={"result": "APPROVE", "comment": "OK"},
                    headers=auth("admin")).json()
    assert did in [x["drawing_id"] for x in r["ready"]]
    d = client.get(f"/api/drawings/{did}", headers=auth("lee.dwg")).json()
    assert d["dwg_status"] == "APPROVED" and [x["comment"] for x in d["approvals"]] == ["승인", "OK"]
    inbox = client.get("/api/approvals/inbox", headers=auth("lee.dwg")).json()
    assert inbox["can_issue"] is True
    assert client.get("/api/approvals/inbox", headers=auth("choi.qa")).json()["can_issue"] is False
    client.post(f"/api/drawings/{did}/revisions/0/issue", headers=auth("lee.dwg"))
    inbox = client.get("/api/approvals/inbox", headers=auth("lee.dwg")).json()
    assert did not in [x["drawing_id"] for x in inbox["ready"]]


def test_apv_ready_effect_plans(client, auth, db):
    did = requested(client, auth)
    h = auth("park.pm")
    p = client.post("/api/hulls/8004/plans", json={"proc_cd": "CUT", "plan_start_dt": "2026-11-01",
                                                  "plan_end_dt": "2026-11-10"}, headers=h).json()
    client.post(f"/api/plans/{p['plan_id']}/drawings", json={"drawing_id": did}, headers=h)
    for emp in ("lee.dwg", "admin"):
        a = mine(client, auth(emp), did)[0]
        client.post(f"/api/approvals/{a['approval_id']}/decision", json={"result": "APPROVE"}, headers=auth(emp))
    ready = next(x for x in client.get("/api/approvals/inbox", headers=auth("lee.dwg")).json()["ready"] if x["drawing_id"] == did)
    assert ready["effect_plans"] == [p["label"]] and ready["rev_no"] == 0


def test_apv_t06_history(client, auth, db):
    h = auth("choi.qa")
    hist = client.get("/api/approvals/history", headers=h).json()
    assert len(hist) == 10 and all(x["result"] != "WAIT" for x in hist)
    keys = [(x["act_dt"], x["approval_id"]) for x in hist]
    assert keys == sorted(keys, reverse=True)
    assert set(hist[0]) == {"approval_id", "act_dt", "drawing_id", "drawing_no", "rev_no", "step_no",
                            "approver_emp_no", "approver_nm", "result", "comment"}
    db.execute("DELETE FROM TB_DWG_Approval")
    assert client.get("/api/approvals/history", headers=h).json() == []


def test_apv_permissions(client, auth):
    assert client.get("/api/approvals/inbox", headers=auth("park.pm")).status_code == 403
    r = client.post("/api/approvals/1/decision", json={"result": "APPROVE"}, headers=auth("choi.qa"))
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"
