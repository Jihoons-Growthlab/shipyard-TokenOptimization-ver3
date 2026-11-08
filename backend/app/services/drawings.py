"""F07 도면·리비전·PDF·배포 (BR-06, BR-07, BR-08)."""
import secrets
from typing import AsyncIterator

from .. import config
from ..db import one, rows, tx
from ..errors import ApiError, bad, conflict, duplicate, not_found
from .common import check_approved, check_code, clean, hull_exists
from .plans import PLAN_SELECT, get_drawing_row, sort_key
from .rules import file_path, impacts, plan_label, recalc_hull, remove_files

MAX_PDF = 30 * 1024 * 1024
DWG_SELECT = """
    SELECT d.*, b.BlockCd, b.BlockNm, u.display_name DesignerNm,
           (SELECT MAX(r.RevNo) FROM TB_DWG_Revision r WHERE r.DrawingId=d.DrawingId) LatestRevNo,
           (SELECT COUNT(*) FROM TB_DWG_PlanLink l WHERE l.DrawingId=d.DrawingId) LinkCount
    FROM TB_DWG_Drawing d
    LEFT JOIN TB_MST_Block b ON b.BlockId=d.BlockId
    LEFT JOIN users u ON u.emp_no=d.DesignerEmpNo"""


def _rev_state(msg_key: str) -> ApiError:
    return conflict("INVALID_REV_STATE", {
        "new": "최신 리비전이 배포/폐기 상태일 때만 신규 리비전을 작성할 수 있습니다.",
        "request": "최신 작성중(DRAFT) 리비전만 결재 요청할 수 있습니다.",
        "issue": "승인(APPROVED)된 리비전만 배포할 수 있습니다.",
        "upload": "작성중(DRAFT) 리비전만 업로드할 수 있습니다.",
        "delete_file": "작성중(DRAFT) 리비전만 파일을 삭제할 수 있습니다.",
    }[msg_key])


def item_out(r: dict) -> dict:
    return {"drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"], "drawing_nm": r["DrawingNm"],
            "hull_no": r["HullNo"], "block_id": r["BlockId"], "block_cd": r["BlockCd"], "discipline": r["Discipline"],
            "dwg_status": r["DwgStatus"], "current_rev_no": r["CurrentRevNo"], "latest_rev_no": r["LatestRevNo"],
            "designer_emp_no": r["DesignerEmpNo"], "designer_nm": r["DesignerNm"], "link_count": r["LinkCount"]}


def list_drawings(conn, hull_no=None, discipline=None, status=None, q=None) -> list[dict]:
    sql, args = DWG_SELECT + " WHERE 1=1", []
    for col, v in (("d.HullNo", hull_no), ("d.Discipline", discipline), ("d.DwgStatus", status)):
        if v:
            sql += f" AND {col}=?"
            args.append(v)
    if q and q.strip():
        sql += " AND (lower(d.DrawingNo) LIKE ? OR lower(d.DrawingNm) LIKE ?)"
        args += [f"%{q.strip().lower()}%"] * 2
    return [item_out(r) for r in rows(conn, sql + " ORDER BY d.DrawingId", *args)]


def revisions(conn, drawing_id: int) -> list[dict]:
    out = rows(conn, "SELECT r.RevNo rev_no, r.RevStatus rev_status, r.ChangeDesc change_desc, r.FileId IS NOT NULL has_file, "
                     "r.FileNm file_nm, r.AuthorEmpNo author_emp_no, u.display_name author_nm, r.IssueDt issue_dt, "
                     "r.CreateDt create_dt FROM TB_DWG_Revision r LEFT JOIN users u ON u.emp_no=r.AuthorEmpNo "
                     "WHERE r.DrawingId=? ORDER BY r.RevNo DESC", drawing_id)
    for r in out:
        r["has_file"] = bool(r["has_file"])
    return out


def _linked_plans(conn, d: dict) -> tuple[list[dict], list[dict]]:
    links = {r["PlanId"]: r for r in rows(conn, "SELECT PlanId, RequiredYN, NeedDt FROM TB_DWG_PlanLink WHERE DrawingId=?",
                                          d["DrawingId"])}
    plans, available = [], []
    for p in sorted(rows(conn, PLAN_SELECT + " WHERE p.HullNo=?", d["HullNo"]), key=sort_key):
        base = {"plan_id": p["PlanId"], "label": plan_label(p["BlockCd"], p["ProcNm"]), "plan_status": p["PlanStatus"]}
        if p["PlanId"] in links:
            lk = links[p["PlanId"]]
            plans.append({**base, "required": bool(lk["RequiredYN"]), "need_dt": lk["NeedDt"],
                          "plan_start_dt": p["PlanStartDt"], "plan_end_dt": p["PlanEndDt"]})
        else:
            available.append(base)
    return plans, available


