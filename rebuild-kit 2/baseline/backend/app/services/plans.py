"""F05 공정 계획·선후행·도면 연계."""
from datetime import date, timedelta

from .. import config
from ..db import one, rows, tx
from ..errors import ApiError, bad, duplicate, not_found
from .common import check_approved, clean, is_date
from .rules import blockers_by_plan, plan_label, recalc_hull, weighted_progress

PLAN_SELECT = """
    SELECT p.*, b.BlockCd, b.BlockNm, pr.ProcNm, pr.Seq AS ProcSeq, u.display_name AS ManagerNm
    FROM TB_PRC_Plan p
    JOIN TB_PRC_Proc pr ON pr.ProcCd=p.ProcCd
    LEFT JOIN TB_MST_Block b ON b.BlockId=p.BlockId
    LEFT JOIN users u ON u.emp_no=p.ManagerEmpNo"""


def sort_key(p: dict):
    """블록코드 숫자순(비숫자 뒤), 블록 없는 공정 맨 뒤, 표준공정 Seq, PlanId."""
    cd = p["BlockCd"]
    if cd is None:
        bk = (2, 0, "")
    elif cd.isdigit():
        bk = (0, int(cd), cd)
    else:
        bk = (1, 0, cd)
    return (*bk, p["ProcSeq"], p["PlanId"])


def plan_out(p: dict, preds: list[int], blockers: list[dict]) -> dict:
    return {"plan_id": p["PlanId"], "hull_no": p["HullNo"], "block_id": p["BlockId"], "block_cd": p["BlockCd"],
            "block_nm": p["BlockNm"], "proc_cd": p["ProcCd"], "proc_nm": p["ProcNm"],
            "label": plan_label(p["BlockCd"], p["ProcNm"]), "plan_start_dt": p["PlanStartDt"],
            "plan_end_dt": p["PlanEndDt"], "actual_start_dt": p["ActualStartDt"], "actual_end_dt": p["ActualEndDt"],
            "progress_rate": p["ProgressRate"], "plan_status": p["PlanStatus"], "manager_emp_no": p["ManagerEmpNo"],
            "manager_nm": p["ManagerNm"], "remark": p["Remark"], "create_user_id": p["CreateUserId"],
            "create_dt": p["CreateDt"], "pred_plan_ids": preds, "gate_ok": not blockers, "blockers": blockers,
            "drawing_wait": p["PlanStatus"] == "PLAN" and bool(blockers)}


def _preds_map(conn, hull_no: str) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for r in rows(conn, "SELECT d.PlanId, d.PredPlanId FROM TB_PRC_PlanDep d JOIN TB_PRC_Plan p ON p.PlanId=d.PlanId "
                        "WHERE p.HullNo=? ORDER BY d.PredPlanId", hull_no):
        out.setdefault(r["PlanId"], []).append(r["PredPlanId"])
    return out


def hull_plans(conn, hull_no: str, block_id: int | None = None, statuses=None) -> list[dict]:
    sql, args = PLAN_SELECT + " WHERE p.HullNo=?", [hull_no]
    if block_id is not None:
        sql += " AND p.BlockId=?"
        args.append(block_id)
    if statuses:
        sql += f" AND p.PlanStatus IN ({','.join('?' * len(statuses))})"
        args += list(statuses)
    preds, blockers = _preds_map(conn, hull_no), blockers_by_plan(conn, hull_no)
    return [plan_out(p, preds.get(p["PlanId"], []), blockers.get(p["PlanId"], []))
            for p in sorted(rows(conn, sql, *args), key=sort_key)]


def get_plan_row(conn, plan_id: int) -> dict:
    p = one(conn, "SELECT * FROM TB_PRC_Plan WHERE PlanId=?", plan_id)
    if not p:
        raise not_found("PLAN_NOT_FOUND", "공정을 찾을 수 없습니다.")
    return p


def get_plan(conn, plan_id: int) -> dict:
    p = one(conn, PLAN_SELECT + " WHERE p.PlanId=?", plan_id)
    if not p:
        raise not_found("PLAN_NOT_FOUND", "공정을 찾을 수 없습니다.")
    preds = [r["PredPlanId"] for r in rows(conn, "SELECT PredPlanId FROM TB_PRC_PlanDep WHERE PlanId=? ORDER BY PredPlanId", plan_id)]
    return plan_out(p, preds, blockers_by_plan(conn, plan_id=plan_id).get(plan_id, []))


def procs(conn) -> list[dict]:
    return rows(conn, "SELECT ProcCd proc_cd, ProcNm proc_nm, ProcGroup proc_group, StdDays std_days, Seq seq "
                      "FROM TB_PRC_Proc WHERE UseYN=1 ORDER BY Seq")


