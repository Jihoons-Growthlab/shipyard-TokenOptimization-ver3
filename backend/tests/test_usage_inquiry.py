"""사용 로그·건의·문의(명세 외 요청 기능)."""
from app.db import scalar
from app.demo_usage import attach_demo_usage


def test_api_calls_are_logged_with_user_and_route(client, auth, db):
    h = auth("park.pm")
    client.get("/api/hulls/8001/plans", headers=h)
    client.get("/api/health")
    r = db.execute("SELECT EmpNo, Method, Path, Status FROM TB_SYS_LogApi WHERE Path LIKE '/api/hulls/%/plans' "
                   "ORDER BY LogApiId DESC LIMIT 1").fetchone()
    assert tuple(r) == ("park.pm", "GET", "/api/hulls/{hull_no}/plans", 200)
    assert not scalar(db, "SELECT COUNT(*) FROM TB_SYS_LogApi WHERE Path='/api/health'")


def test_usage_summary_admin_only(client, auth, db):
    a = auth("admin")
    client.get("/api/hulls", headers=auth("choi.qa"))
    s = client.get("/api/usage/summary", params={"days": 7}, headers=a).json()
    assert s["kpi"]["calls"] > 0 and len(s["daily"]) == 7 and len(s["hours"]) == 24
    assert any(f["feature"] == "호선 관리" for f in s["features"])
    assert any(u["emp_no"] == "choi.qa" for u in s["top_users"])
    f = client.get("/api/usage/summary", params={"days": 30, "emp_no": "choi.qa"}, headers=a).json()
    assert {u["emp_no"] for u in f["top_users"]} == {"choi.qa"}
    assert client.get("/api/usage/summary", params={"days": 5}, headers=a).status_code == 400
    assert client.get("/api/usage/summary", headers=auth("park.pm")).status_code == 403
    out = attach_demo_usage(db)
    assert out["logs"] > 0 and attach_demo_usage(db)["logs"] == 0
    s = client.get("/api/usage/summary", params={"days": 30}, headers=a).json()
    assert s["demo_calls"] > 0 and s["kpi"]["errors"] > 0


def test_inquiry_flow(client, auth):
    u, v, a = auth("han.wk"), auth("choi.qa"), auth("admin")
    r = client.post("/api/inquiries", json={"category": "BUG", "title": " 오류 ", "content": "내용"}, headers=u)
    assert r.status_code == 201 and r.json()["status"] == "OPEN" and r.json()["title"] == "오류"
    iid = r.json()["inquiry_id"]
    assert client.post("/api/inquiries", json={"category": "X", "title": "t", "content": "c"}, headers=u).json()["message"] == "분류를 선택하세요."
    # 조회전용 그룹도 글을 쓸 수 있지만 남의 글은 못 본다.
    assert client.post("/api/inquiries", json={"category": "ETC", "title": "t", "content": "c"}, headers=v).status_code == 201
    assert client.get(f"/api/inquiries/{iid}", headers=v).status_code == 403
    mine = client.get("/api/inquiries", headers=v).json()
    assert mine["is_admin"] is False and all(i["mine"] for i in mine["items"])
    assert client.patch(f"/api/inquiries/{iid}", json={"status": "DONE", "answer": "x"}, headers=u).status_code == 403
    assert client.patch(f"/api/inquiries/{iid}", json={"title": "수정"}, headers=u).json()["title"] == "수정"
    # 관리자 처리
    al = client.get("/api/inquiries", headers=a).json()
    assert al["is_admin"] is True and al["total"] >= 2 and al["counts"]["OPEN"] >= 2
    r = client.patch(f"/api/inquiries/{iid}", json={"status": "DONE"}, headers=a)
    assert r.json()["message"] == "완료·반려 처리에는 답변을 입력하세요."
    r = client.patch(f"/api/inquiries/{iid}", json={"status": "DONE", "answer": "조치했습니다."}, headers=a).json()
    assert r["status"] == "DONE" and r["answer_user_nm"] and r["answer_dt"]
    assert client.patch(f"/api/inquiries/{iid}", json={"title": "x"}, headers=u).status_code == 409
    assert client.delete(f"/api/inquiries/{iid}", headers=u).status_code == 409
    assert client.delete(f"/api/inquiries/{iid}", headers=a).status_code == 204
    assert client.get(f"/api/inquiries/{iid}", headers=a).status_code == 404
