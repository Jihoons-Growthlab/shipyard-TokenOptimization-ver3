"""건의·문의(명세 외 요청 기능). 회원은 본인 글을 쓰고 보며, 관리자(Admin 등급)는 전체를 보고 처리한다."""
from ..db import one, rows, tx
from ..errors import ApiError, bad, not_found
from .common import ADMIN, clean, menu_level, now_utc

MENU = "M95"
CATEGORIES = {"BUG": "오류 신고", "FEATURE": "기능 건의", "QUESTION": "사용 문의", "ETC": "기타"}
STATUSES = {"OPEN": "접수", "IN_PROGRESS": "처리중", "DONE": "완료", "REJECTED": "반려"}

SELECT = """SELECT q.*, cu.display_name AS CreateUserNm, au.display_name AS AnswerUserNm FROM TB_SYS_Inquiry q
    LEFT JOIN users cu ON cu.emp_no=q.CreateUserId LEFT JOIN users au ON au.emp_no=q.AnswerUserId"""


def is_admin(conn, user) -> bool:
    return menu_level(conn, user["emp_no"], MENU) >= ADMIN


def _out(r: dict, user_id: str) -> dict:
    return {"inquiry_id": r["InquiryId"], "category": r["Category"], "title": r["Title"], "content": r["Content"],
            "status": r["Status"], "create_user_id": r["CreateUserId"], "create_user_nm": r["CreateUserNm"],
            "create_dt": r["CreateDt"], "modify_dt": r["ModifyDt"], "answer": r["Answer"],
            "answer_user_nm": r["AnswerUserNm"], "answer_dt": r["AnswerDt"], "mine": r["CreateUserId"] == user_id}


def _forbidden() -> ApiError:
    return ApiError(403, "FORBIDDEN", "본인이 작성한 글만 볼 수 있습니다.", {"menu_id": MENU})


def _get(conn, inquiry_id: int, user) -> dict:
    r = one(conn, SELECT + " WHERE q.InquiryId=?", inquiry_id)
    if not r:
        raise not_found("INQUIRY_NOT_FOUND", "글을 찾을 수 없습니다.")
    if r["CreateUserId"] != user["emp_no"] and not is_admin(conn, user):
        raise _forbidden()
    return r


def list_inquiries(conn, user, status=None, q=None, mine=False) -> dict:
    admin = is_admin(conn, user)
    sql, args = SELECT + " WHERE 1=1", []
    if not admin or mine:
        sql += " AND q.CreateUserId=?"
        args.append(user["emp_no"])
    base_sql, base_args = sql, list(args)
    if status:
        sql += " AND q.Status=?"
        args.append(status)
    if q and q.strip():
        sql += " AND (lower(q.Title) LIKE ? OR lower(q.Content) LIKE ? OR lower(ifnull(cu.display_name,'')) LIKE ?)"
        args += [f"%{q.strip().lower()}%"] * 3
    items = [_out(r, user["emp_no"]) for r in rows(conn, sql + " ORDER BY q.InquiryId DESC", *args)]
    counts = {s: 0 for s in STATUSES}
    for r in rows(conn, base_sql.replace("SELECT q.*, cu.display_name AS CreateUserNm, au.display_name AS AnswerUserNm",
                                         "SELECT q.Status", 1), *base_args):
        counts[r["Status"]] += 1
    return {"items": items, "total": len(items), "counts": counts, "is_admin": admin,
            "categories": CATEGORIES, "statuses": STATUSES}


def get_inquiry(conn, inquiry_id: int, user) -> dict:
    return _out(_get(conn, inquiry_id, user), user["emp_no"])


def _check_body(d: dict) -> dict:
    d = {k: clean(v) for k, v in d.items()}
    if d.get("category") not in CATEGORIES:
        raise bad("분류를 선택하세요.", "category")
    if not d.get("title"):
        raise bad("제목을 입력하세요.", "title")
    if not d.get("content"):
        raise bad("내용을 입력하세요.", "content")
    return d


