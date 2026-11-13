"""사용 로그(명세 외 요청 기능): API 호출 기록과 관리자용 통계."""
from datetime import datetime, timedelta, timezone

from ..db import connect, rows, scalar, tx
from ..errors import bad
from .common import now_utc

SKIP = ("/api/health", "/api/usage")  # 상태 확인·로그 화면 자체는 기록하지 않는다.
KST = "+9 hours"

# API 경로 → 기능 이름. 앞에서부터 처음 맞는 규칙을 쓴다.
FEATURES = [
    ("/api/hulls/{hull_no}/plans", "공정 계획"), ("/api/plans", "공정 계획"), ("/api/plan-hulls", "공정 계획"),
    ("/api/procs", "공정 계획"), ("/api/progress", "공정 실적"), ("/api/hulls", "호선 관리"), ("/api/blocks", "호선 관리"),
    ("/api/drawings", "도면 관리"), ("/api/approvals", "결재"), ("/api/dashboard", "대시보드"), ("/api/users", "회원관리"),
    ("/api/auth-groups", "회원관리"), ("/api/auth", "로그인·인증"), ("/api/inquiries", "건의·문의"), ("/api/chat", "챗봇"),
    ("/api/me", "공통(메뉴·세션)"), ("/api/codes", "공통(메뉴·세션)"), ("/api/weather", "날씨"),
]


def feature_of(path: str) -> str:
    return next((name for prefix, name in FEATURES if path.startswith(prefix)), "기타")


def record(emp_no, method: str, path: str, status: int, ms: int) -> None:
    """미들웨어에서 호출한다. 기록 실패가 요청을 깨뜨리지 않게 예외를 삼킨다."""
    if not path.startswith("/api") or path.startswith(SKIP):
        return
    try:
        conn = connect()
        try:
            conn.execute("INSERT INTO TB_SYS_LogApi(EmpNo, Method, Path, Status, DurationMs, CallDt) VALUES (?,?,?,?,?,?)",
                         (emp_no, method, path, status, ms, now_utc()))
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        pass


def summary(conn, days: int, emp_no: str | None) -> dict:
    if days not in (7, 30, 90):
        raise bad("조회 기간은 7, 30, 90일 중 하나입니다.", "days")
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    where, args = "CallDt>=?", [since]
    if emp_no:
        where += " AND EmpNo=?"
        args.append(emp_no)
    w = f"FROM TB_SYS_LogApi WHERE {where}"
    total = scalar(conn, f"SELECT COUNT(*) {w}", *args)
    errors = scalar(conn, f"SELECT COUNT(*) {w} AND Status>=400", *args)
    users = scalar(conn, f"SELECT COUNT(DISTINCT EmpNo) {w} AND EmpNo IS NOT NULL", *args)
    avg_ms = scalar(conn, f"SELECT AVG(DurationMs) {w}", *args)
    lw, largs = "datetime(LoginDt)>=?", [since]
    if emp_no:
        lw += " AND UserId=?"
        largs.append(emp_no)
    logins = scalar(conn, f"SELECT COUNT(*) FROM TB_SYS_LogAccess WHERE {lw}", *largs)

    by_day = {r["d"]: r for r in rows(conn, f"SELECT date(CallDt,'{KST}') d, COUNT(*) calls, SUM(Status>=400) errors, "
                                            f"COUNT(DISTINCT EmpNo) users {w} GROUP BY d", *args)}
    today = (now + timedelta(hours=9)).date()
    daily = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        r = by_day.get(d)
        daily.append({"date": d, "calls": r["calls"] if r else 0, "errors": r["errors"] if r else 0,
                      "users": r["users"] if r else 0})
    hours = {r["h"]: r["n"] for r in rows(conn, f"SELECT CAST(strftime('%H', CallDt, '{KST}') AS INT) h, COUNT(*) n {w} GROUP BY h", *args)}

    feats: dict[str, dict] = {}
    for r in rows(conn, f"SELECT Path, COUNT(*) n, COUNT(DISTINCT EmpNo) u {w} GROUP BY Path", *args):
        f = feats.setdefault(feature_of(r["Path"]), {"calls": 0, "paths": 0})
        f["calls"] += r["n"]
        f["paths"] += 1
    features = sorted(({"feature": k, **v} for k, v in feats.items()), key=lambda x: -x["calls"])

    top_users = rows(conn, f"""SELECT l.EmpNo emp_no, u.display_name, COUNT(*) calls, MAX(l.CallDt) last_dt
        FROM TB_SYS_LogApi l LEFT JOIN users u ON u.emp_no=l.EmpNo WHERE {where.replace('CallDt', 'l.CallDt').replace('EmpNo', 'l.EmpNo')}
        AND l.EmpNo IS NOT NULL GROUP BY l.EmpNo ORDER BY calls DESC LIMIT 10""", *args)
    for u in top_users:
        paths = rows(conn, f"SELECT Path, COUNT(*) n {w} AND EmpNo=? GROUP BY Path", *args, u["emp_no"])
        agg: dict[str, int] = {}
        for p in paths:
            agg[feature_of(p["Path"])] = agg.get(feature_of(p["Path"]), 0) + p["n"]
        u["top_feature"] = max(agg, key=agg.get) if agg else None

    endpoints = rows(conn, f"""SELECT Method method, Path path, COUNT(*) calls, SUM(Status>=400) errors,
        CAST(ROUND(AVG(DurationMs)) AS INT) avg_ms, MAX(DurationMs) max_ms {w} GROUP BY Method, Path ORDER BY calls DESC LIMIT 15""", *args)
    for e in endpoints:
        e["feature"] = feature_of(e["path"])

    mw, margs = "datetime(m.InDt)>=?", [since]
    if emp_no:
        mw += " AND a.UserId=?"
        margs.append(emp_no)
    menus = rows(conn, f"""SELECT m.MenuId menu_id, i.Title title, COUNT(*) opens, COUNT(DISTINCT a.UserId) users
        FROM TB_SYS_LogMenuAccess m JOIN TB_SYS_LogAccess a ON a.LogId=m.LogId JOIN TB_SYS_MenuInfo i ON i.MenuId=m.MenuId
        WHERE {mw} GROUP BY m.MenuId ORDER BY opens DESC""", *margs)

    recent_errors = rows(conn, f"""SELECT l.CallDt call_dt, l.Method method, l.Path path, l.Status status, l.EmpNo emp_no,
        u.display_name FROM TB_SYS_LogApi l LEFT JOIN users u ON u.emp_no=l.EmpNo
        WHERE {where.replace('CallDt', 'l.CallDt').replace('EmpNo', 'l.EmpNo')} AND l.Status>=400 ORDER BY l.CallDt DESC LIMIT 10""", *args)
    demo = scalar(conn, f"SELECT COUNT(*) {w} AND DemoYN=1", *args)
    return {"days": days, "emp_no": emp_no, "since": since,
            "kpi": {"calls": total, "users": users, "logins": logins, "errors": errors,
                    "error_rate": round(errors * 100 / total, 1) if total else 0, "avg_ms": round(avg_ms or 0)},
            "daily": daily, "hours": [hours.get(h, 0) for h in range(24)], "features": features, "top_users": top_users,
            "endpoints": endpoints, "menus": menus, "recent_errors": recent_errors, "demo_calls": demo,
            "user_options": rows(conn, "SELECT emp_no, display_name FROM users ORDER BY display_name, emp_no")}


def clear_demo(conn) -> int:
    with tx(conn):
        return conn.execute("DELETE FROM TB_SYS_LogApi WHERE DemoYN=1").rowcount
