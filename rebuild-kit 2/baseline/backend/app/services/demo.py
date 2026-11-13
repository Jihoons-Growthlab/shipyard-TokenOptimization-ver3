"""Role switching for the isolated demo database."""
import os

from .. import config
from ..db import one, tx
from ..errors import forbidden
from ..security import make_token
from .common import now_utc

ROLES = {"admin": "admin", "user": "han.wk"}


def role_for(user):
    if os.environ.get("SHIPYARD_DEMO") != "1" or config.db_path().resolve() != (config.ROOT / "state/run/demo.db").resolve():
        return None
    return next((role for role, emp_no in ROLES.items() if emp_no == user["emp_no"]), None)


def switch(conn, user, role, ip):
    if role_for(user) is None or role not in ROLES:
        raise forbidden()
    with tx(conn):
        target = one(conn, "SELECT * FROM users WHERE emp_no=? AND status='approved' AND totp_enabled=0", ROLES[role])
        if not target:
            raise forbidden()
        now = now_utc()
        closed = conn.execute("UPDATE TB_SYS_LogAccess SET LogoutDt=? WHERE LogId=? AND LogoutDt IS NULL",
                              (now, user["lid"]))
        if closed.rowcount != 1:
            raise forbidden()
        access = conn.execute("INSERT INTO TB_SYS_LogAccess(UserId, LoginDt, IpAddress) VALUES (?,?,?)",
                              (target["emp_no"], now, ip))
        token = make_token(target["emp_no"], "full", config.token_ttl(), access.lastrowid)
    return {"access_token": token}
