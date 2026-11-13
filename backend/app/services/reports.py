"""챗봇 보고서(명세 외 요청 기능): 호선·공정·도면 현황을 PDF 또는 Excel로 만든다.

MCP 서버(app.hull_mcp)의 build_report 도구가 호출한다. 메뉴 조회 권한이 없는 영역은 보고서에서 빠진다.
파일은 <저장소>/reports/<사번>/<report_id>.<확장자>에 두고, 다운로드는 만든 사람만 할 수 있다.
"""
import io
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import config
from ..db import rows
from ..errors import bad, not_found
from .common import VIEW, code_map, menu_levels
from .hulls import get_hull_row, list_hulls, milestones
from .plans import hull_plans

FORMATS = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
REPORT_ID = re.compile(r"^[0-9a-f]{24}$")
# 한글 글꼴 (경로, 컬렉션 내 번호): 환경 변수 → macOS 기본 → 리눅스 Nanum/Noto 순으로 찾는다.
FONT_CANDIDATES = [(os.environ.get("SHIPYARD_REPORT_FONT"), 0), ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),
                   ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0), ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 1)]


def report_dir(emp_no: str) -> Path:
    return config.file_dir().parent / "reports" / re.sub(r"[^A-Za-z0-9._-]", "_", emp_no)


# ---- 데이터 모으기
def collect(conn, emp_no: str, hull_no: str | None) -> dict:
    lv = menu_levels(conn, emp_no)
    can = {k: lv.get(m, 0) >= VIEW for k, m in (("hull", "M11"), ("plan", "M21"), ("dwg", "M31"))}
    if not any(can.values()):
        raise bad("보고서에 넣을 수 있는 메뉴 권한(호선·공정·도면 조회)이 없습니다.")
    if hull_no:
        get_hull_row(conn, hull_no)
    names = {g: code_map(conn, g) for g in ("SHIPTYPE", "HULLSTAT", "PLANSTAT", "DWGSTAT", "DWGDISC")}
    hulls = [h for h in list_hulls(conn) if not hull_no or h["hull_no"] == hull_no] if can["hull"] else []
    plans = []
    if can["plan"]:
        targets = [hull_no] if hull_no else [r["HullNo"] for r in rows(conn, "SELECT HullNo FROM TB_MST_Hull WHERE UseYN=1 ORDER BY HullNo")]
        for no in targets:
            plans += hull_plans(conn, no)
    drawings = []
    if can["dwg"]:
        sql = ("SELECT d.DrawingNo, d.DrawingNm, d.HullNo, b.BlockCd, d.Discipline, d.DwgStatus, d.CurrentRevNo, "
               "u.display_name DesignerNm FROM TB_DWG_Drawing d LEFT JOIN TB_MST_Block b ON b.BlockId=d.BlockId "
               "LEFT JOIN users u ON u.emp_no=d.DesignerEmpNo")
        drawings = rows(conn, sql + (" WHERE d.HullNo=? ORDER BY d.DrawingNo" if hull_no else " ORDER BY d.DrawingNo"),
                        *([hull_no] if hull_no else []))
    ms = milestones(conn, hull_no) if hull_no and can["hull"] else []
    author = rows(conn, "SELECT display_name FROM users WHERE emp_no=?", emp_no)
    kst = datetime.now(timezone.utc) + timedelta(hours=9)
    by_status: dict[str, int] = {}
    for p in plans:
        by_status[p["plan_status"]] = by_status.get(p["plan_status"], 0) + 1
    dwg_status: dict[str, int] = {}
    for d in drawings:
        dwg_status[d["DwgStatus"]] = dwg_status.get(d["DwgStatus"], 0) + 1
    return {
        "title": f"{hull_no} 호선 현황 보고서" if hull_no else "전체 호선 현황 보고서",
        "hull_no": hull_no, "author": author[0]["display_name"] if author else emp_no, "emp_no": emp_no,
        "created": kst.strftime("%Y-%m-%d %H:%M"), "base_date": config.TODAY, "can": can, "names": names,
        "hulls": hulls, "plans": plans, "drawings": drawings, "milestones": ms,
        "kpi": {"hulls": len(hulls), "plans": len(plans), "delay": by_status.get("DELAY", 0),
                "waiting": sum(1 for p in plans if p["drawing_wait"]), "drawings": len(drawings),
                "unissued": sum(1 for d in drawings if d["DwgStatus"] not in ("ISSUED", "OBSOLETE"))},
        "plan_status": by_status, "dwg_status": dwg_status,
    }


def _num(v) -> str:
    v = float(v or 0)
    return str(int(v)) if v.is_integer() else f"{v:.1f}"