def plan_hulls(conn) -> list[dict]:
    return rows(conn, "SELECT h.HullNo hull_no, h.HullNm hull_nm, "
                      "(SELECT COUNT(*) FROM TB_PRC_Plan p WHERE p.HullNo=h.HullNo) plan_count "
                      "FROM TB_MST_Hull h WHERE h.UseYN=1 ORDER BY h.HullNo")


def gantt(conn, hull_no: str, block_id: int | None) -> dict:
    from .hulls import get_hull_row
    get_hull_row(conn, hull_no)
    all_plans = rows(conn, "SELECT ProgressRate, PlanStartDt, PlanEndDt FROM TB_PRC_Plan WHERE HullNo=?", hull_no)
    plans = hull_plans(conn, hull_no, block_id)
    ids = {p["plan_id"] for p in plans}
    deps = [{"plan_id": p["plan_id"], "pred_plan_id": x, "lag_days": 0}
            for p in plans for x in p["pred_plan_ids"] if x in ids]
    return {"hull_no": hull_no, "hull_progress": weighted_progress(all_plans), "today": config.TODAY,
            "plans": plans, "deps": deps}


# ---- 검증
def _validate_fields(conn, hull_no: str, d: dict) -> None:
    s, e = d.get("plan_start_dt"), d.get("plan_end_dt")
    if not is_date(s) or not is_date(e):
        raise bad("계획 시작/종료일을 입력하세요.", "plan_start_dt" if not is_date(s) else "plan_end_dt")
    if e < s:
        raise bad("계획 종료일이 시작일보다 빠릅니다.", "plan_end_dt")
    if d.get("block_id") is not None and not one(
            conn, "SELECT 1 x FROM TB_MST_Block WHERE BlockId=? AND HullNo=?", d["block_id"], hull_no):
        raise bad("해당 호선의 블록이 아닙니다.", "block_id")
    if not d.get("proc_cd") or not one(conn, "SELECT 1 x FROM TB_PRC_Proc WHERE ProcCd=? AND UseYN=1", d["proc_cd"]):
        raise bad("허용되지 않는 공정 코드입니다.", "proc_cd")
    check_approved(conn, d.get("manager_emp_no"), "manager_emp_no", "승인된 회원만 담당자로 지정할 수 있습니다.")


def _validate_preds(conn, plan_id: int | None, hull_no: str, start: str, pred_ids: list[int], confirm: bool) -> list[int]:
    """BR-04. 중복 제거한 선행 목록을 반환한다."""
    pred_ids = list(dict.fromkeys(int(x) for x in pred_ids))
    if plan_id is not None and plan_id in pred_ids:
        raise bad("자기 자신을 선행 공정으로 지정할 수 없습니다.", "pred_plan_ids", "PLAN_DEPENDENCY_SELF")
    preds = {r["PlanId"]: r for r in rows(
        conn, f"SELECT PlanId, HullNo, PlanEndDt FROM TB_PRC_Plan WHERE PlanId IN ({','.join('?' * len(pred_ids))})",
        *pred_ids)} if pred_ids else {}
    if any(x not in preds or preds[x]["HullNo"] != hull_no for x in pred_ids):
        raise bad("선행 공정은 같은 호선의 공정이어야 합니다.", "pred_plan_ids")
    if plan_id is not None and pred_ids:
        graph: dict[int, list[int]] = {}
        for r in rows(conn, "SELECT d.PlanId, d.PredPlanId FROM TB_PRC_PlanDep d JOIN TB_PRC_Plan p "
                            "ON p.PlanId=d.PlanId WHERE p.HullNo=? AND d.PlanId<>?", hull_no, plan_id):
            graph.setdefault(r["PlanId"], []).append(r["PredPlanId"])
        stack, seen = list(pred_ids), set()
        while stack:
            n = stack.pop()
            if n == plan_id:
                raise bad("선행 공정이 순환 구조를 만듭니다.", "pred_plan_ids", "PLAN_DEPENDENCY_CYCLE")
            if n not in seen:
                seen.add(n)
                stack.extend(graph.get(n, []))
    late = [x for x in pred_ids if preds[x]["PlanEndDt"] > start]
    if late and not confirm:
        raise ApiError(409, "PRED_LATE_CONFIRM_REQUIRED",
                       "선행 공정 종료일이 이 공정의 시작일보다 늦습니다. 그대로 저장할까요?",
                       {"late_pred_plan_ids": late})
    return pred_ids


def _write_preds(conn, plan_id: int, pred_ids: list[int]) -> None:
    conn.execute("DELETE FROM TB_PRC_PlanDep WHERE PlanId=?", (plan_id,))
    conn.executemany("INSERT INTO TB_PRC_PlanDep(PlanId, PredPlanId, LagDays) VALUES (?,?,0)",
                     [(plan_id, x) for x in pred_ids])


def _norm(body: dict) -> dict:
    return {k: clean(v) if isinstance(v, str) else v for k, v in body.items()}


