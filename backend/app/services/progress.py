"""F06 공정 실적 (BR-05)."""
from .. import config
from ..db import one, rows, tx
from ..errors import bad, not_found
from .common import check_approved, clean, is_date
from .plans import get_plan, get_plan_row, hull_plans
from .rules import recalc_hull

TARGET_STATUSES = ("READY", "WORK", "DELAY")
TARGET_FIELDS = ("plan_id", "label", "plan_start_dt", "plan_end_dt", "actual_start_dt", "actual_end_dt",
                 "progress_rate", "plan_status", "manager_emp_no", "manager_nm", "drawing_wait")


def progress_hulls(conn) -> dict:
    hulls = rows(conn, "SELECT HullNo hull_no, HullNm hull_nm, HullStatus hull_status FROM TB_MST_Hull h "
                       "WHERE EXISTS (SELECT 1 FROM TB_PRC_Plan p WHERE p.HullNo=h.HullNo) ORDER BY HullNo")
    build = next((h["hull_no"] for h in hulls if h["hull_status"] == "BUILD"), None)
    return {"hulls": hulls, "default_hull_no": build or (hulls[0]["hull_no"] if hulls else None)}


def targets(conn, hull_no: str, include_done: bool) -> dict:
    from .hulls import get_hull_row
    get_hull_row(conn, hull_no)
    plans = hull_plans(conn, hull_no, statuses=None if include_done else TARGET_STATUSES)
    return {"hull_no": hull_no, "today": config.TODAY,
            "plans": [{k: p[k] for k in TARGET_FIELDS} for p in plans]}


def _history(conn, plan_id: int) -> list[dict]:
    return rows(conn, "SELECT g.ProgressId progress_id, g.PlanId plan_id, g.WorkDt work_dt, g.ProgressRate progress_rate, "
                      "g.ManHour man_hour, g.WorkerCnt worker_cnt, g.WorkerEmpNo worker_emp_no, u.display_name worker_nm, "
                      "g.Remark remark, g.CreateDt create_dt FROM TB_PRC_Progress g LEFT JOIN users u ON u.emp_no=g.WorkerEmpNo "
                      "WHERE g.PlanId=? ORDER BY g.WorkDt DESC", plan_id)


def plan_progress(conn, plan_id: int) -> dict:
    return {"plan": get_plan(conn, plan_id), "history": _history(conn, plan_id)}


def _apply(conn, plan_id: int) -> None:
    """BR-05: 마지막 작업일의 누적률 = 진척, 첫 작업일 = 실제착수, 마지막 ≥100이면 실제종료."""
    hist = rows(conn, "SELECT WorkDt, ProgressRate FROM TB_PRC_Progress WHERE PlanId=? ORDER BY WorkDt", plan_id)
    if hist:
        last = hist[-1]
        vals = (last["ProgressRate"], hist[0]["WorkDt"], last["WorkDt"] if last["ProgressRate"] >= 100 else None)
    else:
        vals = (0, None, None)
    conn.execute("UPDATE TB_PRC_Plan SET ProgressRate=?, ActualStartDt=?, ActualEndDt=? WHERE PlanId=?", (*vals, plan_id))


def save(conn, plan_id: int, work_dt: str, body: dict) -> dict:
    p = get_plan_row(conn, plan_id)
    if not is_date(work_dt):
        raise bad("작업일을 입력하세요.", "work_dt")
    if work_dt > config.TODAY:
        raise bad("미래 일자의 실적은 입력할 수 없습니다.", "work_dt")
    rate = body.get("progress_rate")
    if rate is None or not (0 <= rate <= 100):
        raise bad("진척률은 0~100 사이로 입력하세요.", "progress_rate")
    worker = clean(body.get("worker_emp_no"))
    check_approved(conn, worker, "worker_emp_no", "승인된 회원만 작업자로 지정할 수 있습니다.")
    with tx(conn):
        conn.execute(
            "INSERT INTO TB_PRC_Progress(PlanId, WorkDt, ProgressRate, ManHour, WorkerCnt, WorkerEmpNo, Remark, CreateDt) "
            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(PlanId, WorkDt) DO UPDATE SET ProgressRate=excluded.ProgressRate, "
            "ManHour=excluded.ManHour, WorkerCnt=excluded.WorkerCnt, WorkerEmpNo=excluded.WorkerEmpNo, Remark=excluded.Remark",
            (plan_id, work_dt, rate, body.get("man_hour"), body.get("worker_cnt"), worker, clean(body.get("remark")),
             config.TODAY))
        _apply(conn, plan_id)
        recalc_hull(conn, p["HullNo"])
    return plan_progress(conn, plan_id)


def delete(conn, progress_id: int) -> dict:
    g = one(conn, "SELECT g.PlanId, p.HullNo FROM TB_PRC_Progress g JOIN TB_PRC_Plan p ON p.PlanId=g.PlanId "
                  "WHERE g.ProgressId=?", progress_id)
    if not g:
        raise not_found("PROGRESS_NOT_FOUND", "실적을 찾을 수 없습니다.")
    with tx(conn):
        conn.execute("DELETE FROM TB_PRC_Progress WHERE ProgressId=?", (progress_id,))
        _apply(conn, g["PlanId"])
        recalc_hull(conn, g["HullNo"])
    return plan_progress(conn, g["PlanId"])