def _rows_for(r: dict):
    n = r["names"]
    hull_rows = [[h["hull_no"], h["hull_nm"], n["SHIPTYPE"].get(h["ship_type"], h["ship_type"] or "-"),
                  n["HULLSTAT"].get(h["hull_status"], h["hull_status"] or "-"), h.get("owner_nm") or "-",
                  h.get("delivery_dt") or "-", "-" if h["progress"] is None else f"{h['progress']}%", h["delay_count"] or 0]
                 for h in r["hulls"]]
    plan_rows = [[p["hull_no"], p["block_cd"] or "호선", p["proc_nm"], p["plan_start_dt"], p["plan_end_dt"],
                  f"{_num(p['progress_rate'])}%", n["PLANSTAT"].get(p["plan_status"], p["plan_status"]), p["manager_nm"] or "-",
                  ", ".join(b["drawing_no"] for b in p["blockers"]) or "-"] for p in r["plans"]]
    dwg_rows = [[d["DrawingNo"], d["DrawingNm"], d["HullNo"], d["BlockCd"] or "-", n["DWGDISC"].get(d["Discipline"], d["Discipline"] or "-"),
                 f"Rev{d['CurrentRevNo']}", n["DWGSTAT"].get(d["DwgStatus"], d["DwgStatus"]), d["DesignerNm"] or "-"] for d in r["drawings"]]
    return hull_rows, plan_rows, dwg_rows


HULL_HEAD = ["호선번호", "호선명", "선종", "상태", "선주", "인도예정", "진척률", "지연"]
PLAN_HEAD = ["호선", "블록", "공정", "계획 시작", "계획 종료", "진척", "상태", "담당자", "미배포 필수 도면"]
DWG_HEAD = ["도면번호", "도면명", "호선", "블록", "분야", "Rev", "상태", "설계자"]
STATUS_RGB = {"PLAN": (148, 163, 184), "READY": (14, 165, 233), "WORK": (37, 99, 235), "DONE": (22, 163, 74), "DELAY": (220, 38, 38)}


# ---- Excel
def to_xlsx(r: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    head_fill = PatternFill("solid", fgColor="1B3A66")
    head_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="D9DEE8")
    hull_rows, plan_rows, dwg_rows = _rows_for(r)

    ws = wb.active
    ws.title = "요약"
    ws["A1"] = r["title"]
    ws["A1"].font = Font(size=16, bold=True, color="12294A")
    ws["A2"] = f"작성 {r['created']} · 작성자 {r['author']} · 기준일 {r['base_date']}"
    ws["A2"].font = Font(color="6B7280")
    k = r["kpi"]
    items = [("호선", k["hulls"]), ("공정", k["plans"]), ("지연 공정", k["delay"]), ("도면 대기 공정", k["waiting"]),
             ("도면", k["drawings"]), ("미배포 도면", k["unissued"])]
    for i, (label, v) in enumerate(items):
        c = ws.cell(row=4, column=1 + i, value=label)
        c.font, c.fill, c.alignment = head_font, head_fill, Alignment(horizontal="center")
        c = ws.cell(row=5, column=1 + i, value=v)
        c.font, c.alignment = Font(size=14, bold=True, color="DC2626" if label == "지연 공정" and v else "1F2937"), Alignment(horizontal="center")
    row = 7
    ws.cell(row=row, column=1, value="공정 상태별").font = Font(bold=True)
    for i, (st, cnt) in enumerate(sorted(r["plan_status"].items())):
        ws.cell(row=row + 1 + i, column=1, value=r["names"]["PLANSTAT"].get(st, st))
        ws.cell(row=row + 1 + i, column=2, value=cnt)
    ws.cell(row=row, column=4, value="도면 상태별").font = Font(bold=True)
    for i, (st, cnt) in enumerate(sorted(r["dwg_status"].items())):
        ws.cell(row=row + 1 + i, column=4, value=r["names"]["DWGSTAT"].get(st, st))
        ws.cell(row=row + 1 + i, column=5, value=cnt)
    if r["milestones"]:
        row = 9 + max(len(r["plan_status"]), len(r["dwg_status"]))
        ws.cell(row=row, column=1, value="주요 일정").font = Font(bold=True)
        for i, m in enumerate(r["milestones"]):
            ws.cell(row=row + 1 + i, column=1, value=m["name"])
            ws.cell(row=row + 1 + i, column=2, value=m["plan_dt"] or "-")
            ws.cell(row=row + 1 + i, column=3, value=m["actual_dt"] or "-")
    for col in range(1, 7):
        ws.column_dimensions[get_column_letter(col)].width = 16
    skipped = [name for key, name in (("hull", "호선"), ("plan", "공정"), ("dwg", "도면")) if not r["can"][key]]
    if skipped:
        ws.cell(row=3, column=1, value=f"조회 권한이 없어 제외: {', '.join(skipped)}").font = Font(color="B45309")

    def table(name, head, data, widths):
        s = wb.create_sheet(name)
        s.append(head)
        for c in s[1]:
            c.font, c.fill, c.alignment = head_font, head_fill, Alignment(horizontal="center", vertical="center")
        for line in data:
            s.append(line)
        for row_cells in s.iter_rows(min_row=1, max_row=s.max_row):
            for c in row_cells:
                c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
        for i, w in enumerate(widths, 1):
            s.column_dimensions[get_column_letter(i)].width = w
        s.freeze_panes = "A2"
        if data:
            s.auto_filter.ref = f"A1:{get_column_letter(len(head))}{len(data) + 1}"
        return s

    if r["can"]["hull"]:
        table("호선", HULL_HEAD, hull_rows, [10, 24, 12, 10, 22, 12, 9, 7])
    if r["can"]["plan"]:
        s = table("공정", PLAN_HEAD, plan_rows, [8, 8, 12, 12, 12, 8, 9, 10, 26])
        red = Font(color="DC2626", bold=True)
        for i, p in enumerate(r["plans"], 2):
            if p["plan_status"] == "DELAY":
                s.cell(row=i, column=7).font = red
    if r["can"]["dwg"]:
        table("도면", DWG_HEAD, dwg_rows, [18, 28, 8, 8, 8, 7, 9, 10])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---- PDF
