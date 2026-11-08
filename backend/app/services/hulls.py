"""F04 호선·일정·블록."""
import re
from datetime import date

from .. import config
from ..db import one, rows, tx
from ..errors import bad, duplicate, not_found
from .common import blank, check_code, clean, code_map, is_date
from .rules import PLAN_STATUSES, recalc_hull, remove_files, weighted_progress

HULL_NO_RE = re.compile(r"^[A-Za-z0-9._-]{1,20}$")
MILESTONES = ("CUT", "KEEL", "LAUNCH", "TRIAL", "DELIVER")
DWG_COUNT_STATUSES = ("ISSUED", "APPROVED", "REVIEW", "DRAFT")

# API ↔ DB 매핑
HULL_FIELDS = {"hull_no": "HullNo", "hull_nm": "HullNm", "ship_type": "ShipType", "hull_status": "HullStatus",
               "owner_nm": "OwnerNm", "class_society": "ClassSociety", "length_m": "LengthM",
               "breadth_m": "BreadthM", "depth_m": "DepthM", "dead_weight": "DeadWeight", "dock_no": "DockNo",
               "contract_dt": "ContractDt", "delivery_dt": "DeliveryDt", "remark": "Remark", "use_yn": "UseYN",
               "create_user_id": "CreateUserId", "create_dt": "CreateDt", "modify_user_id": "ModifyUserId",
               "modify_dt": "ModifyDt"}
EDITABLE = [k for k in HULL_FIELDS if k not in ("hull_no", "create_user_id", "create_dt", "modify_user_id", "modify_dt")]
NUMERIC = ("length_m", "breadth_m", "depth_m", "dead_weight")


def get_hull_row(conn, hull_no: str) -> dict:
    h = one(conn, "SELECT * FROM TB_MST_Hull WHERE HullNo=?", hull_no)
    if not h:
        raise not_found("HULL_NOT_FOUND", "호선을 찾을 수 없습니다.")
    return h


def _plans_by_hull(conn, where="", *args) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for p in rows(conn, f"SELECT HullNo, BlockId, ProgressRate, PlanStartDt, PlanEndDt, PlanStatus FROM TB_PRC_Plan {where}", *args):
        out.setdefault(p["HullNo"], []).append(p)
    return out


def hull_out(h: dict, plans: list[dict]) -> dict:
    d = {k: h[c] for k, c in HULL_FIELDS.items()}
    d["use_yn"] = bool(d["use_yn"])
    d["plan_count"] = len(plans)
    d["progress"] = weighted_progress(plans)
    d["delay_count"] = sum(1 for p in plans if p["PlanStatus"] == "DELAY")
    return d


def list_hulls(conn, status=None, ship_type=None, q=None) -> list[dict]:
    sql, args = "SELECT * FROM TB_MST_Hull WHERE 1=1", []
    if status:
        sql += " AND HullStatus=?"
        args.append(status)
    if ship_type:
        sql += " AND ShipType=?"
        args.append(ship_type)
    if q and q.strip():
        sql += " AND (lower(HullNo) LIKE ? OR lower(HullNm) LIKE ? OR lower(IFNULL(OwnerNm,'')) LIKE ?)"
        args += [f"%{q.strip().lower()}%"] * 3
    plans = _plans_by_hull(conn)
    return [hull_out(h, plans.get(h["HullNo"], [])) for h in rows(conn, sql + " ORDER BY HullNo", *args)]


def get_hull(conn, hull_no: str) -> dict:
    h = get_hull_row(conn, hull_no)
    return hull_out(h, _plans_by_hull(conn, "WHERE HullNo=?", hull_no).get(hull_no, []))


def _validate(conn, d: dict, given: set) -> None:
    if "hull_status" in given and blank(d.get("hull_status")):
        raise bad("상태를 선택하세요.", "hull_status")
    check_code(conn, "SHIPTYPE", d.get("ship_type"), "ship_type")
    check_code(conn, "HULLSTAT", d.get("hull_status"), "hull_status")
    for f in ("contract_dt", "delivery_dt"):
        if d.get(f) is not None and not is_date(d[f]):
            raise bad("날짜 형식(YYYY-MM-DD)이 올바르지 않습니다.", f)
    if d.get("contract_dt") and d.get("delivery_dt") and d["delivery_dt"] < d["contract_dt"]:
        raise bad("인도 예정일이 계약일보다 빠릅니다.", "delivery_dt")
    for f in NUMERIC:
        if d.get(f) is not None and d[f] < 0:
            raise bad("0 이상의 값을 입력하세요.", f)


def _normalize(body: dict) -> dict:
    return {k: (clean(v) if isinstance(v, str) else v) for k, v in body.items()}


