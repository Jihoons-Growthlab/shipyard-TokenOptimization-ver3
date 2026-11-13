"""개발·시연용 예시 사용 로그·건의 글(명세 외 요청 기능). 예시 로그는 DemoYN=1로 표시해 실제 기록과 구분한다."""
import random
from datetime import datetime, timedelta, timezone

from .db import rows, scalar, tx

# 회원별 주 사용 기능: (경로 템플릿, 메서드, 가중치)
PROFILE = {
    "park.pm": [("/api/hulls/{hull_no}/plans", "GET", 30), ("/api/plans/{plan_id}", "PATCH", 8), ("/api/plans/{plan_id}/schedule", "PATCH", 6),
                ("/api/dashboard/summary", "GET", 8), ("/api/hulls", "GET", 6), ("/api/plans/{plan_id}/drawings", "GET", 6)],
    "han.wk": [("/api/progress", "GET", 20), ("/api/plans/{plan_id}/progress/{work_dt}", "PUT", 14), ("/api/hulls/{hull_no}/plans", "GET", 8),
               ("/api/dashboard/summary", "GET", 4)],
    "lee.dwg": [("/api/drawings", "GET", 22), ("/api/drawings/{drawing_id}", "GET", 14), ("/api/drawings/{drawing_id}/revisions/{rev_no}/pdf", "GET", 10),
                ("/api/approvals", "GET", 8), ("/api/drawings/{drawing_id}/revisions", "POST", 3)],
    "choi.qa": [("/api/dashboard/summary", "GET", 10), ("/api/hulls", "GET", 8), ("/api/hulls/{hull_no}/summary", "GET", 6),
                ("/api/drawings", "GET", 5)],
    "admin": [("/api/users", "GET", 10), ("/api/users/{emp_no}", "PATCH", 3), ("/api/dashboard/summary", "GET", 6),
              ("/api/inquiries", "GET", 4)],
}
DAILY = {"park.pm": 60, "han.wk": 45, "lee.dwg": 50, "choi.qa": 18, "admin": 14}
COMMON = [("/api/auth/login", "POST"), ("/api/me/menu", "GET"), ("/api/codes", "GET"), ("/api/weather", "GET")]

INQUIRIES = [
    ("park.pm", "FEATURE", "공정 계획 엑셀 내보내기 요청", "간트 화면의 공정 목록을 엑셀로 내려받을 수 있으면 주간 회의 자료 만들기가 편할 것 같습니다.",
     "IN_PROGRESS", "검토 중입니다. 다음 배포에 포함할 예정입니다."),
    ("lee.dwg", "BUG", "도면 PDF 업로드 시 파일명이 깨집니다", "한글 파일명으로 업로드하면 목록에서 파일명이 ??? 로 보입니다.", "OPEN", None),
    ("han.wk", "QUESTION", "실적 입력 마감 시간이 있나요?", "전날 실적을 다음날 오전에 입력해도 되는지 궁금합니다.", "DONE",
     "마감 시간은 없습니다. 다만 주간 보고 전(금 17시)까지 입력해 주세요."),
    ("choi.qa", "ETC", "대시보드 글자 크기 조정", "회의실 화면에서 대시보드 숫자가 작게 보입니다.", "REJECTED",
     "브라우저 확대(Ctrl +)로 조정해 주세요. 별도 설정은 제공하지 않습니다."),
]


def attach_demo_usage(conn, days: int = 30, seed: int = 7) -> dict:
    """예시 로그가 이미 있으면 다시 만들지 않는다."""
    out = {"logs": 0, "inquiries": 0}
    users = {r["emp_no"] for r in rows(conn, "SELECT emp_no FROM users")}
    rnd = random.Random(seed)
    if not scalar(conn, "SELECT COUNT(*) FROM TB_SYS_LogApi WHERE DemoYN=1"):
        now = datetime.now(timezone.utc)
        batch = []
        for d in range(days, 0, -1):
            day = (now - timedelta(days=d)).replace(hour=0, minute=0, second=0, microsecond=0)
            weekend = (day + timedelta(hours=9)).weekday() >= 5
            for emp, n in DAILY.items():
                if emp not in users or (weekend and rnd.random() < .85):
                    continue
                count = max(0, int(rnd.gauss(n * (1.1 if d < 8 else 1), n * .25)))
                paths = PROFILE[emp] + [(p, m, 3) for p, m in COMMON]
                weights = [w for _, _, w in paths]
                for _ in range(count):
                    path, method, _w = rnd.choices(paths, weights)[0]
                    hour_kst = min(19, max(7, int(rnd.gauss(13, 3))))
                    ts = day + timedelta(hours=hour_kst - 9, minutes=rnd.randrange(60), seconds=rnd.randrange(60))
                    status = 200 if rnd.random() > .03 else rnd.choice([400, 403, 404, 409, 500])
                    ms = max(2, int(rnd.lognormvariate(3.2 if method == "GET" else 3.7, .5)))
                    batch.append((emp, method, path, status, ms, ts.strftime("%Y-%m-%d %H:%M:%S")))
        with tx(conn):
            conn.executemany("INSERT INTO TB_SYS_LogApi(EmpNo, Method, Path, Status, DurationMs, CallDt, DemoYN) "
                             "VALUES (?,?,?,?,?,?,1)", batch)
        out["logs"] = len(batch)
    titles = {r["Title"] for r in rows(conn, "SELECT Title FROM TB_SYS_Inquiry")}
    base = datetime.now(timezone.utc) - timedelta(days=6)
    new = [(cat, title, body, st, emp, (base + timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S"), ans,
            "admin" if ans else None, (base + timedelta(days=i, hours=5)).strftime("%Y-%m-%d %H:%M:%S") if ans else None)
           for i, (emp, cat, title, body, st, ans) in enumerate(INQUIRIES) if title not in titles and emp in users]
    if new:
        with tx(conn):
            conn.executemany("INSERT INTO TB_SYS_Inquiry(Category, Title, Content, Status, CreateUserId, CreateDt, Answer, "
                             "AnswerUserId, AnswerDt) VALUES (?,?,?,?,?,?,?,?,?)", new)
    out["inquiries"] = len(new)
    return out