def detail(conn, drawing_id: int) -> dict:
    r = one(conn, DWG_SELECT + " WHERE d.DrawingId=?", drawing_id)
    if not r:
        raise not_found("DRAWING_NOT_FOUND", "도면을 찾을 수 없습니다.")
    plans, available = _linked_plans(conn, r)
    approvals = rows(conn, "SELECT a.ApprovalId approval_id, a.RevNo rev_no, a.StepNo step_no, a.ApproverEmpNo approver_emp_no, "
                           "u.display_name approver_nm, a.Result result, a.Comment comment, a.ActDt act_dt "
                           "FROM TB_DWG_Approval a LEFT JOIN users u ON u.emp_no=a.ApproverEmpNo "
                           "WHERE a.DrawingId=? ORDER BY a.RevNo DESC, a.StepNo", drawing_id)
    return {**item_out(r), "block_nm": r["BlockNm"], "create_user_id": r["CreateUserId"], "create_dt": r["CreateDt"],
            "modify_user_id": r["ModifyUserId"], "modify_dt": r["ModifyDt"], "today": config.TODAY,
            "revisions": revisions(conn, drawing_id), "approvals": approvals, "plans": plans,
            "available_plans": available, "impacts": impacts(conn, drawing_id)}


def _check_block(conn, hull_no, block_id) -> None:
    if block_id is not None and not one(conn, "SELECT 1 x FROM TB_MST_Block WHERE BlockId=? AND HullNo=?", block_id, hull_no):
        raise bad("해당 호선의 블록이 아닙니다.", "block_id")


def _norm(body: dict) -> dict:
    return {k: clean(v) if isinstance(v, str) else v for k, v in body.items()}


def create(conn, body: dict, user: dict) -> dict:
    d = _norm(body)
    if not d.get("drawing_no"):
        raise bad("도면번호를 입력하세요.", "drawing_no")
    if not hull_exists(conn, d.get("hull_no")):
        raise bad("호선을 선택하세요.", "hull_no")
    if not d.get("drawing_nm"):
        raise bad("도면명을 입력하세요.", "drawing_nm")
    check_code(conn, "DWGDISC", d.get("discipline"), "discipline", "허용되지 않는 분야입니다.")
    _check_block(conn, d["hull_no"], d.get("block_id"))
    check_approved(conn, d.get("designer_emp_no"), "designer_emp_no", "승인된 회원만 지정할 수 있습니다.")
    if one(conn, "SELECT 1 x FROM TB_DWG_Drawing WHERE DrawingNo=?", d["drawing_no"]):
        raise duplicate("이미 존재하는 도면번호입니다.", "drawing_no")
    with tx(conn):
        cur = conn.execute(
            "INSERT INTO TB_DWG_Drawing(DrawingNo, DrawingNm, HullNo, BlockId, Discipline, DwgStatus, CurrentRevNo, "
            "DesignerEmpNo, UseYN, CreateUserId, CreateDt) VALUES (?,?,?,?,?,'DRAFT',0,?,1,?,?)",
            (d["drawing_no"], d["drawing_nm"], d["hull_no"], d.get("block_id"), d.get("discipline"),
             d.get("designer_emp_no"), user["emp_no"], config.TODAY))
        conn.execute("INSERT INTO TB_DWG_Revision(DrawingId, RevNo, RevStatus, ChangeDesc, AuthorEmpNo, CreateDt) "
                     "VALUES (?,0,'DRAFT','최초 작성',?,?)", (cur.lastrowid, user["emp_no"], config.TODAY))
    return detail(conn, cur.lastrowid)


EDIT_COLS = {"drawing_nm": "DrawingNm", "discipline": "Discipline", "block_id": "BlockId", "designer_emp_no": "DesignerEmpNo"}


