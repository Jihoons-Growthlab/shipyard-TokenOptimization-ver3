"""회원 입력 검증(가입·회원관리 공유)과 매핑."""
import re

from ..db import one, rows
from ..errors import bad, duplicate
from .common import is_date

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^01\d-?\d{3,4}-?\d{4}$")
EMPNO_RE = re.compile(r"^[A-Za-z0-9._-]{4,20}$")


def normalize_phone(phone: str) -> str:
    d = re.sub(r"\D", "", phone)
    return f"{d[:3]}-{d[3:-4]}-{d[-4:]}"


def validate_member(conn, d: dict, *, creating: bool, self_emp: str | None = None) -> None:
    """F01 가입 검증 순서. creating=False면 아이디 검사 제외, 비밀번호는 입력 시만."""
    if not (d.get("last_name") or "").strip() or not (d.get("first_name") or "").strip():
        raise bad("성과 이름을 입력하세요.", "name")
    if not is_date(d.get("birth_date")):
        raise bad("생년월일을 입력하세요.", "birth_date")
    email = (d.get("email") or "").strip()
    if not EMAIL_RE.match(email):
        raise bad("이메일 형식이 올바르지 않습니다.", "email")
    phone = (d.get("phone") or "").strip()
    if not PHONE_RE.match(phone):
        raise bad("전화번호 형식(010-0000-0000)이 올바르지 않습니다.", "phone")
    emp_no = (d.get("emp_no") or "").strip()
    if creating and not EMPNO_RE.match(emp_no):
        raise bad("아이디는 영문/숫자/._- 조합 4~20자입니다.", "emp_no")
    pw = d.get("password") or ""
    if creating or pw:
        if len(pw) < 8:
            raise bad("비밀번호는 8자 이상 입력하세요.", "password")
        if d.get("password_confirm") is not None and d["password_confirm"] != pw:
            raise bad("비밀번호 확인이 일치하지 않습니다.", "password_confirm")
    other = self_emp or ""
    if creating and one(conn, "SELECT 1 x FROM users WHERE emp_no=?", emp_no):
        raise duplicate("이미 사용 중인 아이디입니다.", "emp_no")
    if one(conn, "SELECT 1 x FROM users WHERE lower(email)=lower(?) AND emp_no<>?", email, other):
        raise duplicate("이미 등록된 이메일입니다.", "email")
    if one(conn, "SELECT 1 x FROM users WHERE replace(phone,'-','')=? AND emp_no<>?",
           re.sub(r"\D", "", phone), other):
        raise duplicate("이미 등록된 전화번호입니다.", "phone")


def groups_of(conn, emp_no: str) -> list[dict]:
    return rows(conn, "SELECT g.AuthCd code, g.AuthNm name FROM TB_SYS_AuthUser u "
                      "JOIN TB_SYS_AuthGroup g ON g.AuthCd=u.AuthCd WHERE u.EmpNo=? ORDER BY g.AuthCd", emp_no)


def user_out(conn, u: dict) -> dict:
    """응답에 password_hash, totp_secret을 넣지 않는다."""
    return {"emp_no": u["emp_no"], "last_name": u["last_name"], "first_name": u["first_name"],
            "display_name": u["display_name"], "email": u["email"], "phone": u["phone"],
            "birth_date": u["birth_date"], "status": u["status"], "totp_enabled": bool(u["totp_enabled"]),
            "groups": groups_of(conn, u["emp_no"]), "created_at": u["created_at"]}
