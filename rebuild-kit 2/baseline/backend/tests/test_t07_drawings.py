from app import config
from app.db import one, scalar
from tests.helpers import new_plan, orphan_counts

PDF = b"%PDF-1.4\n%test\n"
NEW = {"drawing_no": "8004-HULL-T01", "drawing_nm": "시험 도면", "hull_no": "8004", "discipline": "HULL"}


def create(client, h, **kw):
    r = client.post("/api/drawings", json={**NEW, **kw}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def upload(client, h, did, rev, data=PDF, name="a.pdf", ctype="application/pdf"):
    return client.post(f"/api/drawings/{did}/revisions/{rev}/pdf", params={"filename": name}, content=data,
                       headers={**h, "Content-Type": ctype})


def approve_all(client, auth, did, rev):
    for emp in ("lee.dwg", "admin"):
        inbox = client.get("/api/approvals/inbox", headers=auth(emp)).json()["waiting"]
        a = next(x for x in inbox if x["drawing_id"] == did and x["rev_no"] == rev)
        r = client.post(f"/api/approvals/{a['approval_id']}/decision", json={"result": "APPROVE"}, headers=auth(emp))
        assert r.status_code == 200, r.text


def test_dwg_t01_filters_and_rev_labels(client, auth):
    h = auth("choi.qa")
    allr = client.get("/api/drawings", headers=h).json()
    assert len(allr) == 47 and [x["drawing_id"] for x in allr] == sorted(x["drawing_id"] for x in allr)
    assert set(allr[0]) == {"drawing_id", "drawing_no", "drawing_nm", "hull_no", "block_id", "block_cd", "discipline",
                            "dwg_status", "current_rev_no", "latest_rev_no", "designer_emp_no", "designer_nm", "link_count"}
    f = client.get("/api/drawings", params={"hull_no": "8001", "discipline": "PIPE"}, headers=h).json()
    assert f and all(x["hull_no"] == "8001" and x["discipline"] == "PIPE" for x in f)
    s = client.get("/api/drawings", params={"status": "ISSUED"}, headers=h).json()
    assert s and all(x["dwg_status"] == "ISSUED" for x in s)
    q = client.get("/api/drawings", params={"q": "8001-elec"}, headers=h).json()
    assert q and all("8001-ELEC" in x["drawing_no"] for x in q)
    w = auth("lee.dwg")
    client.post("/api/drawings/1/revisions", json={"change_desc": "보강"}, headers=w)
    x = next(d for d in client.get("/api/drawings", headers=h).json() if d["drawing_id"] == 1)
    assert (x["current_rev_no"], x["latest_rev_no"], x["dwg_status"]) == (0, 1, "DRAFT")


def test_dwg_t02_create_validation(client, auth, db):
    h = auth("lee.dwg")
    cases = [({"drawing_no": ""}, "도면번호를 입력하세요."), ({"hull_no": ""}, "호선을 선택하세요."),
             ({"hull_no": "NOPE"}, "호선을 선택하세요."), ({"drawing_nm": " "}, "도면명을 입력하세요."),
             ({"discipline": "XX"}, "허용되지 않는 분야입니다."),
             ({"designer_emp_no": "jung.new"}, "승인된 회원만 지정할 수 있습니다.")]
    for patch, msg in cases:
        r = client.post("/api/drawings", json={**NEW, **patch}, headers=h)
        assert (r.status_code, r.json()["message"]) == (400, msg), patch
    d = create(client, h, designer_emp_no="lee.dwg")
    assert d["dwg_status"] == "DRAFT" and d["current_rev_no"] == 0 and d["designer_nm"] == "이도면"
    assert d["revisions"] == [{"rev_no": 0, "rev_status": "DRAFT", "change_desc": "최초 작성", "has_file": False,
                               "file_nm": None, "author_emp_no": "lee.dwg", "author_nm": "이도면", "issue_dt": None,
                               "create_dt": config.TODAY}]
    r = client.post("/api/drawings", json=NEW, headers=h)
    assert (r.status_code, r.json()["message"]) == (409, "이미 존재하는 도면번호입니다.")


def test_dwg_t03_block_and_hull_immutable(client, auth):
    h = auth("lee.dwg")
    r = client.post("/api/drawings", json={**NEW, "block_id": 1}, headers=h)
    assert r.json()["message"] == "해당 호선의 블록이 아닙니다."
    d = create(client, h, block_id=13)
    r = client.patch(f"/api/drawings/{d['drawing_id']}", json={"hull_no": "8001"}, headers=h)
    assert r.json()["message"] == "호선은 변경할 수 없습니다."
    r = client.patch(f"/api/drawings/{d['drawing_id']}", json={"drawing_no": "X-1"}, headers=h)
    assert r.json()["message"] == "도면번호는 변경할 수 없습니다."
    r = client.patch(f"/api/drawings/{d['drawing_id']}", json={"block_id": 1}, headers=h)
    assert r.json()["message"] == "해당 호선의 블록이 아닙니다."
    r = client.patch(f"/api/drawings/{d['drawing_id']}", json={"drawing_nm": "변경", "discipline": "PIPE",
                                                               "block_id": None, "hull_no": "8004"}, headers=h)
    assert r.status_code == 200 and r.json()["drawing_nm"] == "변경" and r.json()["block_id"] is None
    assert r.json()["modify_user_id"] == "lee.dwg"


def test_dwg_t04_pdf_rules(client, auth, db):
    h = auth("lee.dwg")
    d = create(client, h)
    did = d["drawing_id"]
    r = upload(client, h, did, 0, data=b"hello", name="a.pdf")
    assert (r.status_code, r.json()["code"], r.json()["message"]) == (400, "INVALID_FILE_TYPE", "PDF 파일만 업로드할 수 있습니다.")
    r = upload(client, h, did, 0, name="a.txt", ctype="text/plain")
    assert r.json()["code"] == "INVALID_FILE_TYPE"
    big = b"%PDF-" + b"0" * (30 * 1024 * 1024)
    r = upload(client, h, did, 0, data=big)
    assert (r.status_code, r.json()["code"], r.json()["message"]) == (413, "FILE_TOO_LARGE", "파일 크기는 30MB 이하여야 합니다.")
    assert list(config.file_dir().glob("*.pdf")) == []
    r = upload(client, h, did, 0, name="../../etc/도면 A.pdf", ctype="application/octet-stream")
    assert r.status_code == 200
    rev = r.json()["revisions"][0]
    assert rev["has_file"] is True and rev["file_nm"] == "도면 A.pdf"
    fid = scalar(db, "SELECT FileId FROM TB_DWG_Revision WHERE DrawingId=? AND RevNo=0", did)
    assert len(fid) == 32 and (config.file_dir() / f"{fid}.pdf").read_bytes() == PDF
    g = client.get(f"/api/drawings/{did}/revisions/0/pdf", headers=auth("choi.qa"))
    assert g.status_code == 200 and g.content == PDF and g.headers["x-content-type-options"] == "nosniff"
    assert g.headers["content-type"] == "application/pdf" and g.headers["content-disposition"].startswith("inline")
    # 교체 시 이전 파일 삭제
    upload(client, h, did, 0, name="b.pdf")
    assert not (config.file_dir() / f"{fid}.pdf").exists() and len(list(config.file_dir().glob("*.pdf"))) == 1
    # DRAFT가 아니면 업로드·삭제 불가 (시드 ISSUED 리비전)
    r = upload(client, h, 1, 0)
    assert (r.status_code, r.json()["code"], r.json()["message"]) == (409, "INVALID_REV_STATE", "작성중(DRAFT) 리비전만 업로드할 수 있습니다.")
    r = client.delete("/api/drawings/1/revisions/0/pdf", headers=h)
    assert r.json()["message"] == "작성중(DRAFT) 리비전만 파일을 삭제할 수 있습니다."
    r = client.delete(f"/api/drawings/{did}/revisions/0/pdf", headers=h)
    assert r.status_code == 200 and r.json()["revisions"][0]["has_file"] is False
    assert list(config.file_dir().glob("*.pdf")) == []


def test_dwg_t05_seed_has_no_file(client, auth, db):
    h = auth("choi.qa")
    d = client.get("/api/drawings/1", headers=h).json()
    assert d["revisions"][0]["file_nm"] and d["revisions"][0]["has_file"] is False
    r = client.get("/api/drawings/1/revisions/0/pdf", headers=h)
    assert (r.status_code, r.json()["code"]) == (404, "NO_FILE")
    db.execute("UPDATE TB_DWG_Revision SET FileId=? WHERE DrawingId=1 AND RevNo=0", ("b" * 32,))
    r = client.get("/api/drawings/1/revisions/0/pdf", headers=h)
    assert (r.status_code, r.json()["code"]) == (404, "FILE_NOT_FOUND")
    assert set(d) >= {"block_nm", "today", "revisions", "approvals", "plans", "available_plans", "impacts"}


def test_dwg_t06_t07_lifecycle_and_gate(client, auth, db):
    h = auth("lee.dwg")
    d = create(client, h)
    did = d["drawing_id"]
    plan = new_plan(client, auth("park.pm"), "8004", plan_start_dt="2026-11-01", plan_end_dt="2026-11-20")
    r = client.post(f"/api/drawings/{did}/plans", json={"plan_id": plan["plan_id"], "required": True}, headers=h)
    assert r.status_code == 201 and r.json()["plans"][0]["plan_id"] == plan["plan_id"]
    assert client.get(f"/api/plans/{plan['plan_id']}", headers=h).json()["plan_status"] == "PLAN"
    r = client.post(f"/api/drawings/{did}/revisions", json={"change_desc": "x"}, headers=h)
    assert r.status_code == 409 and r.json()["message"] == "최신 리비전이 배포/폐기 상태일 때만 신규 리비전을 작성할 수 있습니다."
    r = client.post(f"/api/drawings/{did}/revisions/0/issue", headers=h)
    assert (r.status_code, r.json()["message"]) == (409, "승인(APPROVED)된 리비전만 배포할 수 있습니다.")
    body = {"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}
    for bad_body, msg in (({"reviewer_emp_no": "lee.dwg"}, "검토자와 승인자를 선택하세요."),
                          ({"reviewer_emp_no": "admin", "approver_emp_no": "admin"}, "검토자와 승인자는 서로 다른 사람이어야 합니다."),
                          ({"reviewer_emp_no": "jung.new", "approver_emp_no": "admin"}, "승인된 회원만 지정할 수 있습니다.")):
        r = client.post(f"/api/drawings/{did}/revisions/0/request-approval", json=bad_body, headers=h)
        assert (r.status_code, r.json()["message"]) == (400, msg)
    r = client.post(f"/api/drawings/{did}/revisions/0/request-approval", json=body, headers=h).json()
    assert r["dwg_status"] == "REVIEW" and r["revisions"][0]["rev_status"] == "REVIEW"
    assert [(a["step_no"], a["result"]) for a in r["approvals"]] == [(1, "WAIT"), (2, "WAIT")]
    r = client.post(f"/api/drawings/{did}/revisions/0/request-approval", json=body, headers=h)
    assert r.json()["message"] == "최신 작성중(DRAFT) 리비전만 결재 요청할 수 있습니다."
    assert upload(client, h, did, 0).status_code == 409
    approve_all(client, auth, did, 0)
    assert client.get(f"/api/drawings/{did}", headers=h).json()["dwg_status"] == "APPROVED"
    r = client.post(f"/api/drawings/{did}/revisions/0/issue", headers=h).json()
    assert r["dwg_status"] == "ISSUED" and r["revisions"][0]["issue_dt"] == config.TODAY
    assert client.get(f"/api/plans/{plan['plan_id']}", headers=h).json()["plan_status"] == "READY"
    # Rev1: 기존 ISSUED 유지 → 배포 시 OBSOLETE
    r = client.post(f"/api/drawings/{did}/revisions", json={"change_desc": ""}, headers=h)
    assert r.json()["message"] == "개정 사유를 입력하세요."
    r = client.post(f"/api/drawings/{did}/revisions", json={"change_desc": "치수 수정"}, headers=h)
    assert r.status_code == 201
    revs = r.json()["revisions"]
    assert [(x["rev_no"], x["rev_status"]) for x in revs] == [(1, "DRAFT"), (0, "ISSUED")] and r.json()["dwg_status"] == "DRAFT"
    assert r.json()["current_rev_no"] == 0
    assert client.get(f"/api/plans/{plan['plan_id']}", headers=h).json()["plan_status"] == "READY"
    client.post(f"/api/drawings/{did}/revisions/1/request-approval", json=body, headers=h)
    approve_all(client, auth, did, 1)
    r = client.post(f"/api/drawings/{did}/revisions/1/issue", headers=h).json()
    assert [(x["rev_no"], x["rev_status"]) for x in r["revisions"]] == [(1, "ISSUED"), (0, "OBSOLETE")]
    assert r["current_rev_no"] == 1 and r["dwg_status"] == "ISSUED"


def test_dwg_issue_requires_complete_approval(client, auth, db):
    h = auth("lee.dwg")
    d = create(client, h)
    did = d["drawing_id"]
    client.post(f"/api/drawings/{did}/revisions/0/request-approval",
                json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=h)
    db.execute("UPDATE TB_DWG_Revision SET RevStatus='APPROVED' WHERE DrawingId=?", (did,))
    r = client.post(f"/api/drawings/{did}/revisions/0/issue", headers=h)
    assert (r.status_code, r.json()["code"], r.json()["message"]) == (409, "APPROVAL_INCOMPLETE", "결재가 완료된 리비전만 배포할 수 있습니다.")


def test_dwg_t08_links_and_impact(client, auth, db):
    h = auth("lee.dwg")
    d = create(client, h, hull_no="8001", drawing_no="8001-T-IMPACT")
    did = d["drawing_id"]
    work = one(db, "SELECT PlanId FROM TB_PRC_Plan WHERE HullNo='8001' AND PlanStatus='WORK' LIMIT 1")["PlanId"]
    other = one(db, "SELECT PlanId FROM TB_PRC_Plan WHERE HullNo='8002' LIMIT 1")["PlanId"]
    assert work in [p["plan_id"] for p in d["available_plans"]]
    r = client.post(f"/api/drawings/{did}/plans", json={"plan_id": other}, headers=h)
    assert r.status_code == 400
    assert client.post(f"/api/drawings/{did}/plans", json={"plan_id": None}, headers=h).json()["message"] == "공정을 선택하세요."
    client.post(f"/api/drawings/{did}/plans", json={"plan_id": work, "required": False}, headers=h)
    assert client.post(f"/api/drawings/{did}/plans", json={"plan_id": work}, headers=h).status_code == 409
    body = {"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}
    client.post(f"/api/drawings/{did}/revisions/0/request-approval", json=body, headers=h)
    approve_all(client, auth, did, 0)
    client.post(f"/api/drawings/{did}/revisions/0/issue", headers=h)
    assert client.get(f"/api/drawings/{did}", headers=h).json()["impacts"] == []  # Rev0은 영향 대상 아님
    client.post(f"/api/drawings/{did}/revisions", json={"change_desc": "보강재 추가"}, headers=h)
    client.post(f"/api/drawings/{did}/revisions/1/request-approval", json=body, headers=h)
    approve_all(client, auth, did, 1)
    client.post(f"/api/drawings/{did}/revisions/1/issue", headers=h)
    imp = client.get(f"/api/drawings/{did}", headers=h).json()["impacts"]
    assert len(imp) == 1 and imp[0]["plan_id"] == work and imp[0]["rev_no"] == 1 and imp[0]["change_desc"] == "보강재 추가"
    assert imp[0]["link"] == {"screen": "drawing", "param": did}
    assert client.delete(f"/api/drawings/{did}/plans/{work}", headers=h).status_code == 204
    assert client.get(f"/api/drawings/{did}/plans", headers=h).json()["plans"] == []
    assert client.delete(f"/api/drawings/{did}/plans/{work}", headers=h).status_code == 404


def test_dwg_t09_delete_no_orphans(client, auth, db):
    h = auth("lee.dwg")
    d = create(client, h)
    did = d["drawing_id"]
    upload(client, h, did, 0)
    plan = new_plan(client, auth("park.pm"), "8004")
    client.post(f"/api/drawings/{did}/plans", json={"plan_id": plan["plan_id"]}, headers=h)
    client.post(f"/api/drawings/{did}/revisions/0/request-approval",
                json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=h)
    assert client.get(f"/api/plans/{plan['plan_id']}", headers=h).json()["plan_status"] == "PLAN"
    assert client.delete(f"/api/drawings/{did}", headers=h).status_code == 204
    assert sum(orphan_counts(db).values()) == 0
    assert list(config.file_dir().glob("*.pdf")) == []
    assert client.get(f"/api/plans/{plan['plan_id']}", headers=h).json()["plan_status"] == "READY"
    assert client.get(f"/api/drawings/{did}", headers=h).status_code == 404


def test_dwg_t10_view_forbidden(client, auth):
    h = auth("choi.qa")
    big = b"%PDF-" + b"0" * (31 * 1024 * 1024)
    r = upload(client, h, 1, 0, data=big)
    assert r.status_code == 403  # 권한 검사가 본문 크기보다 먼저
    assert client.post("/api/drawings", json=NEW, headers=h).status_code == 403
    assert client.post("/api/drawings/1/revisions/0/issue", headers=h).status_code == 403
    assert client.delete("/api/drawings/1", headers=h).status_code == 403
    assert client.delete("/api/drawings/1/revisions/0/pdf", headers=h).status_code == 403
    assert client.post("/api/drawings/1/plans", json={"plan_id": 1}, headers=h).status_code == 403
    assert client.post("/api/drawings/1/revisions", json={"change_desc": "x"}, headers=h).status_code == 403
    assert client.post("/api/drawings", json=NEW, headers=auth("park.pm")).status_code == 403
    assert client.get("/api/drawings/1", headers=h).status_code == 200
