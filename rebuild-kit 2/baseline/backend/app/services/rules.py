"""교차 업무 규칙 BR-01(가중 진척), BR-02(도면 게이트), BR-03(상태 재계산), BR-07(개정 영향), BR-08(파일 정리)."""
import math
from datetime import date, timedelta
from pathlib import Path

from .. import config
from ..db import rows

PLAN_STATUSES = ("PLAN", "READY", "WORK", "DONE", "DELAY")


def period_days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def weighted_progress(plans, empty=None):
    """BR-01: round(Σ(rate×일수)/Σ일수), 0.5 올림. plans 원소는 ProgressRate/PlanStartDt/PlanEndDt."""
    total = sum(period_days(p["PlanStartDt"], p["PlanEndDt"]) for p in plans)
    if not plans or total <= 0:
        return empty
    s = sum(p["ProgressRate"] * period_days(p["PlanStartDt"], p["PlanEndDt"]) for p in plans)
    return int(math.floor(s / total + 0.5))


def plan_label(block_cd, proc_nm) -> str:
    return f"[{block_cd}] {proc_nm}" if block_cd else f"[호선] {proc_nm}"


def blockers_by_plan(conn, hull_no: str | None = None, plan_id: int | None = None) -> dict[int, list[dict]]:
    """BR-02: 필수 연계 도면 중 OBSOLETE가 아니고 ISSUED 리비전이 하나도 없는 도면. 도면번호순."""
    sql = ("SELECT l.PlanId, d.DrawingId drawing_id, d.DrawingNo drawing_no, d.DwgStatus dwg_status "
           "FROM TB_DWG_PlanLink l JOIN TB_DWG_Drawing d ON d.DrawingId=l.DrawingId "
           "JOIN TB_PRC_Plan p ON p.PlanId=l.PlanId "
           "WHERE l.RequiredYN=1 AND d.DwgStatus<>'OBSOLETE' AND NOT EXISTS "
           "(SELECT 1 FROM TB_DWG_Revision r WHERE r.DrawingId=d.DrawingId AND r.RevStatus='ISSUED')")
    args = []
    if hull_no is not None:
        sql += " AND p.HullNo=?"
        args.append(hull_no)
    if plan_id is not None:
        sql += " AND p.PlanId=?"
        args.append(plan_id)
    out: dict[int, list[dict]] = {}
    for r in rows(conn, sql + " ORDER BY d.DrawingNo", *args):
        out.setdefault(r.pop("PlanId"), []).append(r)
    return out


def preds_by_plan(conn, hull_no: str) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for r in rows(conn, "SELECT d.PlanId, d.PredPlanId FROM TB_PRC_PlanDep d JOIN TB_PRC_Plan p ON p.PlanId=d.PlanId "
                        "WHERE p.HullNo=? ORDER BY d.PlanId, d.PredPlanId", hull_no):
        out.setdefault(r["PlanId"], []).append(r["PredPlanId"])
    return out


def plan_status(p: dict, preds: list[int], progress: dict[int, float], blocked: bool, today: str) -> str:
    """BR-03 1~4."""
    if p["ProgressRate"] >= 100:
        return "DONE"
    if p["ProgressRate"] > 0 or p["ActualStartDt"]:
        return "DELAY" if p["PlanEndDt"] < today else "WORK"
    if p["PlanEndDt"] < today:
        return "DELAY"
    if all(progress.get(x, 0) >= 100 for x in preds) and not blocked:
        return "READY"
    return "PLAN"


