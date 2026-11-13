import json
import shutil

import pytest
from fastapi.testclient import TestClient

from app import config, security
from app.db import connect, migrate
from app.seed import load_seed

SEED = json.loads(config.SEED_FILE.read_text(encoding="utf-8"))
_U = SEED["users"]
PASSWORDS = {r[_U["columns"].index("emp_no")]: r[_U["columns"].index("demo_password")] for r in _U["rows"]}
SECRETS = {r[_U["columns"].index("emp_no")]: r[_U["columns"].index("totp_secret")] for r in _U["rows"]}


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("tpl") / "seed.db"
    conn = connect(path)
    migrate(conn)
    load_seed(conn)
    conn.close()
    return path


@pytest.fixture
def client(template_db, tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    shutil.copy(template_db, db_file)
    monkeypatch.setenv("SHIPYARD_DB_PATH", str(db_file))
    monkeypatch.setenv("SHIPYARD_FILE_DIR", str(tmp_path / "files"))
    monkeypatch.delenv("WEATHER_PROVIDER", raising=False)
    security.reset_state()
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(client):
    conn = connect()
    yield conn
    conn.close()


def otp_code(emp_no, offset=0):
    return security.totp(SECRETS[emp_no], security.current_step() + offset)


def login_token(client, emp_no, password=None):
    r = client.post("/api/auth/login", json={"emp_no": emp_no, "password": password or PASSWORDS[emp_no]})
    assert r.status_code == 200, r.text
    body = r.json()
    if not body["otp_required"]:
        return body["access_token"]
    for off in (0, 1, -1):
        v = client.post("/api/auth/otp/verify", json={"code": otp_code(emp_no, off)},
                        headers={"Authorization": f"Bearer {body['otp_token']}"})
        if v.status_code == 200:
            return v.json()["access_token"]
    raise AssertionError("OTP login failed")


@pytest.fixture
def auth(client):
    cache = {}

    def get(emp_no):
        if emp_no not in cache:
            cache[emp_no] = {"Authorization": f"Bearer {login_token(client, emp_no)}"}
        return cache[emp_no]
    return get