def _insert(conn, body, user_id, created_at):
    return conn.execute("INSERT INTO TB_SYS_Inquiry(Category, Title, Content, CreateUserId, CreateDt) VALUES (?,?,?,?,?)",
                        (body["category"], body["title"], body["content"], user_id, created_at)).lastrowid


def create(conn, body: dict, user) -> dict:
    d = _check_body(body)
    with tx(conn):
        inquiry_id = _insert(conn, d, user["emp_no"], now_utc())
    return get_inquiry(conn, inquiry_id, user)


def create_from_chat(conn, user_id, request_id, kind, content, created_at=None, legacy_id=None):
    category = {"suggestion": "FEATURE", "inquiry": "QUESTION"}[kind]
    title = content.splitlines()[0].strip()[:80]
    if legacy_id is not None:
        title = f"[FB-{legacy_id:06d}] {title}"
    body = _check_body({"category": category, "title": title, "content": content})
    with tx(conn):
        existing = one(conn, "SELECT * FROM TB_SYS_ChatInquiry WHERE CreateUserId=? AND RequestId=?",
                       user_id, request_id)
        if existing:
            if (existing["Category"], existing["Content"]) != (category, body["content"]):
                raise ValueError("Feedback request ID was already used")
            return existing["InquiryId"]
        inquiry_id = _insert(conn, body, user_id, created_at or now_utc())
        conn.execute("INSERT INTO TB_SYS_ChatInquiry VALUES (?,?,?,?,?)",
                     (user_id, request_id, inquiry_id, category, body["content"]))
        return inquiry_id


def update(conn, inquiry_id: int, body: dict, user) -> dict:
    """작성자: 접수 상태일 때 분류·제목·내용 수정. 관리자: 상태·답변 처리."""
    r = _get(conn, inquiry_id, user)
    admin = is_admin(conn, user)
    sets: dict = {}
    if any(k in body for k in ("category", "title", "content")):
        if r["CreateUserId"] != user["emp_no"]:
            raise _forbidden()
        if r["Status"] != "OPEN":
            raise ApiError(409, "INVALID_STATUS", "접수 상태인 글만 수정할 수 있습니다.")
        d = _check_body({k: body.get(k, r[c]) for k, c in (("category", "Category"), ("title", "Title"), ("content", "Content"))})
        sets.update(Category=d["category"], Title=d["title"], Content=d["content"], ModifyDt=now_utc())
    if "status" in body or "answer" in body:
        if not admin:
            raise ApiError(403, "FORBIDDEN", "관리자만 처리할 수 있습니다.", {"menu_id": MENU})
        status = body.get("status", r["Status"])
        if status not in STATUSES:
            raise bad("허용되지 않는 상태입니다.", "status")
        answer = clean(body.get("answer", r["Answer"]))
        if status in ("DONE", "REJECTED") and not answer:
            raise bad("완료·반려 처리에는 답변을 입력하세요.", "answer")
        sets.update(Status=status, Answer=answer)
        if answer != r["Answer"] or status != r["Status"]:
            sets.update(AnswerUserId=user["emp_no"], AnswerDt=now_utc())
    if sets:
        with tx(conn):
            conn.execute(f"UPDATE TB_SYS_Inquiry SET {','.join(k + '=?' for k in sets)} WHERE InquiryId=?",
                         [*sets.values(), inquiry_id])
    return get_inquiry(conn, inquiry_id, user)


def delete(conn, inquiry_id: int, user) -> None:
    r = _get(conn, inquiry_id, user)
    if not is_admin(conn, user):
        if r["Status"] != "OPEN":
            raise ApiError(409, "INVALID_STATUS", "접수 상태인 글만 삭제할 수 있습니다.")
    with tx(conn):
        conn.execute("DELETE FROM TB_SYS_Inquiry WHERE InquiryId=?", (inquiry_id,))
