from app import config
from app.db import one, scalar
from tests.helpers import new_plan, orphan_counts

NEW = {"hull_no": "9001", "hull_nm": "테스트선", "ship_type": "LNG", "owner_nm": "Test Owner",
       "contract_dt": "2026-01-01", "delivery_dt": "2028-05-31", "length_m": 100.0}


def test_hull_t01_list_filters(client, auth):
    h = auth("park.pm")
    all_ = client.get("/api/hulls", headers=h).json()
    assert [x["hull_no"] for x in all_] == ["8001", "8002", "8003", "8004", "8005"]
    by = {x["hull_no"]: x for x in all_}
    assert by["8001"]["progress"] == 65 and by["8005"]["progress"] == 94 and by["8002"]["progress"] == 17
    assert {"plan_count", "progress", "delay_count", "use_yn", "modify_dt"} <= set(by["8001"])
    assert [x["hull_no"] for x in client.get("/api/hulls", params={"status": "BUILD"}, headers=h).json()] == ["8001", "8002"]
    assert [x["hull_no"] for x in client.get("/api/hulls", params={"ship_type": "LNG"}, headers=h).json()] == ["8001", "8005"]
    nordic = client.get("/api/hulls", params={"q": "NORDIC"}, headers=h).json()
    assert "8001" in [x["hull_no"] for x in nordic] and all("nordic" in (x["owner_nm"] or "").lower() for x in nordic)
    assert [x["hull_no"] for x in client.get("/api/hulls", params={"q": "titan"}, headers=h).json()] == ["8002"]
    assert client.get("/api/hulls/8001", headers=h).json()["hull_nm"] == "SWP LNG 174K 1호"
    r = client.get("/api/hulls/XXXX", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "HULL_NOT_FOUND" and r.json()["message"] == "호선을 찾을 수 없습니다."


def test_hull_progress_null_without_plans(client, auth):
    h = auth("park.pm")
    client.post("/api/hulls", json=NEW, headers=h)
    x = client.get("/api/hulls/9001", headers=h).json()
    assert x["progress"] is None and x["plan_count"] == 0 and x["delay_count"] == 0


def test_hull_t02_validation(client, auth):
    h = auth("park.pm")
    cases = [({"hull_no": ""}, 400, "호선번호를 입력하세요."),
             ({"hull_no": "bad no!"}, 400, "호선번호는 영문/숫자/._- 1~20자입니다."),
             ({"hull_no": "8001"}, 409, "이미 존재하는 호선번호입니다."),
             ({"ship_type": "XX"}, 400, "허용되지 않는 코드값입니다."),
             ({"contract_dt": "2026/01/01"}, 400, "날짜 형식(YYYY-MM-DD)이 올바르지 않습니다."),
             ({"delivery_dt": "2025-12-31"}, 400, "인도 예정일이 계약일보다 빠릅니다."),
             ({"dead_weight": -1}, 400, "0 이상의 값을 입력하세요."),
             ({"hull_status": ""}, 400, "상태를 선택하세요.")]
    for patch, status, msg in cases:
        r = client.post("/api/hulls", json={**NEW, **patch}, headers=h)
        assert (r.status_code, r.json()["message"]) == (status, msg), patch
    r = client.post("/api/hulls", json={**NEW, "remark": "x" * 501}, headers=h)
    assert r.status_code == 422


def test_hull_t03_create_milestones(client, auth):
    h = auth("park.pm")
    r = client.post("/api/hulls", json=NEW, headers=h)
    assert r.status_code == 201
    b = r.json()
    assert b["hull_status"] == "PLAN" and b["use_yn"] is True and b["create_user_id"] == "park.pm"
    assert b["create_dt"] == config.TODAY
    ms = client.get("/api/hulls/9001/milestones", headers=h).json()
    assert [m["milestone_cd"] for m in ms] == ["CUT", "KEEL", "LAUNCH", "TRIAL", "DELIVER"]
    assert ms[-1]["plan_dt"] == "2028-05-31" and all(m["plan_dt"] is None for m in ms[:-1])
    assert ms[1]["name"] == "기공(Keel Laying)"
    r = client.put("/api/hulls/9001/milestones", headers=h, json={"items": [
        {"milestone_cd": "CUT", "plan_dt": "2026-11-01", "actual_dt": "2026-11-04"}]})
    assert r.status_code == 200 and r.json()[0]["diff_days"] == 3
    for items in ([{"milestone_cd": "CUT"}, {"milestone_cd": "CUT"}], [{"milestone_cd": "XX"}]):
        r = client.put("/api/hulls/9001/milestones", headers=h, json={"items": items})
        assert r.status_code == 400 and r.json()["message"] == "허용되지 않거나 중복된 일정 코드입니다."


def test_hull_t04_update(client, auth):
    h = auth("park.pm")
    r = client.patch("/api/hulls/8004", json={"hull_nm": "Star Chemi II", "dock_no": "5도크"}, headers=h)
    assert r.status_code == 200 and r.json()["hull_nm"] == "Star Chemi II"
    assert r.json()["modify_user_id"] == "park.pm" and r.json()["modify_dt"] == config.TODAY
    assert r.json()["ship_type"] == "PC"  # 보내지 않은 필드는 유지
    lst = {x["hull_no"]: x for x in client.get("/api/hulls", headers=h).json()}
    assert lst["8004"]["hull_nm"] == "Star Chemi II"
    r = client.patch("/api/hulls/8004", json={"hull_no": "9999"}, headers=h)
    assert r.status_code == 400 and r.json()["message"] == "호선번호는 수정할 수 없습니다."
    r = client.patch("/api/hulls/8004", json={"hull_status": None}, headers=h)
    assert r.json()["message"] == "상태를 선택하세요."
    r = client.patch("/api/hulls/8001", json={"delivery_dt": "2020-01-01"}, headers=h)
    assert r.json()["message"] == "인도 예정일이 계약일보다 빠릅니다."


def test_hull_t05_block_unique_in_hull(client, auth):
    h = auth("park.pm")
    r = client.post("/api/hulls/8005/blocks", json={"block_cd": "101", "block_nm": "선수", "block_type": "FLAT",
                                                     "weight_ton": 10}, headers=h)
    assert r.status_code in (201, 409)
    r = client.post("/api/hulls/8004/blocks", json={"block_cd": "901", "block_type": "CURVE"}, headers=h)
    assert r.status_code == 201 and r.json()["block_cd"] == "901" and r.json()["progress"] is None
    r = client.post("/api/hulls/8004/blocks", json={"block_cd": "901"}, headers=h)
    assert (r.status_code, r.json()["message"]) == (409, "이미 존재하는 블록코드입니다.")
    assert client.post("/api/hulls/8004/blocks", json={"block_cd": ""}, headers=h).json()["message"] == "블록코드를 입력하세요."
    assert client.post("/api/hulls/8004/blocks", json={"block_cd": "902", "block_type": "X"}, headers=h).status_code == 400
    assert client.post("/api/hulls/8004/blocks", json={"block_cd": "902", "weight_ton": -1}, headers=h).status_code == 400
    blocks = client.get("/api/hulls/8001/blocks", headers=h).json()
    assert [b["block_cd"] for b in blocks] == ["101", "201", "301", "401", "501"]
    assert {"plan_count", "progress", "drawing_count"} <= set(blocks[0])


def test_hull_t06_block_delete_keeps_drawings(client, auth, db):
    h = auth("park.pm")
    dwg = scalar(db, "SELECT COUNT(*) FROM TB_DWG_Drawing WHERE BlockId=1")
    assert dwg > 0
    total = scalar(db, "SELECT COUNT(*) FROM TB_DWG_Drawing")
    assert client.delete("/api/blocks/1", headers=h).status_code == 204
    assert scalar(db, "SELECT COUNT(*) FROM TB_DWG_Drawing") == total
    assert scalar(db, "SELECT COUNT(*) FROM TB_PRC_Plan WHERE BlockId=1") == 0
    assert scalar(db, "SELECT COUNT(*) FROM TB_DWG_Drawing WHERE BlockId IS NULL AND HullNo='8001'") >= dwg
    r = client.delete("/api/blocks/1", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "BLOCK_NOT_FOUND"
    assert sum(orphan_counts(db).values()) == 0


def test_hull_t07_delete_no_orphans(client, auth, db, tmp_path):
    h = auth("park.pm")
    fid = "a" * 32
    path = config.file_dir() / f"{fid}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4")
    db.execute("UPDATE TB_DWG_Revision SET FileId=? WHERE DrawingId=1 AND RevNo=0", (fid,))
    assert client.delete("/api/hulls/8001", headers=h).status_code == 204
    for t in ("TB_MST_Block", "TB_PRC_Plan", "TB_DWG_Drawing", "TB_MST_HullMilestone"):
        assert scalar(db, f"SELECT COUNT(*) FROM {t} WHERE HullNo='8001'") == 0
    assert sum(orphan_counts(db).values()) == 0
    assert not path.exists()
    assert client.get("/api/hulls/8001", headers=h).status_code == 404


def test_hull_t08_view_write_forbidden(client, auth):
    for emp in ("choi.qa", "lee.dwg"):
        h = auth(emp)
        assert client.get("/api/hulls", headers=h).status_code == 200
        r = client.post("/api/hulls", json=NEW, headers=h)
        assert r.status_code == 403 and r.json()["details"]["menu_id"] == "M11"
        assert client.patch("/api/hulls/8001", json={"hull_nm": "x"}, headers=h).status_code == 403
        assert client.delete("/api/hulls/8001", headers=h).status_code == 403
        assert client.post("/api/hulls/8001/blocks", json={"block_cd": "999"}, headers=h).status_code == 403
        assert client.delete("/api/blocks/1", headers=h).status_code == 403
        assert client.put("/api/hulls/8001/milestones", json={"items": []}, headers=h).status_code == 403


def test_hull_summary(client, auth):
    s = client.get("/api/hulls/8001/summary", headers=auth("choi.qa")).json()
    assert s["progress"] == 65 and set(s["plan_status"]) == {"PLAN", "READY", "WORK", "DONE", "DELAY"}
    assert sum(s["plan_status"].values()) == s["plan_count"]
    assert set(s["drawing_status"]) == {"ISSUED", "APPROVED", "REVIEW", "DRAFT"}


def test_hull_auto_transition(client, auth, db):
    h = auth("park.pm")
    assert one(db, "SELECT HullStatus FROM TB_MST_Hull WHERE HullNo='8003'")["HullStatus"] == "DESIGN"
    p = new_plan(client, h, "8003", plan_start_dt="2026-10-01", plan_end_dt="2026-11-30")
    client.put(f"/api/plans/{p['plan_id']}/progress/2026-10-10", json={"progress_rate": 10}, headers=h)
    assert one(db, "SELECT HullStatus FROM TB_MST_Hull WHERE HullNo='8003'")["HullStatus"] == "BUILD"
    launch = new_plan(client, h, "8003", proc_cd="LAUNCH", plan_start_dt="2026-10-15", plan_end_dt="2026-10-20")
    client.put(f"/api/plans/{launch['plan_id']}/progress/2026-10-19", json={"progress_rate": 100}, headers=h)
    assert one(db, "SELECT HullStatus FROM TB_MST_Hull WHERE HullNo='8003'")["HullStatus"] == "LAUNCH"
    # PLAN 호선은 전이하지 않는다
    q = new_plan(client, h, "8004", plan_start_dt="2026-10-01", plan_end_dt="2026-11-30")
    client.put(f"/api/plans/{q['plan_id']}/progress/2026-10-10", json={"progress_rate": 10}, headers=h)
    assert one(db, "SELECT HullStatus FROM TB_MST_Hull WHERE HullNo='8004'")["HullStatus"] == "PLAN"
