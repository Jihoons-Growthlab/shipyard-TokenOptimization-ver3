"""F08 결재함 (BR-06)."""
from ..db import one, rows, tx
from ..errors import ApiError, bad, conflict, not_found
from .common import WRITE, act_dt, clean, menu_level
from .rules import plan_label, recalc_hull

_CURRENT = """
    r.RevStatus='REVIEW'
    AND r.RevNo=(SELECT MAX(r2.RevNo) FROM TB_DWG_Revision r2 WHERE r2.DrawingId=a.DrawingId)
    AND NOT EXISTS (SELECT 1 FROM TB_DWG_Approval p WHERE p.DrawingId=a.DrawingId AND p.RevNo=a.RevNo
                    AND p.StepNo<a.StepNo AND p.Result<>'APPROVE')"""


def waiting(conn, emp_no: str) -> list[dict]:
    return rows(conn, f"""
        SELECT a.ApprovalId approval_id, a.DrawingId drawing_id, d.DrawingNo drawing_no, d.DrawingNm drawing_nm,
               a.RevNo rev_no, a.StepNo step_no, r.ChangeDesc change_desc
        FROM TB_DWG_Approval a
        JOIN TB_DWG_Revision r ON r.DrawingId=a.DrawingId AND r.RevNo=a.RevNo
        JOIN TB_DWG_Drawing d ON d.DrawingId=a.DrawingId
        WHERE a.ApproverEmpNo=? AND a.Result='WAIT' AND {_CURRENT}
        ORDER BY a.ApprovalId""", emp_no)


def ready(conn) -> list[dict]:
    out = rows(conn, """
        SELECT d.DrawingId drawing_id, d.DrawingNo drawing_no, d.DrawingNm drawing_nm, r.RevNo rev_no
        FROM TB_DWG_Drawing d JOIN TB_DWG_Revision r ON r.DrawingId=d.DrawingId
         AND r.RevNo=(SELECT MAX(r2.RevNo) FROM TB_DWG_Revision r2 WHERE r2.DrawingId=d.DrawingId)
        WHERE r.RevStatus='APPROVED' ORDER BY d.DrawingId""")
    for x in out:
        x["effect_plans"] = [plan_label(p["BlockCd"], p["ProcNm"]) for p in rows(conn, """
            SELECT b.BlockCd, pr.ProcNm FROM TB_DWG_PlanLink l JOIN TB_PRC_Plan p ON p.PlanId=l.PlanId
            JOIN TB_PRC_Proc pr ON pr.ProcCd=p.ProcCd LEFT JOIN TB_MST_Block b ON b.BlockId=p.BlockId
            WHERE l.DrawingId=? AND p.PlanStatus='PLAN' ORDER BY p.PlanStartDt, p.PlanId""", x["drawing_id"])]
    return out


def inbox(conn, user: dict) -> dict:
    return {"waiting": waiting(conn, user["emp_no"]), "ready": ready(conn),
            "can_issue": menu_level(conn, user["emp_no"], "M31") >= WRITE}


def decide(conn, approval_id: int, result, comment, user: dict) -> dict:
    if result not in ("APPROVE", "REJECT"):
        raise bad("결재 결과는 APPROVE 또는 REJECT 이어야 합니다.", "result")
    comment = clean(comment)
    if result == "REJECT" and not comment:
        raise bad("반려 시 의견을 입력하세요.", "comment")
    a = one(conn, "SELECT * FROM TB_DWG_Approval WHERE ApprovalId=?", approval_id)
    if not a:
        raise not_found("APPROVAL_NOT_FOUND", "결재 건을 찾을 수 없습니다.")
    if a["ApproverEmpNo"] != user["emp_no"]:
        raise ApiError(403, "NOT_ASSIGNED_APPROVER", "본인에게 지정된 결재 건이 아닙니다.")
    if a["Result"] != "WAIT":
        raise conflict("ALREADY_DECIDED", "이미 처리된 결재 건입니다.")
    if not one(conn, f"SELECT 1 x FROM TB_DWG_Approval a JOIN TB_DWG_Revision r ON r.DrawingId=a.DrawingId "
                     f"AND r.RevNo=a.RevNo WHERE a.ApprovalId=? AND {_CURRENT}", approval_id):
        raise conflict("NOT_CURRENT_STEP", "결재 순서가 아니거나 최신 검토중 리비전이 아닙니다.")
    did, rev = a["DrawingId"], a["RevNo"]
    hull_no = one(conn, "SELECT HullNo FROM TB_DWG_Drawing WHERE DrawingId=?", did)["HullNo"]
    with tx(conn):
        conn.execute("UPDATE TB_DWG_Approval SET Result=?, Comment=?, ActDt=? WHERE ApprovalId=?",
                     (result, comment or ("승인" if result == "APPROVE" else None), act_dt(), approval_id))
        if result == "APPROVE":
            pending = conn.execute("SELECT COUNT(*) FROM TB_DWG_Approval WHERE DrawingId=? AND RevNo=? AND Result<>'APPROVE'",
                                   (did, rev)).fetchone()[0]
            if not pending:
                conn.execute("UPDATE TB_DWG_Revision SET RevStatus='APPROVED' WHERE DrawingId=? AND RevNo=?", (did, rev))
                conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus='APPROVED' WHERE DrawingId=?", (did,))
        else:
            conn.execute("UPDATE TB_DWG_Revision SET RevStatus='DRAFT' WHERE DrawingId=? AND RevNo=?", (did, rev))
            conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus='DRAFT' WHERE DrawingId=?", (did,))
            conn.execute("DELETE FROM TB_DWG_Approval WHERE DrawingId=? AND RevNo=? AND Result='WAIT'", (did, rev))
        recalc_hull(conn, hull_no)
    return {"approval_id": approval_id, "result": result, "waiting": waiting(conn, user["emp_no"]), "ready": ready(conn)}


def history(conn) -> list[dict]:
    return rows(conn, """
        SELECT a.ApprovalId approval_id, a.ActDt act_dt, a.DrawingId drawing_id, d.DrawingNo drawing_no, a.RevNo rev_no,
               a.StepNo step_no, a.ApproverEmpNo approver_emp_no, u.display_name approver_nm, a.Result result,
               a.Comment comment
        FROM TB_DWG_Approval a JOIN TB_DWG_Drawing d ON d.DrawingId=a.DrawingId
        LEFT JOIN users u ON u.emp_no=a.ApproverEmpNo
        WHERE a.Result<>'WAIT' ORDER BY a.ActDt DESC, a.ApprovalId DESC LIMIT 10""")