def update(conn, drawing_id: int, body: dict, user: dict) -> dict:
    cur = get_drawing_row(conn, drawing_id)
    d = _norm(body)
    if "hull_no" in body and d.get("hull_no") != cur["HullNo"]:
        raise bad("호선은 변경할 수 없습니다.", "hull_no")
    if "drawing_no" in body and d.get("drawing_no") != cur["DrawingNo"]:
        raise bad("도면번호는 변경할 수 없습니다.", "drawing_no")
    changes = {k: d.get(k) for k in EDIT_COLS if k in body}
    if "drawing_nm" in changes and not changes["drawing_nm"]:
        raise bad("도면명을 입력하세요.", "drawing_nm")
    check_code(conn, "DWGDISC", changes.get("discipline"), "discipline", "허용되지 않는 분야입니다.")
    if "block_id" in changes:
        _check_block(conn, cur["HullNo"], changes["block_id"])
    check_approved(conn, changes.get("designer_emp_no"), "designer_emp_no", "승인된 회원만 지정할 수 있습니다.")
    changes_db = {EDIT_COLS[k]: v for k, v in changes.items()}
    changes_db.update(ModifyUserId=user["emp_no"], ModifyDt=config.TODAY)
    with tx(conn):
        conn.execute(f"UPDATE TB_DWG_Drawing SET {','.join(c + '=?' for c in changes_db)} WHERE DrawingId=?",
                     [*changes_db.values(), drawing_id])
    return detail(conn, drawing_id)


def delete(conn, drawing_id: int) -> None:
    d = get_drawing_row(conn, drawing_id)
    files = [r["FileId"] for r in rows(conn, "SELECT FileId FROM TB_DWG_Revision WHERE DrawingId=? AND FileId IS NOT NULL", drawing_id)]
    with tx(conn):
        conn.execute("DELETE FROM TB_DWG_Drawing WHERE DrawingId=?", (drawing_id,))
        recalc_hull(conn, d["HullNo"])
    remove_files(files)


# ---- 리비전
def _rev(conn, drawing_id: int, rev_no: int) -> dict:
    get_drawing_row(conn, drawing_id)
    r = one(conn, "SELECT * FROM TB_DWG_Revision WHERE DrawingId=? AND RevNo=?", drawing_id, rev_no)
    if not r:
        raise not_found("REVISION_NOT_FOUND", "리비전을 찾을 수 없습니다.")
    return r


def _latest(conn, drawing_id: int) -> dict | None:
    return one(conn, "SELECT * FROM TB_DWG_Revision WHERE DrawingId=? ORDER BY RevNo DESC LIMIT 1", drawing_id)


def new_revision(conn, drawing_id: int, change_desc, user: dict) -> dict:
    d = get_drawing_row(conn, drawing_id)
    desc = clean(change_desc)
    if not desc:
        raise bad("개정 사유를 입력하세요.", "change_desc")
    latest = _latest(conn, drawing_id)
    if latest and latest["RevStatus"] not in ("ISSUED", "OBSOLETE"):
        raise _rev_state("new")
    rev_no = (latest["RevNo"] + 1) if latest else 0
    with tx(conn):
        conn.execute("INSERT INTO TB_DWG_Revision(DrawingId, RevNo, RevStatus, ChangeDesc, AuthorEmpNo, CreateDt) "
                     "VALUES (?,?,'DRAFT',?,?,?)", (drawing_id, rev_no, desc, user["emp_no"], config.TODAY))
        conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus='DRAFT', ModifyUserId=?, ModifyDt=? WHERE DrawingId=?",
                     (user["emp_no"], config.TODAY, drawing_id))
        recalc_hull(conn, d["HullNo"])
    return detail(conn, drawing_id)


def request_approval(conn, drawing_id: int, rev_no: int, reviewer, approver) -> dict:
    d = get_drawing_row(conn, drawing_id)
    rev = _rev(conn, drawing_id, rev_no)
    latest = _latest(conn, drawing_id)
    if rev["RevStatus"] != "DRAFT" or latest["RevNo"] != rev_no:
        raise _rev_state("request")
    reviewer, approver = clean(reviewer), clean(approver)
    if not reviewer or not approver:
        raise bad("검토자와 승인자를 선택하세요.", "reviewer_emp_no" if not reviewer else "approver_emp_no")
    if reviewer == approver:
        raise bad("검토자와 승인자는 서로 다른 사람이어야 합니다.", "approver_emp_no")
    check_approved(conn, reviewer, "reviewer_emp_no", "승인된 회원만 지정할 수 있습니다.")
    check_approved(conn, approver, "approver_emp_no", "승인된 회원만 지정할 수 있습니다.")
    with tx(conn):
        conn.execute("DELETE FROM TB_DWG_Approval WHERE DrawingId=? AND RevNo=?", (drawing_id, rev_no))
        conn.executemany("INSERT INTO TB_DWG_Approval(DrawingId, RevNo, StepNo, ApproverEmpNo, Result) VALUES (?,?,?,?,'WAIT')",
                         [(drawing_id, rev_no, 1, reviewer), (drawing_id, rev_no, 2, approver)])
        conn.execute("UPDATE TB_DWG_Revision SET RevStatus='REVIEW' WHERE DrawingId=? AND RevNo=?", (drawing_id, rev_no))
        conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus='REVIEW' WHERE DrawingId=?", (drawing_id,))
        recalc_hull(conn, d["HullNo"])
    return detail(conn, drawing_id)