def create_hull(conn, body: dict, user: dict) -> dict:
    d = _normalize(body)
    hull_no = d.get("hull_no")
    if not hull_no:
        raise bad("호선번호를 입력하세요.", "hull_no")
    if not HULL_NO_RE.match(hull_no):
        raise bad("호선번호는 영문/숫자/._- 1~20자입니다.", "hull_no")
    if one(conn, "SELECT 1 x FROM TB_MST_Hull WHERE HullNo=?", hull_no):
        raise duplicate("이미 존재하는 호선번호입니다.", "hull_no")
    given = set(body)
    if "hull_status" not in given:
        d["hull_status"] = "PLAN"
    _validate(conn, d, given)
    vals = {k: d.get(k) for k in EDITABLE}
    vals["hull_nm"] = vals["hull_nm"] or ""
    vals["use_yn"] = 1 if vals["use_yn"] is None else int(bool(vals["use_yn"]))
    vals.update(hull_no=hull_no, create_user_id=user["emp_no"], create_dt=config.TODAY)
    cols = list(vals)
    with tx(conn):
        conn.execute(f"INSERT INTO TB_MST_Hull ({','.join(HULL_FIELDS[c] for c in cols)}) "
                     f"VALUES ({','.join('?' * len(cols))})", [vals[c] for c in cols])
        conn.executemany("INSERT INTO TB_MST_HullMilestone(HullNo, MilestoneCd, PlanDt) VALUES (?,?,?)",
                         [(hull_no, m, vals["delivery_dt"] if m == "DELIVER" else None) for m in MILESTONES])
    return get_hull(conn, hull_no)


def update_hull(conn, hull_no: str, body: dict, user: dict) -> dict:
    h = get_hull_row(conn, hull_no)
    d = _normalize(body)
    if "hull_no" in body and d.get("hull_no") != hull_no:
        raise bad("호선번호는 수정할 수 없습니다.", "hull_no")
    changes = {k: d[k] for k in EDITABLE if k in body}
    merged = {k: h[c] for k, c in HULL_FIELDS.items()}
    merged.update(changes)
    _validate(conn, merged, set(changes))
    if "hull_nm" in changes:
        changes["hull_nm"] = changes["hull_nm"] or ""
    if "use_yn" in changes:
        changes["use_yn"] = 1 if changes["use_yn"] is None else int(bool(changes["use_yn"]))
    changes.update(modify_user_id=user["emp_no"], modify_dt=config.TODAY)
    with tx(conn):
        conn.execute(f"UPDATE TB_MST_Hull SET {','.join(HULL_FIELDS[k] + '=?' for k in changes)} WHERE HullNo=?",
                     [*changes.values(), hull_no])
    return get_hull(conn, hull_no)


def delete_hull(conn, hull_no: str) -> None:
    get_hull_row(conn, hull_no)
    files = [r["FileId"] for r in rows(conn, "SELECT r.FileId FROM TB_DWG_Revision r JOIN TB_DWG_Drawing d "
                                             "ON d.DrawingId=r.DrawingId WHERE d.HullNo=? AND r.FileId IS NOT NULL", hull_no)]
    with tx(conn):
        conn.execute("DELETE FROM TB_MST_Hull WHERE HullNo=?", (hull_no,))
    remove_files(files)


# ---- 일정
def milestones(conn, hull_no: str) -> list[dict]:
    get_hull_row(conn, hull_no)
    names = code_map(conn, "MILESTONE")
    order = {c: i for i, c in enumerate(names)}
    out = []
    for r in rows(conn, "SELECT * FROM TB_MST_HullMilestone WHERE HullNo=?", hull_no):
        diff = None
        if r["PlanDt"] and r["ActualDt"] and is_date(r["PlanDt"]) and is_date(r["ActualDt"]):
            diff = (date.fromisoformat(r["ActualDt"]) - date.fromisoformat(r["PlanDt"])).days
        out.append({"milestone_cd": r["MilestoneCd"], "name": names.get(r["MilestoneCd"], r["MilestoneCd"]),
                    "plan_dt": r["PlanDt"], "actual_dt": r["ActualDt"], "diff_days": diff})
    return sorted(out, key=lambda x: order.get(x["milestone_cd"], 99))


def save_milestones(conn, hull_no: str, items: list[dict]) -> list[dict]:
    get_hull_row(conn, hull_no)
    allowed = code_map(conn, "MILESTONE")
    cds = [i.get("milestone_cd") for i in items]
    if any(c not in allowed for c in cds) or len(set(cds)) != len(cds):
        raise bad("허용되지 않거나 중복된 일정 코드입니다.", "items")
    for i in items:
        for f in ("plan_dt", "actual_dt"):
            v = clean(i.get(f))
            if v is not None and not is_date(v):
                raise bad("날짜 형식(YYYY-MM-DD)이 올바르지 않습니다.", f)
    with tx(conn):
        for i in items:
            conn.execute("INSERT INTO TB_MST_HullMilestone(HullNo, MilestoneCd, PlanDt, ActualDt) VALUES (?,?,?,?) "
                         "ON CONFLICT(HullNo, MilestoneCd) DO UPDATE SET PlanDt=excluded.PlanDt, ActualDt=excluded.ActualDt",
                         (hull_no, i["milestone_cd"], clean(i.get("plan_dt")), clean(i.get("actual_dt"))))
    return milestones(conn, hull_no)