def _font_path() -> tuple[str, int]:
    for p, idx in FONT_CANDIDATES:
        if p and Path(p).is_file():
            return p, idx
    raise bad("PDF에 쓸 한글 글꼴을 찾지 못했습니다. SHIPYARD_REPORT_FONT 환경 변수에 TTF 경로를 지정하세요.")


def to_pdf(r: dict) -> bytes:
    from fpdf import FPDF

    font, idx = _font_path()
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(True, margin=14)
    if font.lower().endswith(".ttc"):
        pdf.add_font("ko", "", font, collection_font_number=idx)
    else:
        pdf.add_font("ko", "", font)
    pdf.set_title(r["title"])
    pdf.set_author(r["author"])
    pdf.set_creator("SWP Shipyard")
    navy, muted, line = (18, 41, 74), (107, 114, 128), (217, 222, 232)

    def footer_hook():
        pdf.set_y(-10)
        pdf.set_font("ko", size=8)
        pdf.set_text_color(*muted)
        pdf.cell(0, 5, f"SWP 조선소 통합관리 · {r['title']} · {pdf.page_no()}쪽", align="C")

    pdf.footer = footer_hook  # type: ignore[method-assign]
    pdf.add_page()
    pdf.set_fill_color(*navy)
    pdf.rect(0, 0, 297, 24, "F")
    pdf.set_xy(12, 6)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("ko", size=17)
    pdf.cell(0, 8, r["title"])
    pdf.set_xy(12, 15)
    pdf.set_font("ko", size=9)
    pdf.cell(0, 5, f"작성 {r['created']}  ·  작성자 {r['author']}  ·  기준일 {r['base_date']}")
    pdf.set_y(30)

    k = r["kpi"]
    cards = [("호선", k["hulls"], None), ("공정", k["plans"], None), ("지연 공정", k["delay"], (220, 38, 38) if k["delay"] else None),
             ("도면 대기 공정", k["waiting"], (217, 119, 6) if k["waiting"] else None), ("도면", k["drawings"], None),
             ("미배포 도면", k["unissued"], (217, 119, 6) if k["unissued"] else None)]
    w = (297 - 24 - 5 * 4) / 6
    for i, (label, v, color) in enumerate(cards):
        x = 12 + i * (w + 4)
        pdf.set_draw_color(*line)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x, 30, w, 20, "DF")
        pdf.set_fill_color(*(color or (37, 99, 235)))
        pdf.rect(x, 30, 1.2, 20, "F")
        pdf.set_xy(x + 4, 32)
        pdf.set_font("ko", size=8)
        pdf.set_text_color(*muted)
        pdf.cell(w - 6, 5, label)
        pdf.set_xy(x + 4, 38)
        pdf.set_font("ko", size=16)
        pdf.set_text_color(*(color or (31, 41, 55)))
        pdf.cell(w - 6, 9, str(v))
    pdf.set_y(56)

    # 공정 상태 막대
    total = sum(r["plan_status"].values())
    if total:
        pdf.set_font("ko", size=10)
        pdf.set_text_color(31, 41, 55)
        pdf.cell(0, 6, "공정 상태 분포", new_x="LMARGIN", new_y="NEXT")
        x, y, width = 12, pdf.get_y() + 1, 297 - 24
        for st in ("DONE", "WORK", "READY", "PLAN", "DELAY"):
            n = r["plan_status"].get(st, 0)
            if not n:
                continue
            seg = width * n / total
            pdf.set_fill_color(*STATUS_RGB[st])
            pdf.rect(x, y, seg, 6, "F")
            if seg > 22:
                pdf.set_xy(x, y + .6)
                pdf.set_font("ko", size=7.5)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(seg, 5, f"{r['names']['PLANSTAT'].get(st, st)} {n}", align="C")
            x += seg
        pdf.set_y(y + 10)

    skipped = [name for key, name in (("hull", "호선"), ("plan", "공정"), ("dwg", "도면")) if not r["can"][key]]
    if skipped:
        pdf.set_font("ko", size=8.5)
        pdf.set_text_color(180, 83, 9)
        pdf.cell(0, 5, f"조회 권한이 없어 제외한 영역: {', '.join(skipped)}", new_x="LMARGIN", new_y="NEXT")

    def section(title, head, data, widths, highlight=None):
        pdf.ln(2)
        pdf.set_font("ko", size=11)
        pdf.set_text_color(*navy)
        pdf.cell(0, 7, f"{title} ({len(data)})", new_x="LMARGIN", new_y="NEXT")
        if not data:
            pdf.set_font("ko", size=9)
            pdf.set_text_color(*muted)
            pdf.cell(0, 6, "자료가 없습니다.", new_x="LMARGIN", new_y="NEXT")
            return
        pdf.set_font("ko", size=8)
        pdf.set_draw_color(*line)
        pdf.set_fill_color(244, 247, 251)  # 줄무늬 행 색(직전 도형의 채움색이 이어지지 않게)
        pdf.set_text_color(31, 41, 55)
        with pdf.table(col_widths=widths, line_height=5.2, text_align="LEFT", borders_layout="HORIZONTAL_LINES",
                       headings_style=__import__("fpdf").FontFace(color=(255, 255, 255), fill_color=navy),
                       cell_fill_color=(246, 248, 251), cell_fill_mode="ROWS") as t:
            t.row(head)
            for i, line_data in enumerate(data):
                row = t.row()
                for j, v in enumerate(line_data):
                    style = highlight(i, j) if highlight else None
                    row.cell(str(v), style=style)

    hull_rows, plan_rows, dwg_rows = _rows_for(r)
    if r["can"]["hull"]:
        section("호선 현황", HULL_HEAD, hull_rows, [16, 40, 20, 14, 36, 20, 14, 10])
    if r["milestones"]:
        section("주요 일정", ["일정", "계획", "실적", "차이(일)"],
                [[m["name"], m["plan_dt"] or "-", m["actual_dt"] or "-", "-" if m["diff_days"] is None else m["diff_days"]]
                 for m in r["milestones"]], [40, 30, 30, 20])
    if r["can"]["plan"]:
        from fpdf import FontFace
        red = FontFace(color=(220, 38, 38))
        plans = r["plans"]
        section("공정 현황", PLAN_HEAD, plan_rows, [12, 12, 20, 20, 20, 12, 14, 18, 40],
                highlight=lambda i, j: red if j == 6 and plans[i]["plan_status"] == "DELAY" else None)
    if r["can"]["dwg"]:
        section("도면 현황", DWG_HEAD, dwg_rows, [30, 50, 12, 12, 12, 10, 14, 16])
    return bytes(pdf.output())


def build(conn, emp_no: str, hull_no: str | None, fmt: str) -> dict:
    if fmt not in FORMATS:
        raise bad("보고서 형식은 pdf 또는 xlsx입니다.", "format")
    r = collect(conn, emp_no, hull_no or None)
    data = to_pdf(r) if fmt == "pdf" else to_xlsx(r)
    report_id = secrets.token_hex(12)
    d = report_dir(emp_no)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{report_id}.{fmt}").write_bytes(data)
    stamp = r["created"].replace("-", "").replace(":", "").replace(" ", "_")
    filename = f"{r['title'].replace(' ', '_')}_{stamp}.{fmt}"
    return {"report_id": report_id, "format": fmt, "filename": filename, "title": r["title"], "size": len(data),
            "summary": r["kpi"]}


def report_file(emp_no: str, report_id: str, fmt: str) -> Path:
    if not REPORT_ID.match(report_id or "") or fmt not in FORMATS:
        raise not_found("REPORT_NOT_FOUND", "보고서를 찾을 수 없습니다.")
    p = report_dir(emp_no) / f"{report_id}.{fmt}"
    if not p.is_file():
        raise not_found("REPORT_NOT_FOUND", "보고서를 찾을 수 없습니다. 다시 만들어 주세요.")
    return p
