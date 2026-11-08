"""F02 메뉴·메뉴 접근 로그·날씨."""
from typing import Callable

from .. import config
from ..db import rows, tx
from ..errors import bad, forbidden
from .common import LEVEL_NAMES, VIEW, WRITE, menu_level, now_utc


def my_menu(conn, emp_no: str) -> list[dict]:
    items = rows(conn, """
        SELECT m.MenuId, m.ParentId, m.Title, m.TokenUrl, m.Seq,
               MAX(CASE a.AuthGbn WHEN 'Admin' THEN 3 WHEN 'Write' THEN 2 WHEN 'View' THEN 1 ELSE 0 END) lvl
        FROM TB_SYS_MenuInfo m
        JOIN TB_SYS_AuthMenu a ON a.MenuId=m.MenuId
        JOIN TB_SYS_AuthUser u ON u.AuthCd=a.AuthCd AND u.EmpNo=?
        WHERE m.UseYN=1 GROUP BY m.MenuId ORDER BY m.Seq, m.MenuId""", emp_no)
    by_id = {r["MenuId"]: r for r in items}

    def visible(r, seen=()):
        if r["lvl"] < VIEW:
            return False
        p = r["ParentId"]
        return p is None or (p in by_id and p not in seen and visible(by_id[p], seen + (r["MenuId"],)))

    return [{"menu_id": r["MenuId"], "parent_id": r["ParentId"], "title": r["Title"], "token": r["TokenUrl"],
             "seq": r["Seq"], "level": r["lvl"], "auth_gbn": LEVEL_NAMES[r["lvl"]], "can_write": r["lvl"] >= WRITE}
            for r in items if visible(r)]


def log_menu_access(conn, user: dict, menu_id: str) -> None:
    if menu_level(conn, user["emp_no"], menu_id) < VIEW:
        raise forbidden(menu_id)
    with tx(conn):
        conn.execute("INSERT INTO TB_SYS_LogMenuAccess(MenuId, LogId, InDt) VALUES (?,?,?)",
                     (menu_id, user["lid"], now_utc()))


# ---- 날씨: 실제 공급자가 없어 기본은 항상 샘플이다.
SAMPLES = {
    "울산": {"tempC": 17.6, "condition": "맑음", "humidity": 52, "windMs": 3.2},
    "거제": {"tempC": 18.9, "condition": "구름조금", "humidity": 61, "windMs": 4.1},
    "목포": {"tempC": 16.2, "condition": "흐림", "humidity": 70, "windMs": 5.0},
}
DEFAULT_REGION = "울산"
# 이름 → (region) -> {obsDt,tempC,condition,humidity,windMs}. 기본 레지스트리는 비어 있다.
PROVIDERS: dict[str, Callable[[str], dict]] = {}


def _valid_live(d) -> bool:
    try:
        return (isinstance(d, dict) and isinstance(d["condition"], str) and d["condition"]
                and all(isinstance(d[k], (int, float)) for k in ("tempC", "humidity", "windMs")))
    except KeyError:
        return False


def weather(region: str | None) -> dict:
    region = (region or DEFAULT_REGION).strip()
    if region not in SAMPLES:
        raise bad("지원하지 않는 지역입니다.", "region")
    name = config.weather_provider()
    if not name:
        error = "날씨 공급자가 설정되지 않아 샘플 데이터를 표시합니다."
    elif name not in PROVIDERS:
        error = f"등록되지 않은 날씨 공급자입니다: {name}"
    else:
        try:
            data = PROVIDERS[name](region)
            if _valid_live(data):
                return {"region": region, "source": "LIVE", "obsDt": data.get("obsDt"),
                        "tempC": data["tempC"], "condition": data["condition"], "humidity": data["humidity"],
                        "windMs": data["windMs"], "error": None}
            error = "날씨 공급자 응답 형식이 올바르지 않습니다."
        except Exception as e:  # 공급자 실패는 샘플로 대체
            error = f"날씨 공급자 호출 실패: {e}"
    return {"region": region, "source": "SAMPLE", "obsDt": config.TODAY, **SAMPLES[region], "error": error}