# ---- 블록
def _block_out(b: dict, plans: list[dict], drawing_count: int) -> dict:
    return {"block_id": b["BlockId"], "hull_no": b["HullNo"], "block_cd": b["BlockCd"], "block_nm": b["BlockNm"],
            "block_type": b["BlockType"], "parent_block_id": b["ParentBlockId"], "weight_ton": b["WeightTon"],
            "use_yn": bool(b["UseYN"]), "plan_count": len(plans), "progress": weighted_progress(plans),
            "drawing_count": drawing_count}


def blocks(conn, hull_no: str) -> list[dict]:
    get_hull_row(conn, hull_no)
    plans: dict[int, list] = {}
    for p in _plans_by_hull(conn, "WHERE HullNo=?", hull_no).get(hull_no, []):
        plans.setdefault(p["BlockId"], []).append(p)
    dwg = {r["BlockId"]: r["n"] for r in rows(conn, "SELECT BlockId, COUNT(*) n FROM TB_DWG_Drawing WHERE HullNo=? "
                                                    "AND BlockId IS NOT NULL GROUP BY BlockId", hull_no)}
    return [_block_out(b, plans.get(b["BlockId"], []), dwg.get(b["BlockId"], 0))
            for b in rows(conn, "SELECT * FROM TB_MST_Block WHERE HullNo=? ORDER BY BlockCd, BlockId", hull_no)]


def create_block(conn, hull_no: str, body: dict) -> dict:
    get_hull_row(conn, hull_no)
    d = _normalize(body)
    cd = d.get("block_cd")
    if not cd:
        raise bad("블록코드를 입력하세요.", "block_cd")
    check_code(conn, "BLOCKTYPE", d.get("block_type"), "block_type")
    if d.get("weight_ton") is not None and d["weight_ton"] < 0:
        raise bad("0 이상의 값을 입력하세요.", "weight_ton")
    if d.get("parent_block_id") is not None and not one(
            conn, "SELECT 1 x FROM TB_MST_Block WHERE BlockId=? AND HullNo=?", d["parent_block_id"], hull_no):
        raise bad("해당 호선의 블록이 아닙니다.", "parent_block_id")
    if one(conn, "SELECT 1 x FROM TB_MST_Block WHERE HullNo=? AND BlockCd=?", hull_no, cd):
        raise duplicate("이미 존재하는 블록코드입니다.", "block_cd")
    with tx(conn):
        cur = conn.execute("INSERT INTO TB_MST_Block(HullNo, BlockCd, BlockNm, BlockType, ParentBlockId, WeightTon, UseYN) "
                           "VALUES (?,?,?,?,?,?,?)", (hull_no, cd, d.get("block_nm"), d.get("block_type"),
                                                      d.get("parent_block_id"), d.get("weight_ton"),
                                                      0 if d.get("use_yn") is False else 1))
    return next(b for b in blocks(conn, hull_no) if b["block_id"] == cur.lastrowid)


def delete_block(conn, block_id: int) -> None:
    b = one(conn, "SELECT HullNo FROM TB_MST_Block WHERE BlockId=?", block_id)
    if not b:
        raise not_found("BLOCK_NOT_FOUND", "블록을 찾을 수 없습니다.")
    with tx(conn):
        conn.execute("DELETE FROM TB_MST_Block WHERE BlockId=?", (block_id,))
        recalc_hull(conn, b["HullNo"])


def summary(conn, hull_no: str) -> dict:
    get_hull_row(conn, hull_no)
    plans = _plans_by_hull(conn, "WHERE HullNo=?", hull_no).get(hull_no, [])
    dwg = dict(conn.execute("SELECT DwgStatus, COUNT(*) FROM TB_DWG_Drawing WHERE HullNo=? GROUP BY DwgStatus",
                            (hull_no,)).fetchall())
    return {"hull_no": hull_no, "plan_count": len(plans), "progress": weighted_progress(plans),
            "plan_status": {s: sum(1 for p in plans if p["PlanStatus"] == s) for s in PLAN_STATUSES},
            "drawing_count": sum(dwg.values()),
            "drawing_status": {s: dwg.get(s, 0) for s in DWG_COUNT_STATUSES}}
