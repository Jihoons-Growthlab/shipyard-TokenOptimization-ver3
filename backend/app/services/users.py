"""F09 회원관리. 입력 검증은 members.validate_member(가입과 공유)."""
from .. import config
from ..db import one, rows, scalar, tx
from ..errors import ApiError, bad, conflict, not_found
from ..security import hash_password
from .common import ADMIN, USER_MENU, WRITE, group_menu_levels, user_menu_levels
from .members import normalize_phone, user_out, validate_member

STATUSES = ("pending", "approved", "rejected", "disabled")


def _get(conn, emp_no: str) -> dict:
    u = one(conn, "SELECT * FROM users WHERE emp_no=?", emp_no)
    if not u:
        raise not_found("USER_NOT_FOUND", "사용자를 찾을 수 없습니다.")
    return u


def get_user(conn, emp_no: str) -> dict:
    return user_out(conn, _get(conn, emp_no))


def list_users(conn, status=None, q=None) -> dict:
    sql, args = "SELECT * FROM users WHERE 1=1", []
    if status:
        sql += " AND status=?"
        args.append(status)
    if q and q.strip():
        sql += (" AND (lower(emp_no) LIKE ? OR lower(display_name) LIKE ? OR lower(email) LIKE ? "
                "OR phone LIKE ? OR replace(phone,'-','') LIKE ?)")
        args += [f"%{q.strip().lower()}%"] * 5
    users = [user_out(conn, u) for u in rows(conn, sql + " ORDER BY created_at, emp_no", *args)]
    return {"users": users, "total": len(users),
            "pending": scalar(conn, "SELECT COUNT(*) FROM users WHERE status='pending'")}


def auth_groups(conn) -> list[dict]:
    return rows(conn, "SELECT AuthCd code, AuthNm name FROM TB_SYS_AuthGroup ORDER BY AuthCd")


def _check_status(v) -> None:
    if v not in STATUSES:
        raise bad("허용되지 않는 상태입니다.", "status")


def _check_groups(conn, groups) -> list[str]:
    groups = list(dict.fromkeys(g for g in (groups or []) if g))
    known = {g["code"] for g in auth_groups(conn)}
    if any(g not in known for g in groups):
        raise bad("존재하지 않는 권한 그룹입니다.", "groups")
    return groups


def _otp_not_enrolled() -> ApiError:
    return conflict("OTP_NOT_ENROLLED", "등록된 OTP 정보가 없는 사용자는 2차 인증을 사용할 수 없습니다.")


def _set_groups(conn, emp_no: str, groups: list[str]) -> None:
    conn.execute("DELETE FROM TB_SYS_AuthUser WHERE EmpNo=?", (emp_no,))
    conn.executemany("INSERT INTO TB_SYS_AuthUser(AuthCd, EmpNo) VALUES (?,?)", [(g, emp_no) for g in groups])


def create_user(conn, body: dict) -> dict:
    validate_member(conn, body, creating=True)
    status = body.get("status") or "approved"
    _check_status(status)
    groups = _check_groups(conn, body.get("groups"))
    if body.get("totp_enabled"):
        raise _otp_not_enrolled()
    emp_no = body["emp_no"].strip()
    last, first = body["last_name"].strip(), body["first_name"].strip()
    with tx(conn):
        conn.execute(
            "INSERT INTO users(id,email,password_hash,display_name,emp_no,status,auth_provider,last_name,first_name,"
            "birth_date,phone,totp_enabled,totp_secret,created_at) VALUES (?,?,?,?,?,?,'local',?,?,?,?,0,NULL,?)",
            ("u-" + emp_no, body["email"].strip(), hash_password(body["password"]), last + first, emp_no, status,
             last, first, body["birth_date"], normalize_phone(body["phone"]), config.TODAY))
        _set_groups(conn, emp_no, groups)
    return get_user(conn, emp_no)