def create_plan(conn, hull_no: str, body: dict, user: dict) -> dict:
    from .hulls import get_hull_row
    get_hull_row(conn, hull_no)
    d = _norm(body)
    _validate_fields(conn, hull_no, d)
    preds = _validate_preds(conn, None, hull_no, d["plan_start_dt"], d.get("pred_plan_ids") or [],
                            bool(d.get("confirm_late_preds")))
    with tx(conn):
        cur = conn.execute(
            "INSERT INTO TB_PRC_Plan(HullNo, BlockId, ProcCd, PlanStartDt, PlanEndDt, ProgressRate, PlanStatus, "
            "ManagerEmpNo, Remark, CreateUserId, CreateDt) VALUES (?,?,?,?,?,0,'PLAN',?,?,?,?)",
            (hull_no, d.get("block_id"), d["proc_cd"], d["plan_start_dt"], d["plan_end_dt"], d.get("manager_emp_no"),
             d.get("remark"), user["emp_no"], config.TODAY))
        _write_preds(conn, cur.lastrowid, preds)
        recalc_hull(conn, hull_no)
    return get_plan(conn, cur.lastrowid)


FIELD_COLS = {"block_id": "BlockId", "proc_cd": "ProcCd", "plan_start_dt": "PlanStartDt",
              "plan_end_dt": "PlanEndDt", "manager_emp_no": "ManagerEmpNo", "remark": "Remark"}


def update_plan(conn, plan_id: int, body: dict) -> dict:
    """진척·실제일은 보존한다."""
    p = get_plan_row(conn, plan_id)
    d = _norm(body)
    merged = {k: p[c] for k, c in FIELD_COLS.items()}
    changes = {k: d.get(k) for k in FIELD_COLS if k in body}
    merged.update(changes)
    _validate_fields(conn, p["HullNo"], merged)
    preds = None
    if "pred_plan_ids" in body and d.get("pred_plan_ids") is not None:
        preds = _validate_preds(conn, plan_id, p["HullNo"], merged["plan_start_dt"], d["pred_plan_ids"],
                                bool(d.get("confirm_late_preds")))
    elif "plan_start_dt" in changes and changes["plan_start_dt"] != p["PlanStartDt"]:
        cur = [r["PredPlanId"] for r in rows(conn, "SELECT PredPlanId FROM TB_PRC_PlanDep WHERE PlanId=?", plan_id)]
        _validate_preds(conn, plan_id, p["HullNo"], merged["plan_start_dt"], cur, bool(d.get("confirm_late_preds")))
    with tx(conn):
        if changes:
            conn.execute(f"UPDATE TB_PRC_Plan SET {','.join(FIELD_COLS[k] + '=?' for k in changes)} WHERE PlanId=?",
                         [*changes.values(), plan_id])
        if preds is not None:
            _write_preds(conn, plan_id, preds)
        recalc_hull(conn, p["HullNo"])
    return get_plan(conn, plan_id)


def set_predecessors(conn, plan_id: int, pred_ids: list[int], confirm: bool) -> dict:
    p = get_plan_row(conn, plan_id)
    preds = _validate_preds(conn, plan_id, p["HullNo"], p["PlanStartDt"], pred_ids, confirm)
    with tx(conn):
        _write_preds(conn, plan_id, preds)
        recalc_hull(conn, p["HullNo"])
    return get_plan(conn, plan_id)


