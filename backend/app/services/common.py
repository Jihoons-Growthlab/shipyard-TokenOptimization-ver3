"""여러 도메인이 공유하는 조회·검증 헬퍼."""
import re
from datetime import date, datetime, timezone

from .. import config
from ..db import one, rows, scalar
from ..errors import bad

VIEW, WRITE, ADMIN = 1, 2, 3
LEVELS = {"View": VIEW, "Write": WRITE, "Admin": ADMIN}
LEVEL_NAMES = {v: k for k, v in LEVELS.items()}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_date(v) -> bool:
    if not isinstance(v, str) or not _DATE_RE.match(v):
        return False
    try:
        date.fromisoformat(v)
        return True
    except ValueError:
        return False


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def act_dt() -> str:
    """결재 일시: 기준일 + 현재 시각."""
    return f"{config.TODAY} {datetime.now():%H:%M}"


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def clean(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


# ---- 코드
def codes(conn) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows(conn, "SELECT c.CodeGroup g, c.Code code, c.CodeName name FROM TB_SYS_Code c "
                        "JOIN TB_SYS_CodeGroup g ON g.CodeGroup=c.CodeGroup "
                        "WHERE c.UseYN=1 AND g.UseYN=1 ORDER BY g.Seq, c.Seq, c.Code"):
        out.setdefault(r.pop("g"), []).append(r)
    return out


def code_map(conn, group: str) -> dict[str, str]:
    return {r["Code"]: r["CodeName"] for r in rows(
        conn, "SELECT Code, CodeName FROM TB_SYS_Code WHERE CodeGroup=? AND UseYN=1 ORDER BY Seq", group)}


def check_code(conn, group: str, value, field: str, message: str = "허용되지 않는 코드값입니다.") -> None:
    if value is not None and value not in code_map(conn, group):
        raise bad(message, field)


# ---- 사용자
def user_name(conn, emp_no):
    return scalar(conn, "SELECT display_name FROM users WHERE emp_no=?", emp_no) if emp_no else None


def check_approved(conn, emp_no, field: str, message: str) -> None:
    if emp_no is not None and not scalar(conn, "SELECT 1 FROM users WHERE emp_no=? AND status='approved'", emp_no):
        raise bad(message, field)


def user_options(conn) -> list[dict]:
    return rows(conn, "SELECT emp_no, display_name FROM users WHERE status='approved' ORDER BY display_name, emp_no")


# ---- 권한
def menu_level(conn, emp_no: str, menu_id: str) -> int:
    v = scalar(conn, "SELECT MAX(CASE a.AuthGbn WHEN 'Admin' THEN 3 WHEN 'Write' THEN 2 WHEN 'View' THEN 1 ELSE 0 END) "
                     "FROM TB_SYS_AuthMenu a JOIN TB_SYS_AuthUser u ON u.AuthCd=a.AuthCd "
                     "WHERE u.EmpNo=? AND a.MenuId=?", emp_no, menu_id)
    return int(v or 0)


def hull_exists(conn, hull_no) -> bool:
    return bool(hull_no) and one(conn, "SELECT 1 x FROM TB_MST_Hull WHERE HullNo=?", hull_no) is not None