def recalc_hull(conn, hull_no: str) -> None:
    """BR-03: 호선의 모든 공정 상태 재계산 + 호선 자동 전이. 호출자의 트랜잭션 안에서 실행한다."""
    plans = rows(conn, "SELECT PlanId, ProcCd, ProgressRate, ActualStartDt, PlanEndDt, PlanStatus "
                       "FROM TB_PRC_Plan WHERE HullNo=?", hull_no)
    progress = {p["PlanId"]: p["ProgressRate"] for p in plans}
    preds = preds_by_plan(conn, hull_no)
    blockers = blockers_by_plan(conn, hull_no)
    statuses = {}
    for p in plans:
        st = plan_status(p, preds.get(p["PlanId"], []), progress, bool(blockers.get(p["PlanId"])), config.TODAY)
        statuses[p["PlanId"]] = st
        if st != p["PlanStatus"]:
            conn.execute("UPDATE TB_PRC_Plan SET PlanStatus=? WHERE PlanId=?", (st, p["PlanId"]))
    hull = rows(conn, "SELECT HullStatus FROM TB_MST_Hull WHERE HullNo=?", hull_no)
    if not hull:
        return
    cur = new = hull[0]["HullStatus"]
    if new == "DESIGN" and "WORK" in statuses.values():
        new = "BUILD"
    if new == "BUILD" and any(p["ProcCd"] == "LAUNCH" and statuses[p["PlanId"]] == "DONE" for p in plans):
        new = "LAUNCH"
    if new != cur:
        conn.execute("UPDATE TB_MST_Hull SET HullStatus=? WHERE HullNo=?", (new, hull_no))


def recalc_hulls(conn, hull_nos) -> None:
    for h in dict.fromkeys(hull_nos):
        if h:
            recalc_hull(conn, h)


def impacts(conn, drawing_id: int | None = None, active_hulls_only: bool = False) -> list[dict]:
    """BR-07: 도면별 Rev≥1 ISSUED, IssueDt∈[오늘-30, 오늘]인 최대 Rev의 연계 공정 중 WORK/DONE/DELAY."""
    t = config.today()
    start, end = (t - timedelta(days=30)).isoformat(), t.isoformat()
    sql = """
        SELECT d.DrawingId, d.DrawingNo, r.RevNo, r.IssueDt, r.ChangeDesc, p.PlanId, p.HullNo, p.PlanStatus,
               b.BlockCd, pr.ProcNm
        FROM TB_DWG_Drawing d
        JOIN TB_DWG_Revision r ON r.DrawingId=d.DrawingId AND r.RevNo=(
             SELECT MAX(r2.RevNo) FROM TB_DWG_Revision r2 WHERE r2.DrawingId=d.DrawingId AND r2.RevNo>=1
             AND r2.RevStatus='ISSUED' AND r2.IssueDt BETWEEN ? AND ?)
        JOIN TB_DWG_PlanLink l ON l.DrawingId=d.DrawingId
        JOIN TB_PRC_Plan p ON p.PlanId=l.PlanId
        JOIN TB_PRC_Proc pr ON pr.ProcCd=p.ProcCd
        JOIN TB_MST_Hull h ON h.HullNo=p.HullNo
        LEFT JOIN TB_MST_Block b ON b.BlockId=p.BlockId
        WHERE p.PlanStatus IN ('WORK','DONE','DELAY')"""
    args: list = [start, end]
    if drawing_id is not None:
        sql += " AND d.DrawingId=?"
        args.append(drawing_id)
    if active_hulls_only:
        sql += " AND h.UseYN=1"
    sql += " ORDER BY r.IssueDt DESC, d.DrawingNo, p.PlanId"
    return [{"drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"], "rev_no": r["RevNo"],
             "issue_dt": r["IssueDt"], "plan_id": r["PlanId"], "plan_label": plan_label(r["BlockCd"], r["ProcNm"]),
             "plan_status": r["PlanStatus"], "hull_no": r["HullNo"], "change_desc": r["ChangeDesc"],
             "link": {"screen": "drawing", "param": r["DrawingId"]}}
            for r in rows(conn, sql, *args)]


# ---- BR-08 파일
def file_path(file_id: str) -> Path:
    return config.file_dir() / f"{file_id}.pdf"


def remove_files(file_ids) -> None:
    """DB 커밋 후 호출한다."""
    for fid in file_ids:
        if fid:
            try:
                file_path(fid).unlink(missing_ok=True)
            except OSError:
                pass