def update_user(conn, emp_no: str, body: dict) -> dict:
    u = _get(conn, emp_no)
    if "emp_no" in body and (body["emp_no"] or "").strip() != emp_no:
        raise bad("아이디는 변경할 수 없습니다.", "emp_no")
    fields = ("last_name", "first_name", "birth_date", "email", "phone")
    merged = {k: u[k] for k in fields}
    merged.update({k: body[k] for k in fields if k in body})
    merged.update({k: body.get(k) for k in ("password", "password_confirm") if k in body})
    validate_member(conn, merged, creating=False, self_emp=emp_no)
    sets = {"last_name": merged["last_name"].strip(), "first_name": merged["first_name"].strip(),
            "birth_date": merged["birth_date"], "email": merged["email"].strip(),
            "phone": normalize_phone(merged["phone"])}
    sets["display_name"] = sets["last_name"] + sets["first_name"]
    if "status" in body:
        _check_status(body["status"])
        sets["status"] = body["status"]
    groups = _check_groups(conn, body["groups"]) if body.get("groups") is not None else None
    if body.get("totp_enabled") is not None:
        if body["totp_enabled"] and not u["totp_secret"]:
            raise _otp_not_enrolled()
        sets["totp_enabled"] = int(bool(body["totp_enabled"]))  # 끌 때 secret은 유지
    if body.get("password"):
        sets["password_hash"] = hash_password(body["password"])
    with tx(conn):
        conn.execute(f"UPDATE users SET {','.join(k + '=?' for k in sets)} WHERE emp_no=?", [*sets.values(), emp_no])
        if groups is not None:
            _set_groups(conn, emp_no, groups)
    return get_user(conn, emp_no)


def _require_pending(u: dict) -> None:
    if u["status"] != "pending":
        raise conflict("INVALID_STATUS", "승인 대기 상태가 아닙니다.")


def approve(conn, emp_no: str, groups) -> dict:
    u = _get(conn, emp_no)
    _require_pending(u)
    groups = _check_groups(conn, groups)
    if not groups:
        raise bad("승인 시 권한 그룹을 1개 이상 지정하세요.", "groups")
    with tx(conn):
        conn.execute("UPDATE users SET status='approved' WHERE emp_no=?", (emp_no,))
        _set_groups(conn, emp_no, groups)
    return get_user(conn, emp_no)


def reject(conn, emp_no: str) -> dict:
    _require_pending(_get(conn, emp_no))
    with tx(conn):
        conn.execute("UPDATE users SET status='rejected' WHERE emp_no=?", (emp_no,))
    return get_user(conn, emp_no)


def delete_user(conn, emp_no: str, actor: dict) -> None:
    _get(conn, emp_no)
    if emp_no == actor["emp_no"]:
        raise conflict("SELF_DELETE", "로그인 중인 본인 계정은 삭제할 수 없습니다.")
    with tx(conn):
        conn.execute("DELETE FROM users WHERE emp_no=?", (emp_no,))


# ---- 회원별 메뉴 권한(명세 외 요청 기능). 화면 단위는 0 없음 / 1 읽기 / 2 쓰기.
_SHOWN = lambda lvl: min(lvl, WRITE)  # noqa: E731


def user_menus(conn, emp_no: str) -> dict:
    _get(conn, emp_no)
    group, own = group_menu_levels(conn, emp_no), user_menu_levels(conn, emp_no)
    menus = rows(conn, "SELECT MenuId menu_id, ParentId parent_id, Title title, Seq seq FROM TB_SYS_MenuInfo "
                       "WHERE UseYN=1 ORDER BY Seq, MenuId")
    for m in menus:
        g, u = _SHOWN(group.get(m["menu_id"], 0)), own.get(m["menu_id"])
        m.update(group_level=g, user_level=None if u is None else _SHOWN(u), level=g if u is None else _SHOWN(u))
    return {"emp_no": emp_no, "menus": menus}


def set_user_menus(conn, emp_no: str, items: list[dict], actor: dict) -> dict:
    """전체 교체. level이 null이거나 그룹 권한과 같으면 그룹을 따른다."""
    _get(conn, emp_no)
    known = {r["MenuId"] for r in rows(conn, "SELECT MenuId FROM TB_SYS_MenuInfo")}
    group = group_menu_levels(conn, emp_no)
    out: dict[str, str] = {}
    for it in items:
        mid, lvl = it.get("menu_id"), it.get("level")
        if mid not in known:
            raise bad("존재하지 않는 메뉴입니다.", "menus")
        if lvl is None:
            continue
        if lvl not in (0, 1, 2):
            raise bad("허용되지 않는 권한입니다.", "menus")
        if lvl != _SHOWN(group.get(mid, 0)):
            out[mid] = ["None", "View", "Admin" if mid == USER_MENU else "Write"][lvl]
    if emp_no == actor["emp_no"]:
        mine = out.get(USER_MENU)
        if (ADMIN if mine == "Admin" else 0 if mine else group.get(USER_MENU, 0)) < ADMIN:
            raise conflict("SELF_LOCKOUT", "본인의 회원관리 쓰기 권한은 낮출 수 없습니다.")
    with tx(conn):
        conn.execute("DELETE FROM TB_SYS_UserMenu WHERE EmpNo=?", (emp_no,))
        conn.executemany("INSERT INTO TB_SYS_UserMenu(EmpNo, MenuId, AuthGbn) VALUES (?,?,?)",
                         [(emp_no, m, g) for m, g in out.items()])
    return user_menus(conn, emp_no)