def _shift(day: str, n: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def reschedule(conn, plan_id: int, start, end, confirm: bool) -> dict:
    """간트 드래그. 기간을 바꾸고, 선행 종료일이 후행 시작일에 닿거나 넘으면 후행을 종료+1일로 민다(기간 유지, 연쇄).
    명세 BR-04의 '자동 조정 없음'을 사용자 요청으로 바꾼 동작이다."""
    p = get_plan_row(conn, plan_id)
    if not is_date(start) or not is_date(end):
        raise bad("계획 시작/종료일을 입력하세요.", "plan_start_dt" if not is_date(start) else "plan_end_dt")
    if end < start:
        raise bad("계획 종료일이 시작일보다 빠릅니다.", "plan_end_dt")
    hull = p["HullNo"]
    sched = {r["PlanId"]: [r["PlanStartDt"], r["PlanEndDt"]]
             for r in rows(conn, "SELECT PlanId, PlanStartDt, PlanEndDt FROM TB_PRC_Plan WHERE HullNo=?", hull)}
    preds = _preds_map(conn, hull)
    if start != p["PlanStartDt"]:
        _validate_preds(conn, plan_id, hull, start, preds.get(plan_id, []), confirm)
    succs: dict[int, list[int]] = {}
    for sid, ps in preds.items():
        for x in ps:
            succs.setdefault(x, []).append(sid)
    sched[plan_id] = [start, end]
    changed, queue = {plan_id}, [plan_id]
    while queue:
        for sid in succs.get(queue.pop(0), []):
            need = _shift(max(sched[x][1] for x in preds[sid]), 1)
            s, e = sched[sid]
            if s < need:
                n = (date.fromisoformat(need) - date.fromisoformat(s)).days
                sched[sid] = [need, _shift(e, n)]
                changed.add(sid)
                queue.append(sid)
    with tx(conn):
        conn.executemany("UPDATE TB_PRC_Plan SET PlanStartDt=?, PlanEndDt=? WHERE PlanId=?",
                         [(*sched[i], i) for i in changed])
        recalc_hull(conn, hull)
    return {"plan": get_plan(conn, plan_id), "shifted_plan_ids": sorted(changed - {plan_id})}


def delete_plan(conn, plan_id: int) -> None:
    p = get_plan_row(conn, plan_id)
    with tx(conn):
        conn.execute("DELETE FROM TB_PRC_Plan WHERE PlanId=?", (plan_id,))
        recalc_hull(conn, p["HullNo"])


# ---- 도면 연계 (공정·도면 양쪽 API가 공유)
def get_drawing_row(conn, drawing_id: int) -> dict:
    d = one(conn, "SELECT * FROM TB_DWG_Drawing WHERE DrawingId=?", drawing_id)
    if not d:
        raise not_found("DRAWING_NOT_FOUND", "도면을 찾을 수 없습니다.")
    return d


def add_link(conn, drawing_id, plan_id, required: bool) -> None:
    if plan_id is None:
        raise bad("공정을 선택하세요.", "plan_id")
    if drawing_id is None:
        raise bad("도면을 선택하세요.", "drawing_id")
    p = get_plan_row(conn, plan_id)
    d = get_drawing_row(conn, drawing_id)
    if d["HullNo"] != p["HullNo"]:
        raise bad("같은 호선의 도면만 연계할 수 있습니다.", "drawing_id")
    if one(conn, "SELECT 1 x FROM TB_DWG_PlanLink WHERE DrawingId=? AND PlanId=?", drawing_id, plan_id):
        raise duplicate("이미 연계된 도면입니다.", "drawing_id")
    with tx(conn):
        conn.execute("INSERT INTO TB_DWG_PlanLink(DrawingId, PlanId, RequiredYN, NeedDt) VALUES (?,?,?,?)",
                     (drawing_id, plan_id, int(bool(required)), p["PlanStartDt"]))
        recalc_hull(conn, p["HullNo"])


def remove_link(conn, drawing_id: int, plan_id: int) -> None:
    p = get_plan_row(conn, plan_id)
    get_drawing_row(conn, drawing_id)
    if not one(conn, "SELECT 1 x FROM TB_DWG_PlanLink WHERE DrawingId=? AND PlanId=?", drawing_id, plan_id):
        raise not_found("LINK_NOT_FOUND", "연계 정보를 찾을 수 없습니다.")
    with tx(conn):
        conn.execute("DELETE FROM TB_DWG_PlanLink WHERE DrawingId=? AND PlanId=?", (drawing_id, plan_id))
        recalc_hull(conn, p["HullNo"])


def plan_drawings(conn, plan_id: int) -> dict:
    p = get_plan_row(conn, plan_id)
    links = rows(conn, """
        SELECT d.DrawingId drawing_id, d.DrawingNo drawing_no, d.DrawingNm drawing_nm, d.DwgStatus dwg_status,
               EXISTS(SELECT 1 FROM TB_DWG_Revision r WHERE r.DrawingId=d.DrawingId AND r.RevStatus='ISSUED') has_issued,
               l.RequiredYN required, l.NeedDt need_dt
        FROM TB_DWG_PlanLink l JOIN TB_DWG_Drawing d ON d.DrawingId=l.DrawingId
        WHERE l.PlanId=? ORDER BY d.DrawingNo""", plan_id)
    for x in links:
        x["has_issued"], x["required"] = bool(x["has_issued"]), bool(x["required"])
    available = rows(conn, "SELECT DrawingId drawing_id, DrawingNo drawing_no, DrawingNm drawing_nm, DwgStatus dwg_status "
                           "FROM TB_DWG_Drawing d WHERE HullNo=? AND NOT EXISTS (SELECT 1 FROM TB_DWG_PlanLink l "
                           "WHERE l.DrawingId=d.DrawingId AND l.PlanId=?) ORDER BY DrawingNo", p["HullNo"], plan_id)
    return {"plan_id": plan_id, "blockers": blockers_by_plan(conn, plan_id=plan_id).get(plan_id, []),
            "links": links, "available": available}


def default_new_plan() -> dict:
    t = config.today()
    return {"proc_cd": "CUT", "plan_start_dt": t.isoformat(), "plan_end_dt": (t + timedelta(days=13)).isoformat()}

