"""인증·권한 의존성. 권한은 요청마다 DB에서 읽는다."""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import get_db, one
from .errors import forbidden, unauthorized
from .security import decode_token
from .services.common import VIEW, menu_level

_bearer = HTTPBearer(auto_error=False)


def token_payload(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    payload = decode_token(cred.credentials) if cred else None
    if not payload:
        raise unauthorized()
    return payload


def current_user(payload: dict = Depends(token_payload), conn=Depends(get_db)) -> dict:
    lid = payload.get("lid")
    if payload.get("stage") != "full" or not lid:
        raise unauthorized()
    log = one(conn, "SELECT UserId, LogoutDt FROM TB_SYS_LogAccess WHERE LogId=?", lid)
    if not log or log["LogoutDt"] or log["UserId"] != payload["sub"]:
        raise unauthorized()
    user = one(conn, "SELECT * FROM users WHERE emp_no=?", payload["sub"])
    if not user or user["status"] != "approved":
        raise unauthorized()
    user["lid"] = lid
    return user


def require(menu_id: str, level: int = VIEW):
    """메뉴 ID와 최소 등급(View=1, Write=2, Admin=3). 미달이면 403."""
    def dep(user: dict = Depends(current_user), conn=Depends(get_db)) -> dict:
        if menu_level(conn, user["emp_no"], menu_id) < level:
            raise forbidden(menu_id)
        return user
    return dep