def issue(conn, drawing_id: int, rev_no: int) -> dict:
    d = get_drawing_row(conn, drawing_id)
    rev = _rev(conn, drawing_id, rev_no)
    if rev["RevStatus"] != "APPROVED":
        raise _rev_state("issue")
    results = [r["Result"] for r in rows(conn, "SELECT Result FROM TB_DWG_Approval WHERE DrawingId=? AND RevNo=?",
                                         drawing_id, rev_no)]
    if not results or any(x != "APPROVE" for x in results):
        raise conflict("APPROVAL_INCOMPLETE", "결재가 완료된 리비전만 배포할 수 있습니다.")
    with tx(conn):
        conn.execute("UPDATE TB_DWG_Revision SET RevStatus='OBSOLETE' WHERE DrawingId=? AND RevStatus='ISSUED'", (drawing_id,))
        conn.execute("UPDATE TB_DWG_Revision SET RevStatus='ISSUED', IssueDt=? WHERE DrawingId=? AND RevNo=?",
                     (config.TODAY, drawing_id, rev_no))
        conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus='ISSUED', CurrentRevNo=? WHERE DrawingId=?", (rev_no, drawing_id))
        recalc_hull(conn, d["HullNo"])
    return detail(conn, drawing_id)


# ---- PDF
def sanitize_filename(name: str | None) -> str:
    base = (name or "").replace("\\", "/").split("/")[-1].strip().replace("\x00", "")
    return (base or "drawing.pdf")[:200]


def _too_large() -> ApiError:
    return ApiError(413, "FILE_TOO_LARGE", "파일 크기는 30MB 이하여야 합니다.")


def _not_pdf() -> ApiError:
    return bad("PDF 파일만 업로드할 수 있습니다.", "file", "INVALID_FILE_TYPE")


async def upload_pdf(conn, drawing_id: int, rev_no: int, filename: str | None, content_type: str | None,
                     content_length: str | None, stream: AsyncIterator[bytes]) -> dict:
    rev = _rev(conn, drawing_id, rev_no)
    if rev["RevStatus"] != "DRAFT":
        raise _rev_state("upload")
    name = sanitize_filename(filename)
    ctype = (content_type or "").split(";")[0].strip().lower()
    if not (name.lower().endswith(".pdf") or ctype == "application/pdf"):
        raise _not_pdf()
    if content_length and content_length.isdigit() and int(content_length) > MAX_PDF:
        raise _too_large()
    file_id = secrets.token_hex(16)
    path = file_path(file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    size, head = 0, b""
    try:
        with open(path, "wb") as f:
            async for chunk in stream:
                size += len(chunk)
                if size > MAX_PDF:
                    raise _too_large()
                if len(head) < 5:
                    head += chunk[:5 - len(head)]
                f.write(chunk)
        if not head.startswith(b"%PDF-"):
            raise _not_pdf()
        with tx(conn):
            conn.execute("UPDATE TB_DWG_Revision SET FileId=?, FileNm=? WHERE DrawingId=? AND RevNo=?",
                         (file_id, name, drawing_id, rev_no))
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    remove_files([rev["FileId"]])
    return detail(conn, drawing_id)


def pdf_path(conn, drawing_id: int, rev_no: int):
    rev = _rev(conn, drawing_id, rev_no)
    if not rev["FileId"]:
        raise not_found("NO_FILE", "이 리비전에는 업로드된 도면 파일이 없습니다.")
    path = file_path(rev["FileId"])
    if not path.is_file():
        raise not_found("FILE_NOT_FOUND", "도면 파일을 찾을 수 없습니다.")
    return path, rev["FileNm"] or f"{rev['FileId']}.pdf"


def delete_pdf(conn, drawing_id: int, rev_no: int) -> dict:
    rev = _rev(conn, drawing_id, rev_no)
    if rev["RevStatus"] != "DRAFT":
        raise _rev_state("delete_file")
    if not rev["FileId"]:
        raise not_found("NO_FILE", "이 리비전에는 업로드된 도면 파일이 없습니다.")
    with tx(conn):
        conn.execute("UPDATE TB_DWG_Revision SET FileId=NULL, FileNm=NULL WHERE DrawingId=? AND RevNo=?", (drawing_id, rev_no))
    remove_files([rev["FileId"]])
    return detail(conn, drawing_id)


def drawing_plans(conn, drawing_id: int) -> dict:
    d = get_drawing_row(conn, drawing_id)
    plans, available = _linked_plans(conn, d)
    return {"drawing_id": drawing_id, "plans": plans, "available_plans": available}
