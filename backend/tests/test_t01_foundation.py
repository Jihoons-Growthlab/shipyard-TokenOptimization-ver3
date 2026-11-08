from app.db import connect, migrate, scalar
from app.seed import load_seed, main as init_db


def count(conn, table, where=""):
    return scalar(conn, f"SELECT COUNT(*) FROM {table} {where}")


def test_seed_counts(db):
    expected = {"users": 6, "TB_MST_Hull": 5, "TB_MST_Block": 17, "TB_PRC_Plan": 83, "TB_PRC_PlanDep": 79,
                "TB_PRC_Progress": 60, "TB_DWG_Drawing": 47, "TB_DWG_Revision": 79, "TB_DWG_Approval": 72,
                "TB_DWG_PlanLink": 45}
    assert {t: count(db, t) for t in expected} == expected
    status = dict(db.execute("SELECT PlanStatus, COUNT(*) FROM TB_PRC_Plan GROUP BY PlanStatus").fetchall())
    assert status == {"PLAN": 39, "WORK": 7, "DONE": 36, "DELAY": 1}


def test_passwords_hashed_argon2(db):
    h = scalar(db, "SELECT password_hash FROM users WHERE emp_no='admin'")
    assert h.startswith("$argon2id$")


def test_init_db_idempotent(db, capsys):
    before = count(db, "TB_PRC_Plan")
    assert init_db(["--seed"]) == 0
    assert init_db(["--seed"]) == 0
    assert migrate(db) == []
    assert count(db, "TB_PRC_Plan") == before and count(db, "users") == 6
    assert scalar(db, "SELECT COUNT(*) FROM schema_migrations") == 1


def test_fresh_db_from_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPYARD_DB_PATH", str(tmp_path / "x.db"))
    assert init_db([]) == 0
    conn = connect()
    assert count(conn, "users") == 0
    load_seed(conn)
    assert count(conn, "TB_DWG_Drawing") == 47
    conn.close()


def test_pragmas_and_fk(db):
    assert scalar(db, "PRAGMA foreign_keys") == 1
    assert scalar(db, "PRAGMA busy_timeout") == 5000


def test_health_and_error_body(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    r = client.get("/api/nope")
    assert r.status_code == 404 and set(r.json()) == {"code", "message", "details"}
    r = client.post("/api/auth/login", content="not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_FORMAT" and r.json()["message"] == "요청 형식이 올바르지 않습니다."
