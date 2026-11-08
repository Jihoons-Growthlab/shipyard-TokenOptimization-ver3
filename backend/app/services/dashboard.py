"""F03 대시보드 집계 (UseYN=1 호선 대상)."""
from .. import config
from ..db import rows
from .common import code_map
from .plans import PLAN_SELECT
from .rules import PLAN_STATUSES, blockers_by_plan, impacts, plan_label, weighted_progress

ACTIVE_HULL = ("DESIGN", "BUILD", "LAUNCH", "TRIAL")
DWG_STATUSES = ("ISSUED", "APPROVED", "REVIEW", "DRAFT")
LIST_MAX = 6


def _lst(items: list) -> dict:
    return {"count": len(items), "items": items[:LIST_MAX]}


def summary(conn) -> dict:
    hulls = rows(conn, "SELECT HullNo, HullNm, HullStatus, DeliveryDt FROM TB_MST_Hull WHERE UseYN=1 ORDER BY HullNo")
    plans = rows(conn, PLAN_SELECT + " JOIN TB_MST_Hull h ON h.HullNo=p.HullNo WHERE h.UseYN=1")
    blockers = blockers_by_plan(conn)

    def item(p):
        return {"plan_id": p["PlanId"], "hull_no": p["HullNo"], "label": plan_label(p["BlockCd"], p["ProcNm"]),
                "plan_status": p["PlanStatus"], "progress_rate": p["ProgressRate"], "plan_start_dt": p["PlanStartDt"],
                "plan_end_dt": p["PlanEndDt"], "blockers": [b["drawing_no"] for b in blockers.get(p["PlanId"], [])],
                "link": {"screen": "plan-gantt", "param": p["HullNo"]}}

    delay = [item(p) for p in sorted((p for p in plans if p["PlanStatus"] == "DELAY"),
                                     key=lambda p: (p["PlanEndDt"], p["PlanId"]))]
    waiting = [item(p) for p in sorted((p for p in plans if p["PlanStatus"] == "PLAN" and blockers.get(p["PlanId"])),
                                       key=lambda p: (p["PlanStartDt"], p["PlanId"]))]
    drawings = rows(conn, "SELECT d.Discipline, d.DwgStatus FROM TB_DWG_Drawing d JOIN TB_MST_Hull h "
                          "ON h.HullNo=d.HullNo WHERE h.UseYN=1")
    by_hull: dict[str, list] = {}
    for p in plans:
        by_hull.setdefault(p["HullNo"], []).append(p)

    disciplines = []
    for code, name in code_map(conn, "DWGDISC").items():
        mine = [d for d in drawings if d["Discipline"] == code]
        if mine:
            disciplines.append({"discipline": code, "name": name, "total": len(mine),
                                "counts": {s: sum(1 for d in mine if d["DwgStatus"] == s) for s in DWG_STATUSES}})

    months: dict[str, list[str]] = {}
    for h in hulls:
        if h["DeliveryDt"]:
            months.setdefault(h["DeliveryDt"][:7], []).append(h["HullNo"])

    return {
        "today": config.TODAY,
        "kpi": {
            "active_hulls": {"value": sum(1 for h in hulls if h["HullStatus"] in ACTIVE_HULL), "link": {"screen": "hull-list"}},
            "delay_plans": {"value": len(delay), "link": {"screen": "plan-gantt"}},
            "waiting_plans": {"value": len(waiting), "link": {"screen": "plan-gantt"}},
            "pending_drawings": {"value": sum(1 for d in drawings if d["DwgStatus"] in ("REVIEW", "APPROVED")),
                                 "link": {"screen": "dwg-approval"}},
        },
        "hull_progress": [{"hull_no": h["HullNo"], "hull_nm": h["HullNm"],
                           "progress": weighted_progress(by_hull.get(h["HullNo"], []), empty=0),
                           "link": {"screen": "plan-gantt", "param": h["HullNo"]}} for h in hulls],
        "plan_status": [{"status": s, "count": sum(1 for p in plans if p["PlanStatus"] == s)} for s in PLAN_STATUSES],
        "drawing_disciplines": disciplines,
        "deliveries": [{"month": m, "count": len(v), "hull_nos": v} for m, v in sorted(months.items())],
        "delay_list": _lst(delay),
        "waiting_list": _lst(waiting),
        "impact_list": _lst(impacts(conn, active_hulls_only=True)),
    }
